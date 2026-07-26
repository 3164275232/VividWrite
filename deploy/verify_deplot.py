import argparse
import time

from deplot_extractor import extract_table_from_image_deplot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("--chart-type", default="auto")
    args = parser.parse_args()

    first_started = time.perf_counter()
    first_result = extract_table_from_image_deplot(
        args.image_path,
        args.chart_type,
    )
    first_seconds = time.perf_counter() - first_started

    second_started = time.perf_counter()
    second_result = extract_table_from_image_deplot(
        args.image_path,
        args.chart_type,
    )
    second_seconds = time.perf_counter() - second_started

    assert first_result.strip()
    assert second_result == first_result
    assert second_seconds < max(1.0, first_seconds / 10)

    print(
        "deplot_verification=passed "
        f"first_seconds={first_seconds:.2f} "
        f"cached_seconds={second_seconds:.4f} "
        f"result_characters={len(first_result)}"
    )


if __name__ == "__main__":
    main()
