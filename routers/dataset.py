# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
import os
import time
from pathlib import Path
from models import SaveDatasetRequest
from dependencies import get_current_user
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = "./storage/datasets"
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)


def _validate_path_component(value: str, field_name: str) -> str:
    name = value.strip()
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or Path(name).is_absolute()
    ):
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return name


def _safe_child_path(base_dir: Path, *components: str) -> Path:
    candidate = base_dir.joinpath(*components).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="保存路径越界")
    return candidate


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user=Depends(get_current_user),
):
    storage_root = Path(STORAGE_PATH).resolve()
    storage_root.mkdir(parents=True, exist_ok=True)

    task_id = _validate_path_component(req.task_id, "task_id")
    cloud_names = [
        _validate_path_component(cloud.cloud_name, "cloud_name")
        for cloud in req.data
    ]
    try:
        folder_name = f"{task_id}_{int(time.time())}"
        save_dir = _safe_child_path(storage_root, folder_name)
        save_dir.mkdir()

        for cloud, cloud_name in zip(req.data, cloud_names):
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _safe_child_path(save_dir, label_filename)

            with file_path.open("w", encoding="utf-8") as f:
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
