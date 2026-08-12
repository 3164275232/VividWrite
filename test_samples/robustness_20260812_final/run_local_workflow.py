from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "robustness_20260812_after_fix" / "run_local_workflow.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("heldout_workflow_runner", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the frozen black-box workflow runner.")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.ROOT = ROOT
    runner.main()


if __name__ == "__main__":
    main()
