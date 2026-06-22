import asyncio
import importlib
import sys
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException


VALID_JWT_SECRET = "test-jwt-secret-for-critical-regression-tests"
DEFAULT_JWT_SECRET = "your_super_secret_key_for_graduation_project"


def reload_security(monkeypatch, secret):
    sys.modules.pop("security", None)
    if secret is None:
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET_KEY", secret)
    return importlib.import_module("security")


def test_jwt_tokens_cannot_be_forged_with_public_default_secret(monkeypatch):
    security = reload_security(monkeypatch, VALID_JWT_SECRET)

    token = security.create_access_token({"sub": "victim@example.com"})

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, DEFAULT_JWT_SECRET, algorithms=[security.ALGORITHM])


def test_jwt_secret_must_be_private(monkeypatch):
    with pytest.raises(RuntimeError):
        reload_security(monkeypatch, DEFAULT_JWT_SECRET)


def test_dataset_save_route_requires_authenticated_user(monkeypatch):
    reload_security(monkeypatch, VALID_JWT_SECRET)
    dataset = importlib.import_module("routers.dataset")
    from dependencies import get_current_user

    route = next(route for route in dataset.router.routes if route.path == "/api/dataset/save")

    assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)


def test_dataset_save_rejects_path_traversal_before_writing(monkeypatch, tmp_path):
    reload_security(monkeypatch, VALID_JWT_SECRET)
    dataset = importlib.import_module("routers.dataset")
    from models import PointData, SaveDatasetRequest

    dataset.STORAGE_PATH = tmp_path / "datasets"
    dataset.STORAGE_PATH.mkdir()
    req = SaveDatasetRequest(
        task_id="../outside",
        data=[PointData(cloud_name="cloud", scene_type="indoor", points_data=[])],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dataset.save_annotated_dataset(req, user=object()))

    assert exc.value.status_code == 400
    assert list(Path(tmp_path).rglob("*")) == [tmp_path / "datasets"]


def test_runtime_output_directory_is_created_for_static_mount(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    runtime_paths = importlib.import_module("runtime_paths")

    runtime_paths.ensure_runtime_directories()

    assert (tmp_path / runtime_paths.OUTPUT_DIR).is_dir()
