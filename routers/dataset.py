# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import time

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response
from services.dataset_storage import resolve_dataset_path, safe_path_component

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = Path("./storage/datasets")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


@router.post("/save")
async def save_annotated_dataset(req: SaveDatasetRequest, current_user=Depends(get_current_user)):
    try:
        task_id = safe_path_component(req.task_id, "task_id")
        folder_name = f"user_{current_user.id}_{task_id}_{int(time.time())}"
        save_dir = resolve_dataset_path(STORAGE_PATH, folder_name)
        save_dir.mkdir()

        for cloud in req.data:
            cloud_name = safe_path_component(cloud.cloud_name, "cloud_name")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = resolve_dataset_path(STORAGE_PATH, folder_name, label_filename)

            with file_path.open("w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！",
            data={"path": str(STORAGE_PATH / folder_name)},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"保存失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
