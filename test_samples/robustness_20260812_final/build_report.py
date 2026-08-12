from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "robustness_20260812_after_fix" / "build_report.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("heldout_report_builder", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the black-box report builder.")
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    report.ROOT = ROOT
    report.main()


if __name__ == "__main__":
    main()
