from pathlib import Path

import pytest
from fastapi import HTTPException

from routers.dataset import _safe_child_path, _safe_path_component


def test_safe_path_component_removes_directory_segments():
    assert _safe_path_component("../../outside", "task") == "outside"
    assert _safe_path_component("..\\..\\outside", "task") == "outside"


def test_safe_path_component_falls_back_for_empty_values():
    assert _safe_path_component("../..", "task") == "task"


def test_safe_child_path_rejects_traversal(tmp_path: Path):
    with pytest.raises(HTTPException) as exc_info:
        _safe_child_path(tmp_path, "../outside.txt")

    assert exc_info.value.status_code == 400


def test_safe_child_path_allows_files_inside_parent(tmp_path: Path):
    child_path = _safe_child_path(tmp_path, "cloud_labels.txt")

    assert child_path == (tmp_path / "cloud_labels.txt").resolve()
