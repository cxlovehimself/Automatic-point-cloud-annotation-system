# routers/auth.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session

from models import UserCreate, UserLogin, ChangePasswordRequest, SendCodeRequest, ResetPasswordRequest
import security
from response import success_response
from database import get_db
from services import crud_user, email_service

router = APIRouter(prefix="/api/auth", tags=["认证模块"])


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if crud_user.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    crud_user.create_user(db=db, user=user)

    return success_response(message="注册成功，请前往登录")


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = crud_user.get_user_by_email(db, email=user.email)
    if not db_user or not security.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    expire_str = db_user.vip_expire_time.strftime("%Y-%m-%d") if db_user.vip_expire_time else None
    register_str = db_user.register_time.isoformat() if db_user.register_time else None

    crud_user.update_last_login(db, db_user=db_user)

    access_token = security.create_access_token(
        data={"sub": db_user.email, "role": db_user.role}
    )

    return success_response(
        message="登录成功",
        data={
            "token": access_token,
            "email": db_user.email,
            "role": db_user.role,
            "is_subscribed": db_user.is_subscribed,
            "vip_expire_time": expire_str,
            "register_time": register_str,
        },
    )


@router.get("/me")
def get_current_user_info(
    db: Session = Depends(get_db),
    current_user_email: str = Depends(security.get_current_user_email),
):
    db_user = crud_user.get_user_by_email(db, email=current_user_email)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    expire_str = db_user.vip_expire_time.strftime("%Y-%m-%d") if db_user.vip_expire_time else None
    register_str = db_user.register_time.isoformat() if db_user.register_time else None

    return success_response(
        message="同步成功",
        data={
            "email": db_user.email,
            "role": db_user.role,
            "is_subscribed": db_user.is_subscribed,
            "vip_expire_time": expire_str,
            "register_time": register_str,
        },
    )


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user_email: str = Depends(security.get_current_user_email),
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
    user = crud_user.get_user_by_email(db, email=req.email)
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册")

    code = email_service.generate_and_store_code(req.email)

    background_tasks.add_task(email_service.send_real_email, req.email, code)

    return success_response(message="验证码已发送，请注意查收")


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    is_valid, error_msg = email_service.verify_code(req.email, req.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    user = crud_user.get_user_by_email(db, email=req.email)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    crud_user.update_password(db, db_user=user, new_password=req.new_password)

    return success_response(message="密码重置成功，请重新登录")
