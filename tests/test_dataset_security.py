import os
from pathlib import Path

os.environ.setdefault("DB_URL", "sqlite://")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import dataset


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "STORAGE_PATH", str(tmp_path / "datasets"))

    app = FastAPI()
    app.dependency_overrides[dataset.get_current_user] = lambda: object()
    app.include_router(dataset.router)
    return TestClient(app)


def _payload(task_id="task-123", cloud_name="Cloud_Result"):
    return {
        "task_id": task_id,
        "data": [
            {
                "cloud_name": cloud_name,
                "scene_type": "indoor",
                "points_data": [[1, 2, 3, 4], [5, 6, 7, 8]],
            }
        ],
    }


def test_save_dataset_writes_inside_storage_root(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/dataset/save", json=_payload())

    assert response.status_code == 200
    save_path = Path(response.json()["data"]["path"])
    assert save_path.is_relative_to((tmp_path / "datasets").resolve())

    label_file = save_path / "Cloud_Result_labels.txt"
    assert label_file.read_text(encoding="utf-8") == "1 2 3 4\n5 6 7 8\n"


def test_save_dataset_rejects_traversal_task_id(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/dataset/save", json=_payload(task_id="../../outside"))

    assert response.status_code == 400
    assert not (tmp_path / "outside").exists()
    assert not (tmp_path / "datasets").exists()


def test_save_dataset_rejects_traversal_cloud_name_before_writing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/dataset/save",
        json=_payload(cloud_name="../outside"),
    )

    assert response.status_code == 400
    assert not (tmp_path / "outside_labels.txt").exists()
    assert not (tmp_path / "datasets").exists()


def test_save_dataset_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "STORAGE_PATH", str(tmp_path / "datasets"))

    app = FastAPI()
    app.include_router(dataset.router)
    client = TestClient(app)

    response = client.post("/api/dataset/save", json=_payload())

    assert response.status_code == 401
    assert not (tmp_path / "datasets").exists()
