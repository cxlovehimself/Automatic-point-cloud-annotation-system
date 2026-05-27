from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from services import crud_history
from response import success_response
from dependencies import get_current_user, get_db
import models

router = APIRouter(prefix="/api/history", tags=["历史记录管理"])


# 查询：获取当前用户的所有历史记录（同步 def + pymysql 驱动）
@router.get("/list")
def get_history(
    page: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(10, ge=1, le=100, description="每页条数"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, records = crud_history.get_user_history(db=db, user_id=user.id, page=page, size=size)

    items = [
        models.HistoryResponse.model_validate(record).model_dump(mode="json")
        for record in records
    ]

    data = {
        "total": total,
        "page": page,
        "size": size,
        "total_pages": (total + size - 1) // size,
        "items": items,
    }

    return success_response(
        message="获取历史记录成功",
        data=data,
    )


# 删除：删除历史记录
@router.delete("/{history_id}")
async def delete_history(history_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    is_deleted = crud_history.delete_user_history(db=db, history_id=history_id, user_id=user.id)

    if not is_deleted:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")

    return success_response(message="历史记录已成功删除")
