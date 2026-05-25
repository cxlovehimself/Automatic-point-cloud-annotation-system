import os
import re
import time
from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_PATH = os.path.join(BASE_DIR, "storage", "datasets")
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
MAX_CLOUDS_PER_SAVE = 100
MAX_POINTS_PER_CLOUD = 500_000

os.makedirs(STORAGE_PATH, exist_ok=True)


def _safe_name(value: str, field_name: str) -> str:
    raw_name = os.path.basename(str(value or "").strip())
    safe_name = SAFE_NAME_RE.sub("_", raw_name).strip("._")
    if not safe_name:
        raise HTTPException(status_code=400, detail=f"{field_name} 不能为空或包含非法路径")
    return safe_name[:120]


def _ensure_under_storage(path: str) -> str:
    storage_root = os.path.realpath(STORAGE_PATH)
    target_path = os.path.realpath(path)
    if os.path.commonpath([storage_root, target_path]) != storage_root:
        raise HTTPException(status_code=400, detail="保存路径非法")
    return target_path

@router.post("/save")
async def save_annotated_dataset(req: SaveDatasetRequest, current_user = Depends(get_current_user)):
    try:
        if len(req.data) > MAX_CLOUDS_PER_SAVE:
            raise HTTPException(status_code=400, detail="单次保存的点云数量过多")

        safe_task_id = _safe_name(req.task_id, "task_id")
        folder_name = f"{safe_task_id}_{current_user.id}_{int(time.time())}"
        save_dir = _ensure_under_storage(os.path.join(STORAGE_PATH, folder_name))
        os.makedirs(save_dir)

        for cloud in req.data:
            if len(cloud.points_data) > MAX_POINTS_PER_CLOUD:
                raise HTTPException(status_code=400, detail="单个点云包含的点数过多")

            safe_cloud_name = _safe_name(cloud.cloud_name, "cloud_name")
            label_filename = f"{safe_cloud_name}_labels.txt"
            file_path = _ensure_under_storage(os.path.join(save_dir, label_filename))
            
            with open(file_path, "w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    if len(p) < 4:
                        raise HTTPException(status_code=400, detail="点数据格式错误")
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        # 💡 使用统一返回体，优雅到极致！
        return success_response(
            message="数据集云端保存成功！", 
            data={"path": save_dir}
        )

    except HTTPException:
        raise
    except Exception as e:
        # 如果出错了，抛出 500 异常
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")