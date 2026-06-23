# routers/dataset.py
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
import time
from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_ROOT = Path("./storage/datasets").resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_path_component(value: str, field_name: str) -> str:
    component = str(value or "").strip()
    if (
        not component
        or component in {".", ".."}
        or "/" in component
        or "\\" in component
        or "\x00" in component
    ):
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return component


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    _current_user=Depends(get_current_user),
):
    try:
        task_id = _safe_path_component(req.task_id, "task_id")
        folder_name = f"{task_id}_{int(time.time())}"
        save_dir = (STORAGE_ROOT / folder_name).resolve()
        if save_dir.parent != STORAGE_ROOT:
            raise HTTPException(status_code=400, detail="task_id 包含非法路径字符")
        save_dir.mkdir()

        for cloud in req.data:
            cloud_name = _safe_path_component(cloud.cloud_name, "cloud_name")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = (save_dir / label_filename).resolve()
            if file_path.parent != save_dir:
                raise HTTPException(status_code=400, detail="cloud_name 包含非法路径字符")

            with open(file_path, "w") as f:
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
