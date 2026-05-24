import pytest
from fastapi import HTTPException

from routers.dataset import _ensure_within_storage, _safe_path_segment
from routers.task import _task_belongs_to_user, _task_id_for_user


def test_dataset_names_are_reduced_to_safe_path_segments():
    assert _safe_path_segment("../../data/outputs/evil", "task_id") == "evil"
    assert _safe_path_segment("..\\..\\secret", "cloud_name") == "secret"


@pytest.mark.parametrize("value", ["", ".", "..", "nested/.."])
def test_dataset_rejects_empty_or_parent_segments(value):
    with pytest.raises(HTTPException):
        _safe_path_segment(value, "task_id")


def test_dataset_paths_must_stay_under_storage_root(tmp_path):
    root = tmp_path / "datasets"
    root.mkdir()

    inside = _ensure_within_storage(root / "task" / "labels.txt", root)
    assert inside == (root / "task" / "labels.txt").resolve()

    with pytest.raises(HTTPException):
        _ensure_within_storage(root / ".." / "outside.txt", root)


def test_task_ids_are_bound_to_requesting_user():
    task_id = _task_id_for_user(42)

    assert _task_belongs_to_user(task_id, 42)
    assert not _task_belongs_to_user(task_id, 43)
