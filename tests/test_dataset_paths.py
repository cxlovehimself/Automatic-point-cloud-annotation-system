from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException

from routers.dataset import _safe_child_path, _safe_path_component


class DatasetPathTests(unittest.TestCase):
    def test_safe_path_component_removes_directory_segments(self):
        self.assertEqual(_safe_path_component("../../outside", "task"), "outside")
        self.assertEqual(_safe_path_component("..\\..\\outside", "task"), "outside")

    def test_safe_path_component_falls_back_for_empty_values(self):
        self.assertEqual(_safe_path_component("../..", "task"), "task")

    def test_safe_child_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with self.assertRaises(HTTPException) as exc_info:
                _safe_child_path(tmp_path, "../outside.txt")

        self.assertEqual(exc_info.exception.status_code, 400)

    def test_safe_child_path_allows_files_inside_parent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            child_path = _safe_child_path(tmp_path, "cloud_labels.txt")

            self.assertEqual(child_path, (tmp_path / "cloud_labels.txt").resolve())


if __name__ == "__main__":
    unittest.main()
