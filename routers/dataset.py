# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
import os
import re
import time
import uuid
from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_PATH = os.path.abspath("./storage/datasets")
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)

_SAFE_PATH_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")

def _safe_path_component(value: str, fallback: str) -> str:
    component = os.path.basename(str(value or "").strip())
    component = _SAFE_PATH_COMPONENT_RE.sub("_", component).strip("._")
    return component or fallback

def _storage_path(*parts: str) -> str:
    path = os.path.abspath(os.path.join(STORAGE_PATH, *parts))
    if os.path.commonpath([STORAGE_PATH, path]) != STORAGE_PATH:
        raise HTTPException(status_code=400, detail="保存路径非法")
    return path

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user = Depends(get_current_user)
):
    try:
        task_id = _safe_path_component(req.task_id, "task")
        folder_name = f"{task_id}_{current_user.id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        save_dir = _storage_path(folder_name)
        os.makedirs(save_dir)

        for cloud in req.data:
            cloud_name = _safe_path_component(cloud.cloud_name, "cloud")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _storage_path(folder_name, label_filename)
            
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