# routers/dataset.py
from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_PATH = Path("./storage/datasets").resolve()
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


def _safe_path_component(value: str, field_name: str) -> str:
    component = value.strip()
    if (
        not component
        or component in {".", ".."}
        or "/" in component
        or "\\" in component
        or "\x00" in component
    ):
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return component


def _ensure_within_storage(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(STORAGE_PATH)
    except ValueError:
        raise HTTPException(status_code=400, detail="保存路径非法")
    return resolved

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    _current_user = Depends(get_current_user),
):
    try:
        task_id = _safe_path_component(req.task_id, "task_id")
        safe_cloud_names = [
            _safe_path_component(cloud.cloud_name, "cloud_name")
            for cloud in req.data
        ]
        if len(set(safe_cloud_names)) != len(safe_cloud_names):
            raise HTTPException(status_code=400, detail="cloud_name 不能重复")

        folder_name = f"{task_id}_{int(time.time())}"
        save_dir = _ensure_within_storage(STORAGE_PATH / folder_name)
        save_dir.mkdir()

        for cloud, cloud_name in zip(req.data, safe_cloud_names):
            label_filename = f"{cloud_name}_labels.txt"
            file_path = _ensure_within_storage(save_dir / label_filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        # 💡 使用统一返回体，优雅到极致！
        return success_response(
            message="数据集云端保存成功！", 
            data={"path": str(save_dir)}
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        # 如果出错了，抛出 500 异常
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")