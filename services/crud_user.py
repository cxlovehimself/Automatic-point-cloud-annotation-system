# services/crud_user.py
from sqlmodel import Session, select
from datetime import datetime
from typing import Optional
import models
import security


def is_subscription_active(db_user: models.User, now: Optional[datetime] = None) -> bool:
    """Return whether a user has an unexpired subscription."""
    if not db_user.is_subscribed:
        return False

    current_time = now or datetime.now()
    if db_user.vip_expire_time and db_user.vip_expire_time <= current_time:
        return False

    return True


def refresh_subscription_status(
    db: Session,
    db_user: models.User,
    now: Optional[datetime] = None,
) -> models.User:
    """Persistently clear stale subscription flags once the VIP period expires."""
    if db_user.is_subscribed and not is_subscription_active(db_user, now=now):
        db_user.is_subscribed = False
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    return db_user


def get_user_by_email(db: Session, email: str):
    """通过邮箱查询用户"""
    statement = select(models.User).where(models.User.email == email)
    return db.exec(statement).first()


def create_user(db: Session, user: models.UserCreate):
    """创建新用户并加密密码入库"""
    hashed_password = security.get_password_hash(user.password)

    new_user = models.User.model_validate(
        user,
        update={"password_hash": hashed_password},
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def update_last_login(db: Session, db_user: models.User):
    """更新用户的最后登录时间"""
    db_user.last_login = datetime.utcnow()
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_password(db: Session, db_user: any, new_password: str):
    """更新用户密码"""
    hashed_password = security.get_password_hash(new_password)

    db_user.password_hash = hashed_password
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user
