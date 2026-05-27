# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
import os
import json
import time
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

STORAGE_PATH = "./storage/datasets"
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)


@router.post("/save")
async def save_annotated_dataset(req: SaveDatasetRequest):
    try:
        folder_name = f"{req.task_id}_{int(time.time())}"
        save_dir = os.path.join(STORAGE_PATH, folder_name)
        os.makedirs(save_dir)

        for cloud in req.data:
            label_filename = f"{cloud.cloud_name}_labels.txt"
            file_path = os.path.join(save_dir, label_filename)

            with open(file_path, "w") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！",
            data={"path": save_dir},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
