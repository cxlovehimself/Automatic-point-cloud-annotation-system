# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import os
import json
import re
import time
from dependencies import get_current_user
from models import SaveDatasetRequest,PointData
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_PATH = "./storage/datasets"
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)
STORAGE_ROOT = os.path.realpath(STORAGE_PATH)
UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")

def _safe_name(value: str, field_name: str) -> str:
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name}不能为空")
    name = UNSAFE_NAME_RE.sub("_", os.path.basename(value.strip())).strip("._")
    if not name:
        raise HTTPException(status_code=400, detail=f"{field_name}包含非法字符")
    return name[:128]

def _storage_path(*parts: str) -> str:
    path = os.path.realpath(os.path.join(STORAGE_ROOT, *parts))
    if os.path.commonpath([STORAGE_ROOT, path]) != STORAGE_ROOT:
        raise HTTPException(status_code=400, detail="保存路径非法")
    return path

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user = Depends(get_current_user)
):
    try:
        task_id = _safe_name(req.task_id, "task_id")
        folder_name = f"{task_id}_{current_user.id}_{int(time.time())}"
        save_dir = _storage_path(folder_name)
        os.makedirs(save_dir)

        for cloud in req.data:
            cloud_name = _safe_name(cloud.cloud_name, "cloud_name")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _storage_path(folder_name, label_filename)
            
            with open(file_path, "w") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        # 💡 使用统一返回体，优雅到极致！
        return success_response(
            message="数据集云端保存成功！", 
            data={"path": os.path.join(STORAGE_PATH, folder_name)}
        )

    except HTTPException:
        raise
    except Exception as e:
        # 如果出错了，抛出 500 异常
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")