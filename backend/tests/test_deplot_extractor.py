import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import deplot_extractor


class DePlotExtractorTests(unittest.TestCase):
    def setUp(self):
        self.original_processor = deplot_extractor._processor
        self.original_model = deplot_extractor._model
        deplot_extractor._processor = object()
        deplot_extractor._model = object()
        deplot_extractor._raw_table_cache.clear()
        deplot_extractor._result_cache.clear()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.image_path = Path(self.temporary_directory.name) / "chart.png"
        Image.new("RGB", (32, 24), "white").save(self.image_path)

    def tearDown(self):
        deplot_extractor._processor = self.original_processor
        deplot_extractor._model = self.original_model
        deplot_extractor._raw_table_cache.clear()
        deplot_extractor._result_cache.clear()
        self.temporary_directory.cleanup()

    def test_auto_and_explicit_type_share_the_same_raw_inference(self):
        raw_table = "Year | 2020<0x0A>Value | 10"
        with (
            patch.object(deplot_extractor, "_ensure_model_loaded"),
            patch.object(
                deplot_extractor,
                "_generate_table",
                return_value=raw_table,
            ) as generate,
            patch.object(
                deplot_extractor,
                "detect_chart_type",
                return_value="bar",
            ),
        ):
            automatic = deplot_extractor.extract_table_from_image_deplot(
                str(self.image_path),
                "auto",
            )
            explicit = deplot_extractor.extract_table_from_image_deplot(
                str(self.image_path),
                "bar",
            )

        self.assertEqual(automatic, explicit)
        self.assertEqual(generate.call_count, 1)

    def test_concurrent_duplicate_requests_run_one_inference(self):
        raw_table = "Year | 2020<0x0A>Value | 10"

        def slow_generate(_image):
            time.sleep(0.05)
            return raw_table

        with (
            patch.object(deplot_extractor, "_ensure_model_loaded"),
            patch.object(
                deplot_extractor,
                "_generate_table",
                side_effect=slow_generate,
            ) as generate,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(
                    deplot_extractor.extract_table_from_image_deplot,
                    str(self.image_path),
                    "bar",
                )
                for _ in range(2)
            ]
            results = [future.result() for future in futures]

        self.assertEqual(results[0], results[1])
        self.assertEqual(generate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
