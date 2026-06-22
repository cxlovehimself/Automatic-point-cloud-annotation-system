import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine
import models
from routers import  auth, dataset, task, history
from routers import payment
from runtime_paths import OUTPUT_DIR, ensure_runtime_directories

# 引入路由模块

# 引入 AI 引擎
from services.ai_engine import ai_engine
from database import init_db

logger = logging.getLogger(__name__)


# 定义 FastAPI 生命周期 (随服务器启动加载模型)
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    
    # 1. 室内模型配置 (S3DIS)
    indoor_yaml = "./configs/indoor.yml"
    indoor_ckpt = "./ckpt_00300.pth"
    
    # 2. 室外模型配置 (SemanticKITTI)；若权重缺失，引擎会跳过室外模型，不影响室内模型
    outdoor_yaml = "./configs/outdoor.yml"
    outdoor_ckpt = "./randlanet_semantickitti_202201071330utc.pth"
    
    try:
        # 传入 4 个参数，同时初始化双引擎
        ai_engine.initialize(
            indoor_yaml=indoor_yaml, 
            indoor_ckpt=indoor_ckpt, 
            outdoor_yaml=outdoor_yaml, 
            outdoor_ckpt=outdoor_ckpt
        )
    except Exception:
        logger.exception("AI 引擎加载失败")
    yield

# 实例化应用并注入生命周期
app = FastAPI(title="PointCloud AI Backend", lifespan=lifespan)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()
ensure_runtime_directories()
# 注册核心路由
app.include_router(auth.router)
app.include_router(task.router)
app.include_router(history.router)
app.include_router(payment.router)
app.include_router(dataset.router)
# 挂载静态文件，让前端能下载处理好的模型
app.mount("/api/models", StaticFiles(directory=str(OUTPUT_DIR)), name="models")

@app.get("/")
def read_root():
    return {"message": "点云标注系统后端（双引擎版）已启动"}