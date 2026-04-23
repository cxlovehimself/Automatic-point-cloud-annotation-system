# worker.py
import os
import time
from celery import Celery
from sqlmodel import Session
from database import engine 
from services import crud_history
from services.ai_engine import ai_engine

celery_app = Celery(
    "ai_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)
celery_app.conf.update(task_track_started=True)

@celery_app.task(name="run_ai_segmentation")
def run_ai_segmentation_task(
    input_path: str, 
    output_path: str, 
    scene_type: str, 
    user_id: int, 
    safe_filename: str, 
    result_url: str
):
    start_time = time.time()
    
    try:
        if not ai_engine.is_loaded:
            ai_engine.initialize(
                indoor_yaml="./configs/indoor.yml",
                indoor_ckpt="./ckpt_00300.pth",
                outdoor_yaml="./configs/outdoor.yml",
                outdoor_ckpt="./randlanet_semantickitti_202201071330utc.pth"
            )
            
            if not ai_engine.is_loaded:
                raise RuntimeError("AI引擎依然未加载，请检查模型文件路径是否正确！")
        metrics = ai_engine.process_pointcloud(input_path, output_path, scene_type)
        actual_scene = metrics.get("scene_type_detected", scene_type)
        total_time = metrics.get("total_process_time_sec", round(time.time() - start_time, 2))
        
        # 2. 将结果写入历史记录数据库
        with Session(engine) as db:
            crud_history.create_history_record(
                db=db,
                user_id=user_id,
                original_filename=safe_filename,
                scene_type=actual_scene,
                result_url=result_url
            )
        
        # 3. 返回最终结果给 Redis 柜子，前端此时就能取到了！
        return {
            "result_url": result_url,
            "scene_type": actual_scene,
            "total_process_time_sec": total_time,
            "metrics": metrics
        }
        
    except Exception as e:
        print(f" [Celery Worker] 发生致命错误: {str(e)}")
        raise e