# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
import os
import json
import time
from pathlib import Path
from models import SaveDatasetRequest
from response import success_response
from dependencies import get_current_user

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = Path("./storage/datasets")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


def _safe_path_component(value: str, field_name: str) -> str:
    value = (value or "").strip()
    if not value or value in {".", ".."} or Path(value).name != value:
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    if "\x00" in value:
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return value


def _ensure_under_storage(path: Path, storage_root: Path) -> None:
    try:
        path.relative_to(storage_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="保存路径非法")


@router.post("/save")
async def save_annotated_dataset(req: SaveDatasetRequest, current_user=Depends(get_current_user)):
    try:
        storage_root = STORAGE_PATH.resolve()
        task_id = _safe_path_component(req.task_id, "task_id")
        cloud_names = [
            _safe_path_component(cloud.cloud_name, "cloud_name")
            for cloud in req.data
        ]
        folder_name = f"{task_id}_{int(time.time())}"
        save_dir = (storage_root / folder_name).resolve()
        _ensure_under_storage(save_dir, storage_root)
        save_dir.mkdir(parents=True, exist_ok=False)

        for cloud, cloud_name in zip(req.data, cloud_names):
            label_filename = f"{cloud_name}_labels.txt"
            file_path = (save_dir / label_filename).resolve()
            _ensure_under_storage(file_path, storage_root)

            with open(file_path, "w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！",
            data={"path": str(save_dir)},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
