# routers/dataset.py
from pathlib import Path
import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_ROOT = Path("storage/datasets").resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_path_component(value: str, field_name: str) -> str:
    component = SAFE_COMPONENT_RE.sub("_", Path(value).name.strip()).strip("._")
    if not component:
        raise HTTPException(status_code=400, detail=f"{field_name} 无效")
    return component[:100]


def _ensure_inside_storage(path: Path) -> Path:
    resolved = path.resolve()
    if STORAGE_ROOT not in (resolved, *resolved.parents):
        raise HTTPException(status_code=400, detail="保存路径无效")
    return resolved

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user=Depends(get_current_user)
):
    try:
        safe_task_id = _safe_path_component(req.task_id, "task_id")
        folder_name = f"{current_user.id}_{safe_task_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        save_dir = _ensure_inside_storage(STORAGE_ROOT / folder_name)
        save_dir.mkdir(parents=False, exist_ok=False)

        for cloud in req.data:
            safe_cloud_name = _safe_path_component(cloud.cloud_name, "cloud_name")
            file_path = _ensure_inside_storage(save_dir / f"{safe_cloud_name}_labels.txt")
            
            with open(file_path, "w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    if len(p) < 4:
                        raise HTTPException(status_code=400, detail="points_data 格式无效")
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
