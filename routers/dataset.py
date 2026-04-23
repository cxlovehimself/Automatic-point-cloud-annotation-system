# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import os
import json
import time
from models import SaveDatasetRequest,PointData
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
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

        # 💡 使用统一返回体，优雅到极致！
        return success_response(
            message="数据集云端保存成功！", 
            data={"path": save_dir}
        )

    except Exception as e:
        # 如果出错了，抛出 500 异常
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")