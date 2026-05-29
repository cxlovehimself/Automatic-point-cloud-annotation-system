import sys
import types

import pytest


def _install_runtime_stubs():
    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code, detail=None, headers=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
            self.headers = headers

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def post(self, *args, **kwargs):
            return lambda fn: fn

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def delete(self, *args, **kwargs):
            return lambda fn: fn

    def depends(value=None):
        return value

    fastapi.APIRouter = APIRouter
    fastapi.Depends = depends
    fastapi.File = depends
    fastapi.Form = depends
    fastapi.HTTPException = HTTPException
    fastapi.Request = type("Request", (), {})
    fastapi.UploadFile = type("UploadFile", (), {})
    sys.modules["fastapi"] = fastapi

    models = types.ModuleType("models")
    models.SaveDatasetRequest = type("SaveDatasetRequest", (), {})
    sys.modules["models"] = models

    dependencies = types.ModuleType("dependencies")
    dependencies.get_current_user = lambda: None
    dependencies.get_db = lambda: None
    sys.modules["dependencies"] = dependencies

    sqlmodel = types.ModuleType("sqlmodel")
    sqlmodel.Session = type("Session", (), {})
    sys.modules["sqlmodel"] = sqlmodel

    worker = types.ModuleType("worker")
    worker.celery_app = object()
    worker.run_ai_segmentation_task = type("TaskRunner", (), {"delay": lambda self, **kwargs: None})()
    sys.modules["worker"] = worker

    celery = types.ModuleType("celery")
    celery_result = types.ModuleType("celery.result")
    celery_result.AsyncResult = type("AsyncResult", (), {})
    sys.modules["celery"] = celery
    sys.modules["celery.result"] = celery_result

    return HTTPException


HTTPException = _install_runtime_stubs()
from routers import dataset, task  # noqa: E402


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
