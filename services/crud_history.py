from sqlmodel import Session, select  # 💡 引入 SQLModel 的核心组件
from models import ProcessingHistory   # 💡 确保引入的是 SQLModel 版本的模型
from datetime import datetime

def get_user_history(db: Session, user_id: int):
    """
    根据 user_id 查询历史记录，按创建时间倒序排列
    """
    # 💡 变化：SQLModel 推荐使用 select() 语法，更接近原生 SQL 逻辑
    statement = select(ProcessingHistory)\
                .where(ProcessingHistory.user_id == user_id)\
                .order_by(ProcessingHistory.created_at.desc())
    
    return db.exec(statement).all()  # 注意：db.query().all() 变成了 db.exec().all()

def update_history_remark(db: Session, history_id: int, user_id: int, new_remark: str):
    """修改备注（带权限校验）"""
    # 💡 同时也演示一下多条件的 select 语法
    statement = select(ProcessingHistory).where(
        ProcessingHistory.id == history_id, 
        ProcessingHistory.user_id == user_id
    )
    record = db.exec(statement).first()
    
    if record:
        record.remark = new_remark
        db.add(record)  # 显式告知会话对象已变更
        db.commit()
        db.refresh(record)
    return record

def delete_user_history(db: Session, history_id: int, user_id: int):
    """删除记录（带权限校验）"""
    statement = select(ProcessingHistory).where(
        ProcessingHistory.id == history_id, 
        ProcessingHistory.user_id == user_id
    )
    record = db.exec(statement).first()
    
    if record:
        db.delete(record)
        db.commit()
        return True
    return False

def create_history_record(
    db: Session, 
    user_id: int, 
    original_filename: str, 
    scene_type: str, 
    result_url: str
):
    """创建新记录"""
    # 💡 变化：SQLModel 的模型本身就是 Pydantic 模型，
    # 我们可以像以前一样直接实例化，它既是表数据也是验证后的数据。
    new_record = ProcessingHistory(
        user_id=user_id,
        original_filename=original_filename,
        scene_type=scene_type,
        result_url=result_url
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    return new_record