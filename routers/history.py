from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session  # 💡 替换为 SQLModel 的 Session
from services import crud_history
from response import success_response
from dependencies import get_current_user, get_db 
import models  # 💡 直接引入 models，彻底告别 schemas！

router = APIRouter(prefix="/api/history", tags=["历史记录管理"])

# 📖 查 (Read) - 获取当前用户的所有历史记录
# 💡 优化：去掉了 async，因为 pymysql 是同步驱动，用普通 def 在 FastAPI 里性能反而更高
@router.get("/list")
def get_history(
    page: int = Query(1, ge=1, description="当前页码"),       # 💡 接收前端传的 page
    size: int = Query(10, ge=1, le=100, description="每页条数"), # 💡 接收前端传的 size
    user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    
    # 1. 调用 Service 层，同时拿到总条数和当前页的数据
    total, records = crud_history.get_user_history(db=db, user_id=user.id, page=page, size=size)
    
    # 2. 依然极其丝滑的数据序列化
    items = [
        models.HistoryResponse.model_validate(record).model_dump(mode='json') 
        for record in records
    ]
    
    # 3. 💡 组装成分页标准的结构，完美配合你前端写的 res.items 和 res.total
    data = {
        "total": total,               # 总条数
        "page": page,                 # 当前页
        "size": size,                 # 每页大小
        "total_pages": (total + size - 1) // size, # 计算出总页数
        "items": items                # 真实的数据数组
    }
    
    return success_response(
        message="获取历史记录成功",
        data=data
    )

# 🗑️ 删 (Delete) - 删除历史记录
@router.delete("/{history_id}")
async def delete_history(history_id: int, user = Depends(get_current_user), db = Depends(get_db)):
    is_deleted = crud_history.delete_user_history(db=db, history_id=history_id, user_id=user.id)
    
    if not is_deleted:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")
        
    return success_response(message="历史记录已成功删除")