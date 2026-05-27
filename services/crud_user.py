# services/crud_user.py
from sqlmodel import Session, select
from datetime import datetime
import models
import security


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
