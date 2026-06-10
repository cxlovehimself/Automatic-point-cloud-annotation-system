import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = Path("./storage/datasets")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_path_component(value: str, fallback: str) -> str:
    cleaned = _SAFE_COMPONENT_RE.sub("_", Path(value).name).strip("._")
    return cleaned or fallback


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    _current_user=Depends(get_current_user),
):
    try:
        safe_task_id = _safe_path_component(req.task_id, "task")
        folder_name = f"{safe_task_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        save_dir = STORAGE_PATH / folder_name
        save_dir.mkdir()

        for cloud in req.data:
            safe_cloud_name = _safe_path_component(cloud.cloud_name, "cloud")
            file_path = save_dir / f"{safe_cloud_name}_labels.txt"

            with file_path.open("w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！",
            data={"path": str(save_dir)},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
