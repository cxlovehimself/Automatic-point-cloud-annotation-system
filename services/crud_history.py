from sqlmodel import Session, func, select  # 💡 引入 SQLModel 的核心组件
from models import ProcessingHistory   # 💡 确保引入的是 SQLModel 版本的模型
from datetime import datetime

def get_user_history(db: Session, user_id: int, page: int = 1, size: int = 10):
    """
    根据 user_id 查询历史记录，支持分页，按创建时间倒序排列
    """
    # 1. 先统计该用户一共有多少条历史记录
    count_statement = select(func.count(ProcessingHistory.id)).where(ProcessingHistory.user_id == user_id)
    total = db.exec(count_statement).one()

    # 2. 计算分页偏移量 (Skip)
    skip = (page - 1) * size

    # 3. 执行分页查询：加上 .offset() 和 .limit()
    statement = select(ProcessingHistory)\
                .where(ProcessingHistory.user_id == user_id)\
                .order_by(ProcessingHistory.created_at.desc())\
                .offset(skip)\
                .limit(size)
    
    records = db.exec(statement).all()
    
    # 将总数和分页后的数据一起返回
    return total, records

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