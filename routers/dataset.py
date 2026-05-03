from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
import time
from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response  # 💡 直接引入你在 models.py 定义的 SaveDatasetRequest
router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 定义接收格式


# 保存路径设置
STORAGE_PATH = Path("./storage/datasets")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)

def _safe_path_component(value: str, field_name: str) -> str:
    """Reject path separators so request fields cannot escape STORAGE_PATH."""
    if value in {"", ".", ".."} or Path(value).name != value or "/" in value or "\\" in value:
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法路径字符")
    return value

@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user=Depends(get_current_user)
):
    try:
        safe_task_id = _safe_path_component(req.task_id, "task_id")
        folder_name = f"{safe_task_id}_{int(time.time())}"
        save_dir = STORAGE_PATH / folder_name
        save_dir.mkdir()

        for cloud in req.data:
            safe_cloud_name = _safe_path_component(cloud.cloud_name, "cloud_name")
            file_path = save_dir / f"{safe_cloud_name}_labels.txt"
            
            with open(file_path, "w", encoding="utf-8") as f:
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