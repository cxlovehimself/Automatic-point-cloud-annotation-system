from sqlmodel import Session, func, select
from models import ProcessingHistory


def get_user_history(db: Session, user_id: int, page: int = 1, size: int = 10):
    """
    根据 user_id 查询历史记录，支持分页，按创建时间倒序排列
    """
    count_statement = select(func.count(ProcessingHistory.id)).where(ProcessingHistory.user_id == user_id)
    total = db.exec(count_statement).one()

    skip = (page - 1) * size

    statement = (
        select(ProcessingHistory)
        .where(ProcessingHistory.user_id == user_id)
        .order_by(ProcessingHistory.created_at.desc())
        .offset(skip)
        .limit(size)
    )

    records = db.exec(statement).all()

    return total, records


def delete_user_history(db: Session, history_id: int, user_id: int):
    """删除记录（带权限校验）"""
    statement = select(ProcessingHistory).where(
        ProcessingHistory.id == history_id,
        ProcessingHistory.user_id == user_id,
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
    result_url: str,
):
    """创建新记录"""
    new_record = ProcessingHistory(
        user_id=user_id,
        original_filename=original_filename,
        scene_type=scene_type,
        result_url=result_url,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return new_record
