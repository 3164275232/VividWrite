import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile

from storage import save_uploaded_file, save_user_revision, user_directory


class StorageTests(unittest.TestCase):
    def test_uploaded_file_gets_safe_generated_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(filename="chart.PNG", file=io.BytesIO(b"image-data"))
            path = asyncio.run(save_uploaded_file(upload, Path(temp_dir)))

            self.assertEqual(path.suffix, ".png")
            self.assertEqual(path.read_bytes(), b"image-data")
            self.assertNotEqual(path.name, "chart.PNG")

    def test_empty_upload_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(filename="chart.png", file=io.BytesIO())
            with self.assertRaisesRegex(ValueError, "empty"):
                asyncio.run(save_uploaded_file(upload, Path(temp_dir)))

    def test_user_paths_cannot_escape_runtime_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("storage.USER_DATA_DIR", root):
                directory = user_directory("../student/name")
                revision = save_user_revision("../student/name", "draft")

            self.assertEqual(directory.parent, root)
            self.assertTrue(revision.is_relative_to(root))
            self.assertEqual(revision.read_text(encoding="utf-8"), "draft")


if __name__ == "__main__":
    unittest.main()
