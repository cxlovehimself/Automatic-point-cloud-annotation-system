import os

import pytest
from fastapi import HTTPException

os.environ.setdefault("DB_URL", "sqlite:///./test.db")

from routers import dataset, task


@pytest.mark.parametrize("value", ["", ".", "..", "../evil", "a/b", "/tmp/evil"])
def test_dataset_path_component_rejects_traversal(value):
    with pytest.raises(HTTPException) as exc_info:
        dataset._safe_path_component(value, "field")

    assert exc_info.value.status_code == 400


def test_dataset_path_component_accepts_plain_filename():
    assert dataset._safe_path_component("Cloud_Result upload", "cloud_name") == "Cloud_Result upload"


class FakeTaskResult:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


def test_task_owner_allows_registered_pending_task():
    task._TASK_OWNERS.clear()
    task._remember_task_owner("task-1", 42)

    task._ensure_task_owner("task-1", FakeTaskResult("PENDING"), 42)


def test_task_owner_allows_completed_backend_owner_after_restart():
    task._TASK_OWNERS.clear()
    result = FakeTaskResult("SUCCESS", {"_owner_user_id": 42, "result_url": "https://example.test/model.ply"})

    task._ensure_task_owner("task-1", result, 42)


def test_task_owner_rejects_other_user():
    task._TASK_OWNERS.clear()
    task._remember_task_owner("task-1", 42)

    with pytest.raises(HTTPException) as exc_info:
        task._ensure_task_owner("task-1", FakeTaskResult("STARTED"), 7)

    assert exc_info.value.status_code == 404


def test_public_task_result_strips_owner_metadata():
    result = FakeTaskResult("SUCCESS", {"_owner_user_id": 42, "result_url": "https://example.test/model.ply"})

    assert task._public_task_result(result) == {"result_url": "https://example.test/model.ply"}
