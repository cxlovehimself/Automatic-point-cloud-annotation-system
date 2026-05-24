# routers/dataset.py
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import os
import time
from models import SaveDatasetRequest
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
from dependencies import get_current_user
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_PATH = "./storage/datasets"
STORAGE_ROOT = Path(STORAGE_PATH).resolve()
if not os.path.exists(STORAGE_ROOT):
    os.makedirs(STORAGE_ROOT)

def _safe_path_segment(value: str, field_name: str) -> str:
    """Keep user-controlled names as filenames, never as path fragments."""
    name = os.path.basename(str(value).replace("\\", "/").strip())
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail=f"{field_name} 不合法")
    return name

def _ensure_within_storage(path: Path, root: Path = STORAGE_ROOT) -> Path:
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise HTTPException(status_code=400, detail="保存路径不合法")
    return resolved

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user = Depends(get_current_user)
):
    try:
        task_id = _safe_path_segment(req.task_id, "task_id")
        folder_name = f"{task_id}_{int(time.time())}"
        save_dir = _ensure_within_storage(STORAGE_ROOT / folder_name)
        os.makedirs(save_dir)

        for cloud in req.data:
            cloud_name = _safe_path_segment(cloud.cloud_name, "cloud_name")
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _ensure_within_storage(save_dir / label_filename, save_dir)
            
            with open(file_path, "w") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        # 💡 使用统一返回体，优雅到极致！
        return success_response(
            message="数据集云端保存成功！", 
            data={"path": str(save_dir)}
        )

    except HTTPException:
        raise
    except Exception as e:
        # 如果出错了，抛出 500 异常
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
