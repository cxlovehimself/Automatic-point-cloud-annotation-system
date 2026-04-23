# routers/auth.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session  # 💡 修改 1：替换为 SQLModel 的 Session
# 💡 你把具体的类直接请进来了
from models import UserCreate, UserLogin, ChangePasswordRequest, SendCodeRequest, ResetPasswordRequest
import security
from response import success_response
from database import get_db
from services import crud_user, email_service
from typing import Tuple   
router = APIRouter(prefix="/api/auth", tags=["认证模块"])

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)): # 💡 修改 3：类型改为 models.UserCreate
    # 1. 呼叫 Service 查重
    if crud_user.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    # 2. 呼叫 Service 创建用户
    crud_user.create_user(db=db, user=user)

    # 3. 返回响应
    return success_response(message="注册成功，请前往登录")


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)): # 💡 修改 4：类型改为 models.UserLogin
    # 1. 呼叫 Service 查询用户
    db_user = crud_user.get_user_by_email(db, email=user.email)
    expire_str = db_user.vip_expire_time.strftime("%Y-%m-%d") if db_user.vip_expire_time else None
    register_str = db_user.register_time.isoformat() if db_user.register_time else None
    
    # 2. 校验密码
    if not db_user or not security.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    # 3. 呼叫 Service 更新时间
    crud_user.update_last_login(db, db_user=db_user)

    # 4. 签发 JWT
    access_token = security.create_access_token(
        data={"sub": db_user.email, "role": db_user.role}
    )

    # 5. 返回响应
    return success_response(
        message="登录成功",
        data={
            "token": access_token,
            "email": db_user.email,
            "role": db_user.role,
            "is_subscribed": db_user.is_subscribed,
            # 💡 附加升级：如果你之前在 User 模型里加了 vip_expire_time，这里顺手返回去，前端会感激涕零！
            "vip_expire_time": expire_str,
            "register_time": register_str
            
        }
    )
# router.py

# ... 其他引入 ...

@router.get("/me")
def get_current_user_info(
    db: Session = Depends(get_db), 
    # 💡 这里依赖 security 里的方法，从 Header 的 Token 中解出 email
    current_user_email: str = Depends(security.get_current_user_email) 
):
    # 直接调用你刚才确认过的 Service 方法
    db_user = crud_user.get_user_by_email(db, email=current_user_email)
    expire_str = db_user.vip_expire_time.strftime("%Y-%m-%d") if db_user.vip_expire_time else None
    register_str = db_user.register_time.isoformat() if db_user.register_time else None
    
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 返回给前端
    return success_response(
        message="同步成功",
        data={
            "email": db_user.email,
            "role": db_user.role,
            "is_subscribed": db_user.is_subscribed,
            "vip_expire_time": expire_str,
            "register_time": register_str
        }
    )
@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user_email: str = Depends(security.get_current_user_email)
):
   
    db_user = crud_user.get_user_by_email(db, email=current_user_email)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not security.verify_password(req.old_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    
    crud_user.update_password(db, db_user=db_user, new_password=req.new_password)

    return success_response(message="密码修改成功，请重新登录")
@router.post("/send-reset-code")
def send_reset_code(req: SendCodeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Router 层：只负责 HTTP 请求与拦截"""
    # 1. 检查有没有这个人
    user = crud_user.get_user_by_email(db, email=req.email)
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册")

    # 2. 呼叫 Service 生成验证码
    code = email_service.generate_and_store_code(req.email)

    # 3. 把 Service 里的发送邮件函数，直接塞进后台任务！
    background_tasks.add_task(email_service.send_real_email, req.email, code)
    
    return success_response(message="验证码已发送，请注意查收")
@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    # 1. 呼叫 Service 进行纯粹的业务校验
    is_valid, error_msg = email_service.verify_code(req.email, req.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 2. 检查用户是否存在
    user = crud_user.get_user_by_email(db, email=req.email)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 3. 呼叫 user_service (crud_user) 更新密码
    crud_user.update_password(db, db_user=user, new_password=req.new_password)

    return success_response(message="密码重置成功，请重新登录")