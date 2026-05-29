import logging
import os
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request
from sqlmodel import Session
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from response import success_response, error_response
from dependencies import get_db, get_current_user
from worker import run_ai_segmentation_task, celery_app
from celery.result import AsyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task", tags=["点云处理模块"])

UPLOAD_DIR = "data/uploads"
OUTPUT_DIR = "data/outputs"
_TASK_OWNERS: Dict[str, int] = {}


def _remember_task_owner(task_id: str, user_id: int) -> None:
    _TASK_OWNERS[task_id] = user_id


def _result_owner_id(task_result: Any) -> Optional[int]:
    result = task_result.result
    if isinstance(result, dict):
        return result.get("_owner_user_id")
    return None


def _ensure_task_owner(task_id: str, task_result, user_id: int) -> None:
    owner_id = _TASK_OWNERS.get(task_id)
    if owner_id is None and task_result.state == "SUCCESS":
        owner_id = _result_owner_id(task_result)
    if owner_id != user_id:
        raise HTTPException(status_code=404, detail="任务不存在或无权查看")


def _public_task_result(task_result: Any) -> Any:
    result = task_result.result
    if isinstance(result, dict):
        public_result = result.copy()
        public_result.pop("_owner_user_id", None)
        return public_result
    return result

@router.post("/predict")
async def predict_pointcloud(
    request: Request, 
    file: UploadFile = File(...),
    scene_type: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user) 
):
    # 非会员：注册超过 14 天则禁止处理
    if not current_user.is_subscribed:
        register_date = current_user.register_time 
        if register_date:
            days_used = (datetime.now() - register_date).days
            if days_used > 14:
                raise HTTPException(
                    status_code=403, 
                    detail="您的 14 天免费试用期已结束，请前往个人中心升级 Pro 账户！"
                )

    if scene_type not in ["indoor", "outdoor", "auto"]:
        raise HTTPException(status_code=400, detail="不支持的 scene_type")

    safe_filename = os.path.basename(file.filename)
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S") 
    short_uuid = uuid.uuid4().hex[:8] 
    
    input_filename = f"input_{time_str}_{short_uuid}_{safe_filename}"
    output_filename = f"result_{time_str}_{short_uuid}.ply"
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_path = os.path.join(UPLOAD_DIR, input_filename)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # 1. 保存上传文件
    try:
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.exception("文件保存异常")
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 提前帮后厨把最终模型要展示的 URL 拼好
    base_url = str(request.base_url).rstrip('/')
    result_url = f"{base_url}/api/models/{output_filename}"

    task = run_ai_segmentation_task.delay(
        input_path=input_path,
        output_path=output_path,
        scene_type=scene_type,
        user_id=current_user.id,
        safe_filename=safe_filename,
        result_url=result_url
    )
    _remember_task_owner(task.id, current_user.id)

    return success_response(
        message="文件已上传，已成功加入 AI 算力集群排队队列！",
        data={
            "task_id": task.id,
            "status": "pending",
        },
    )


# 查询 Celery 任务进度
@router.get("/status/{task_id}")
def get_task_status(task_id: str, current_user=Depends(get_current_user)):
    task_result = AsyncResult(task_id, app=celery_app)
    _ensure_task_owner(task_id, task_result, current_user.id)
    
    if task_result.state == 'PENDING':
        return success_response(data={"status": "pending"}, message="前方拥挤，正在排队等待分配算力...")
        
    elif task_result.state == 'STARTED':
        return success_response(data={"status": "processing"}, message="AI 正在疯狂燃烧 GPU 运算中...")
        
    elif task_result.state == 'SUCCESS':
        # 这里拿到的 result，就是 worker.py 最后那个 return 的字典！
        # 包含了你心心念念的 actual_scene, total_time, metrics 等！
        return success_response(
            message="点云分析完成！",
            data={
                "status": "success",
                "result": _public_task_result(task_result)
            }
        )
        
    elif task_result.state == 'FAILURE':
        return error_response(message=f"后台运算崩溃: {str(task_result.info)}")
        
    else:
        return success_response(data={"status": task_result.state})