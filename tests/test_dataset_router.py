import asyncio
import inspect
import os
from pathlib import Path

from fastapi.params import Depends

os.environ.setdefault("DB_URL", "sqlite://")

from dependencies import get_current_user
from models import PointData, SaveDatasetRequest
from routers import dataset


def test_save_dataset_route_requires_authenticated_user():
    current_user_param = inspect.signature(dataset.save_annotated_dataset).parameters["_current_user"]

    assert isinstance(current_user_param.default, Depends)
    assert current_user_param.default.dependency is get_current_user


def test_save_dataset_sanitizes_paths_and_stays_in_storage(monkeypatch, tmp_path):
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    monkeypatch.setattr(dataset, "STORAGE_PATH", storage_root)

    req = SaveDatasetRequest(
        task_id="../../outside",
        data=[
            PointData(
                cloud_name="../../pwned",
                scene_type="indoor",
                points_data=[[1, 2, 3, 4]],
            )
        ],
    )

    response = asyncio.run(dataset.save_annotated_dataset(req, _current_user=object()))
    save_dir = Path(response["data"]["path"]).resolve()

    assert storage_root.resolve() in save_dir.parents
    assert not (tmp_path / "pwned_labels.txt").exists()

    saved_files = list(save_dir.iterdir())
    assert [path.name for path in saved_files] == ["pwned_labels.txt"]
    assert saved_files[0].read_text(encoding="utf-8") == "1 2 3 4\n"
