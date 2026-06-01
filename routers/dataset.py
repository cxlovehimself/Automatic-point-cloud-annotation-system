# routers/dataset.py
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = Path("./storage/datasets")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


def _safe_path_component(value: str, fallback: str) -> str:
    raw_value = (value or "").replace("\\", "/")
    basename = raw_value.rsplit("/", 1)[-1].strip()
    safe_value = "".join(
        char if char.isalnum() or char in "._-" else "_"
        for char in basename
    ).strip("._")
    return (safe_value or fallback)[:80]


def _safe_child_path(parent: Path, filename: str) -> Path:
    parent_root = parent.resolve()
    child_path = (parent_root / filename).resolve()
    if not child_path.is_relative_to(parent_root):
        raise HTTPException(status_code=400, detail="非法文件名")
    return child_path


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    _current_user=Depends(get_current_user),
):
    try:
        folder_name = f"{_safe_path_component(req.task_id, 'task')}_{int(time.time())}"
        save_dir = _safe_child_path(STORAGE_PATH, folder_name)
        response_path = STORAGE_PATH / folder_name
        save_dir.mkdir(parents=True, exist_ok=False)

        for cloud in req.data:
            label_filename = f"{_safe_path_component(cloud.cloud_name, 'cloud')}_labels.txt"
            file_path = _safe_child_path(save_dir, label_filename)

            with file_path.open("w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！",
            data={"path": str(response_path)},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
