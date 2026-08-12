from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
BACKEND = PROJECT / "backend"
BASELINE_RUNNER = PROJECT / "test_samples" / "robustness_20260812" / "run_local_workflow.py"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from chart_feedback import ChartFeedbackService  # noqa: E402


def load_verifier():
    spec = importlib.util.spec_from_file_location("baseline_blackbox_verifier", BASELINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the independent baseline verifier.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


def canonical_manifest_hash(manifest: dict) -> str:
    canonical = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_frozen_inputs(manifest: dict) -> str:
    expected_manifest_hash = (ROOT / "manifest.sha256").read_text(encoding="ascii").split()[0]
    actual_manifest_hash = canonical_manifest_hash(manifest)
    if actual_manifest_hash != expected_manifest_hash:
        raise RuntimeError("cases.json changed after it was frozen.")
    for case in manifest["cases"]:
        essay_hash = hashlib.sha256(case["essay"].encode("utf-8")).hexdigest()
        if essay_hash != case["essay_sha256"]:
            raise RuntimeError(f"Essay text changed for {case['case_id']}.")
    for relative_path, expected_hash in manifest["code_sha256"].items():
        actual_hash = hashlib.sha256((PROJECT / relative_path).read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(f"Product code changed after test freezing: {relative_path}")
    return expected_manifest_hash


def expected_outcome(case: dict) -> tuple[list[str], bool | None]:
    if case["chart_type"] == "pie" and case["expected_error"] == "trend_direction_error":
        return [], False
    return [case["expected_error"]], None


def validate_semantic_visual(case: dict, chart_data: dict) -> dict:
    needs_alert = case["expected_error"] in {"trend_direction_error", "comparison_ranking_error"}
    if case["chart_type"] == "pie" and case["expected_error"] == "trend_direction_error":
        needs_alert = False
    title = (chart_data.get("vega_lite_spec") or {}).get("title")
    subtitles = title.get("subtitle") if isinstance(title, dict) else []
    if isinstance(subtitles, str):
        subtitles = [subtitles]
    subtitles = subtitles if isinstance(subtitles, list) else []
    visible_alert = any(str(item).startswith("TEXT CONFLICT:") for item in subtitles)
    alert_count = int((chart_data.get("style") or {}).get("semantic_alert_count") or 0)
    return {
        "required": needs_alert,
        "correct": visible_alert and alert_count > 0 if needs_alert else not visible_alert,
        "visible_alert": visible_alert,
        "alert_count": alert_count,
        "subtitles": subtitles,
    }


def main() -> None:
    manifest = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    manifest_hash = verify_frozen_inputs(manifest)
    output_dir = ROOT / "generated_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = ROOT / "results_raw.json"
    existing = {}
    if raw_path.exists():
        saved = json.loads(raw_path.read_text(encoding="utf-8"))
        if saved.get("manifest_sha256") != manifest_hash:
            raise RuntimeError("Existing results belong to a different frozen manifest.")
        existing = {item["case_id"]: item for item in saved.get("results", [])}

    results = []
    service = ChartFeedbackService(BACKEND / "generated_charts")
    started = time.time()
    total = len(manifest["cases"])
    for index, case in enumerate(manifest["cases"], start=1):
        if case["case_id"] in existing and existing[case["case_id"]].get("success"):
            results.append(existing[case["case_id"]])
            print(f"[{index:02d}/{total}] {case['case_id']} RESUME", flush=True)
            continue
        expected_errors, expected_trend_applicable = expected_outcome(case)
        case_started = time.time()
        try:
            chart_data, filename = service.generate(
                chart_type=case["chart_type"],
                requirement=(
                    "Summarise the information by selecting and reporting the main features, "
                    "and make comparisons where relevant."
                ),
                student_answer=case["essay"],
                deplot_text=VERIFIER.DEPLOT[case["chart_type"]],
                image_path=VERIFIER.IMAGES[case["chart_type"]],
            )
            source = BACKEND / "generated_charts" / filename
            destination = output_dir / f"{case['case_id']}.png"
            shutil.copy2(source, destination)
            taxonomy = chart_data.get("error_taxonomy") or {}
            issues = taxonomy.get("issues") or []
            actual_errors = [item.get("error_type") for item in issues]
            unique_errors = list(dict.fromkeys(actual_errors))
            trend_applicable = (taxonomy.get("applicability") or {}).get("trend_direction_error", {}).get("applicable")
            taxonomy_pass = unique_errors == expected_errors
            if expected_trend_applicable is not None:
                taxonomy_pass = taxonomy_pass and trend_applicable is expected_trend_applicable
            data_validation = VERIFIER.validate_records(case, chart_data.get("records") or [])
            png_validation = VERIFIER.validate_png(destination)
            semantic_validation = validate_semantic_visual(case, chart_data)
            image_correct = data_validation["correct"] and png_validation["valid"] and semantic_validation["correct"]
            item = {
                "case_id": case["case_id"],
                "chart_type": case["chart_type"],
                "expected_error": case["expected_error"],
                "expected_output": expected_errors or ["N/A: trend not applicable"],
                "actual_errors": actual_errors,
                "actual_unique_errors": unique_errors,
                "trend_applicable": trend_applicable,
                "taxonomy_pass": taxonomy_pass,
                "image_correct": image_correct,
                "image_file": str(destination.relative_to(ROOT)).replace("\\", "/"),
                "image_data_validation": data_validation,
                "semantic_visual_validation": semantic_validation,
                "png_validation": png_validation,
                "issues": issues,
                "records": chart_data.get("records") or [],
                "essay": case["essay"],
                "generation_metadata": case["generation_metadata"],
                "duration_seconds": round(time.time() - case_started, 2),
                "success": True,
            }
            status = "PASS" if taxonomy_pass and image_correct else "FAIL"
            print(
                f"[{index:02d}/{total}] {case['case_id']} {status} "
                f"actual={unique_errors or ['N/A']} image={image_correct} "
                f"{item['duration_seconds']:.1f}s",
                flush=True,
            )
        except Exception as exc:
            item = {
                "case_id": case["case_id"],
                "chart_type": case["chart_type"],
                "expected_error": case["expected_error"],
                "expected_output": expected_errors or ["N/A: trend not applicable"],
                "actual_errors": [],
                "actual_unique_errors": [],
                "trend_applicable": None,
                "taxonomy_pass": False,
                "image_correct": False,
                "essay": case["essay"],
                "generation_metadata": case["generation_metadata"],
                "duration_seconds": round(time.time() - case_started, 2),
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"[{index:02d}/{total}] {case['case_id']} ERROR {item['error']}", flush=True)

        results.append(item)
        raw_path.write_text(
            json.dumps({"manifest_sha256": manifest_hash, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = {
        "manifest_sha256": manifest_hash,
        "case_count": len(results),
        "taxonomy_passes": sum(bool(item["taxonomy_pass"]) for item in results),
        "image_passes": sum(bool(item["image_correct"]) for item in results),
        "fully_passed": sum(bool(item["taxonomy_pass"] and item["image_correct"]) for item in results),
        "api_errors": sum(not item["success"] for item in results),
        "duration_seconds": round(time.time() - started, 2),
        "by_chart": {
            chart_type: {
                "cases": sum(item["chart_type"] == chart_type for item in results),
                "taxonomy_passes": sum(item["chart_type"] == chart_type and item["taxonomy_pass"] for item in results),
                "image_passes": sum(item["chart_type"] == chart_type and item["image_correct"] for item in results),
            }
            for chart_type in ("bar", "line", "pie")
        },
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
