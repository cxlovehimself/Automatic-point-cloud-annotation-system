# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
import os
import re
import time
from pathlib import Path
from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = "./storage/datasets"
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)

SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_path_component(value: str, default: str) -> str:
    raw_name = str(value or "").replace("\\", "/")
    basename = os.path.basename(raw_name).strip()
    safe_name = SAFE_COMPONENT_RE.sub("_", basename).strip("._")
    return safe_name or default


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    _current_user=Depends(get_current_user),
):
    try:
        storage_root = Path(STORAGE_PATH).resolve()
        folder_name = f"{_safe_path_component(req.task_id, 'task')}_{int(time.time())}"
        save_dir = storage_root / folder_name
        save_dir.mkdir(parents=True, exist_ok=False)

        for cloud in req.data:
            label_filename = f"{_safe_path_component(cloud.cloud_name, 'cloud')}_labels.txt"
            file_path = (save_dir / label_filename).resolve()
            if os.path.commonpath([str(save_dir), str(file_path)]) != str(save_dir):
                raise HTTPException(status_code=400, detail="非法文件名")

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
