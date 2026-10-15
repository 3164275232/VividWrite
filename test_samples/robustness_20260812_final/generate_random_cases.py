from __future__ import annotations

import importlib.util
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "robustness_20260812_after_fix" / "generate_random_cases.py"
SEED = 2026081203


def main() -> None:
    spec = importlib.util.spec_from_file_location("heldout_case_generator", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the frozen randomized case generator.")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.ROOT = ROOT
    generator.SEED = SEED
    generator.RNG = random.Random(SEED)
    generator.main()


if __name__ == "__main__":
    main()
