import os
import tempfile
import unittest

from runtime_paths import RUNTIME_DIRECTORIES, ensure_runtime_directories


class RuntimePathsTests(unittest.TestCase):
    def test_ensure_runtime_directories_creates_ignored_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                ensure_runtime_directories()

                for directory in RUNTIME_DIRECTORIES:
                    self.assertTrue(directory.is_dir(), f"{directory} was not created")
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
