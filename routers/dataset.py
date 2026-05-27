import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models import SaveDatasetRequest
from response import success_response

router = APIRouter(prefix="/api/dataset", tags=["数据集管理"])

# 保存路径设置
STORAGE_PATH = Path("./storage/datasets")
MAX_CLOUDS_PER_SAVE = 20
MAX_POINTS_PER_CLOUD = 2_000_000
MAX_TOTAL_POINTS_PER_SAVE = 2_000_000

os.makedirs(STORAGE_PATH, exist_ok=True)


def _safe_path_component(value: str, field_name: str) -> str:
    component = Path(str(value)).name
    component = re.sub(r"[^\w.-]+", "_", component).strip("._")

    if not component:
        raise HTTPException(status_code=400, detail=f"{field_name} 无效")

    return component[:120]


def _validate_points(points_data: list, cloud_name: str) -> None:
    if len(points_data) > MAX_POINTS_PER_CLOUD:
        raise HTTPException(status_code=400, detail=f"{cloud_name} 点数超过上限")

    for point in points_data:
        if not isinstance(point, (list, tuple)) or len(point) < 4:
            raise HTTPException(status_code=400, detail=f"{cloud_name} 包含无效点数据")


@router.post("/save")
async def save_annotated_dataset(
    req: SaveDatasetRequest,
    current_user=Depends(get_current_user),
):
    try:
        if len(req.data) > MAX_CLOUDS_PER_SAVE:
            raise HTTPException(status_code=400, detail="单次保存的点云数量超过上限")

        total_points = sum(len(cloud.points_data) for cloud in req.data)
        if total_points > MAX_TOTAL_POINTS_PER_SAVE:
            raise HTTPException(status_code=400, detail="单次保存的点数超过上限")

        folder_name = f"{_safe_path_component(req.task_id, 'task_id')}_{int(time.time())}"
        save_dir = STORAGE_PATH / folder_name
        save_dir.mkdir(parents=False, exist_ok=False)

        for cloud in req.data:
            cloud_name = _safe_path_component(cloud.cloud_name, "cloud_name")
            _validate_points(cloud.points_data, cloud_name)

            label_filename = f"{cloud_name}_labels.txt"
            file_path = save_dir / label_filename

            with open(file_path, "w", encoding="utf-8") as f:
                for p in cloud.points_data:
                    f.write(f"{p[0]} {p[1]} {p[2]} {p[3]}\n")

        return success_response(
            message="数据集云端保存成功！", 
            data={"path": str(save_dir)}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
