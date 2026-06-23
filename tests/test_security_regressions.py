import os
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("DB_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-regression-tests-12345")

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import security
from routers import dataset


def _dataset_payload(**overrides):
    payload = {
        "task_id": "task-123",
        "data": [
            {
                "cloud_name": "cloud-1",
                "scene_type": "indoor",
                "points_data": [[1, 2, 3, 4]],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_rejects_tokens_signed_with_the_old_public_default_secret():
    forged_token = jwt.encode(
        {
            "sub": "victim@example.com",
            "exp": datetime.utcnow() + timedelta(minutes=5),
        },
        "your_super_secret_key_for_graduation_project",
        algorithm=security.ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc_info:
        security.get_current_user_email(token=forged_token)

    assert exc_info.value.status_code == 401


def test_dataset_save_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "STORAGE_ROOT", tmp_path)
    app = FastAPI()
    app.include_router(dataset.router)

    response = TestClient(app).post("/api/dataset/save", json=_dataset_payload())

    assert response.status_code == 401
    assert list(tmp_path.iterdir()) == []


def test_dataset_save_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "STORAGE_ROOT", tmp_path)
    app = FastAPI()
    app.dependency_overrides[dataset.get_current_user] = lambda: SimpleNamespace(id=1)
    app.include_router(dataset.router)

    response = TestClient(app).post(
        "/api/dataset/save",
        json=_dataset_payload(task_id="../../outside"),
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_dataset_save_keeps_valid_files_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "STORAGE_ROOT", tmp_path)
    app = FastAPI()
    app.dependency_overrides[dataset.get_current_user] = lambda: SimpleNamespace(id=1)
    app.include_router(dataset.router)

    response = TestClient(app).post("/api/dataset/save", json=_dataset_payload())

    assert response.status_code == 200
    saved_dirs = list(tmp_path.iterdir())
    assert len(saved_dirs) == 1
    saved_file = saved_dirs[0] / "cloud-1_labels.txt"
    assert saved_file.read_text() == "1 2 3 4\n"
