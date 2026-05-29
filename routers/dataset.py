# routers/dataset.py
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import time
from models import SaveDatasetRequest
from response import success_response
from dependencies import get_current_user

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = Path("./storage/datasets")
STORAGE_ROOT = STORAGE_PATH.resolve()
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


def _safe_path_component(value: str, field_name: str) -> str:
    """Only accept a single filename component to keep writes inside storage."""
    component = (value or "").strip()
    path = Path(component)
    if not component or path.is_absolute() or len(path.parts) != 1 or path.parts[0] in {".", ".."}:
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return component


def _storage_child(*parts: str) -> Path:
    candidate = STORAGE_ROOT.joinpath(*parts).resolve()
    if STORAGE_ROOT != candidate and STORAGE_ROOT not in candidate.parents:
        raise HTTPException(status_code=400, detail="保存路径非法")
    return candidate


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user=Depends(get_current_user),
):
    try:
        task_id = _safe_path_component(req.task_id, "task_id")
        folder_name = f"user_{current_user.id}_{task_id}_{int(time.time())}"
        save_dir = _storage_child(folder_name)
        save_dir.mkdir()

        for cloud in req.data:
            cloud_name = _safe_path_component(cloud.cloud_name, "cloud_name")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _storage_child(folder_name, label_filename)

            with file_path.open("w") as f:
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
