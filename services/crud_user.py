# services/crud_user.py
from sqlmodel import Session, select  # 💡 引入 SQLModel 的 select
from datetime import datetime
import models
# import schemas  <-- 💡 这行可以删了！因为 Schema 已经整合进 models 里了
import security

def get_user_by_email(db: Session, email: str):
    """通过邮箱查询用户"""
    # 💡 变化 1：用 select().where() 替代原生 SQLAlchemy 的 db.query().filter()
    statement = select(models.User).where(models.User.email == email)
    return db.exec(statement).first()  # 注意这里变成了 db.exec()

def create_user(db: Session, user: models.UserCreate): # 💡 注意类型提示换成了 models.UserCreate
    """创建新用户并加密密码入库"""
    hashed_password = security.get_password_hash(user.password)
    
    # 💡 变化 2 (神级特性)：直接把前端传来的 Pydantic 模型，无缝转换成数据库模型！
    # update 参数会顺手把加密后的密码塞进去，同时自动丢弃明文密码
    new_user = models.User.model_validate(
        user, 
        update={"password_hash": hashed_password}
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update_last_login(db: Session, db_user: models.User):
    """更新用户的最后登录时间"""
    db_user.last_login = datetime.utcnow()
    db.add(db_user)  # 建议加上这行，显式告诉会话这个对象被修改了
    db.commit()
    db.refresh(db_user)
    return db_user
def update_password(db: Session, db_user: any, new_password: str):
    """
    服务层：专职负责给用户更新密码
    包含：生成新 Hash、更新对象、提交数据库
    """
    # 1. 生成新密码的 Hash
    hashed_password = security.get_password_hash(new_password)
    
    # 2. 更新到数据库对象并提交
    db_user.password_hash = hashed_password
    db.add(db_user)
    db.commit()
    db.refresh(db_user) # 刷新一下状态以防万一
    
    return db_user