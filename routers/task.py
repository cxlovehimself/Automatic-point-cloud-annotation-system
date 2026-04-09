import os
import time
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request # 💡 新增引入 Request
from sqlmodel import Session  # 💡 修改 1：替换为 SQLModel 的 Session

# 💡 引入你的依赖项、模型服务和自定义响应
from response import success_response
from services.ai_engine import ai_engine
from services import crud_history            
from dependencies import get_db, get_current_user  
import uuid  # 💡 新增：用于生成唯一标识符
from datetime import datetime
router = APIRouter(prefix="/api/task", tags=["点云处理模块"])

UPLOAD_DIR = "data/uploads"
OUTPUT_DIR = "data/outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 💡 这里的 async def 必须保留，因为下面用到了 await file.read()
@router.post("/predict")
async def predict_pointcloud(
    request: Request, # 动态获取域名
    file: UploadFile = File(...),
    scene_type: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user) 
):
    # ==========================================
    # 💡 核心新增：商业级权限校验防线 (拦截白嫖党)
    # 必须放在最前面，防止过期用户上传大文件撑爆硬盘！
    # ==========================================
    if not current_user.is_subscribed:
        # 获取用户的注册时间，计算白嫖了多少天
        register_date = current_user.register_time 
        if register_date:
            days_used = (datetime.now() - register_date).days
            if days_used > 14:
                raise HTTPException(
                    status_code=403, 
                    detail="您的 14 天免费试用期已结束，请前往个人中心升级 Pro 账户！"
                )

    # 引擎初始化检查
    if not ai_engine.is_loaded:
        raise HTTPException(status_code=503, detail="AI 引擎暂未完成初始化")

    if scene_type not in ["indoor", "outdoor", "auto"]:
        raise HTTPException(status_code=400, detail="不支持的 scene_type")

    # 获取用户原始文件名
    safe_filename = os.path.basename(file.filename)
    
    # 时间戳 + 8位短UUID，绝对防撞！
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S") 
    short_uuid = uuid.uuid4().hex[:8] 
    
    # 拼接出极其优雅且绝对安全的保存路径
    input_filename = f"input_{time_str}_{short_uuid}_{safe_filename}"
    output_filename = f"result_{time_str}_{short_uuid}.ply"
    
    # 💡 保底防线：确保文件夹存在 (别忘了之前加的这个防崩溃机制)
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
        print(f"文件保存异常: {e}")
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 2. 调用 AI 引擎推理
    try:
        start_time = time.time()
        metrics = ai_engine.process_pointcloud(input_path, output_path, scene_type)
        total_time = round(time.time() - start_time, 2)
        
        # 动态获取后端的基础 URL，再也不用担心写死 IP 了！
        base_url = str(request.base_url).rstrip('/')
        result_url = f"{base_url}/api/models/{output_filename}"

        # 确定最终场景类型
        actual_scene = metrics.get("scene_type_detected", scene_type)

        # 3. 将结果持久化到数据库
        crud_history.create_history_record(
            db=db,
            user_id=current_user.id,        
            original_filename=safe_filename,
            scene_type=actual_scene,
            result_url=result_url
        )

        # 4. 返回成功响应
        return success_response(
            message=f"{actual_scene} 场景点云分析完成",
            data={
                "result_url": result_url,
                "scene_type": actual_scene,
                "total_process_time_sec": total_time,
                "metrics": metrics
            }
        )
    except Exception as e:
        print(f"AI 推理报错: {e}")
        raise HTTPException(status_code=500, detail=f"推理过程出错: {str(e)}")