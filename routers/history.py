from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session  # 💡 替换为 SQLModel 的 Session
from services import crud_history
from response import success_response
from dependencies import get_current_user, get_db 
import models  # 💡 直接引入 models，彻底告别 schemas！

router = APIRouter(prefix="/api/history", tags=["历史记录管理"])

# 📖 查 (Read) - 获取当前用户的所有历史记录
# 💡 优化：去掉了 async，因为 pymysql 是同步驱动，用普通 def 在 FastAPI 里性能反而更高
@router.get("/")
def get_history(user = Depends(get_current_user), db: Session = Depends(get_db)):
    
    # 1. 调用 Service 层拿数据，Router 层一行 SQL 都不写
    records = crud_history.get_user_history(db=db, user_id=user.id)
    
    # 2. 极其丝滑的数据序列化：直接使用 models.HistoryResponse 进行过滤和转换
    data = [
        models.HistoryResponse.model_validate(record).model_dump(mode='json') 
        for record in records
    ]
    
    return success_response(
        message="获取历史记录成功",
        data=data
    )

# ✏️ 改 (Update) - 修改备注
@router.put("/{history_id}")
async def update_history(history_id: int, remark: str, user = Depends(get_current_user), db = Depends(get_db)):
    # UPDATE processing_history SET remark = remark WHERE id = history_id AND user_id = user.id
    pass

# 🗑️ 删 (Delete) - 删除历史记录
@router.delete("/{history_id}")
async def delete_history(history_id: int, user = Depends(get_current_user), db = Depends(get_db)):
    # DELETE FROM processing_history WHERE id = history_id AND user_id = user.id
    is_deleted = crud_history.delete_user_history(db=db, history_id=history_id, user_id=user.id)
    
    # 2. 如果返回 False，说明记录不存在，或者这个记录根本不是当前用户的！
    if not is_deleted:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")
        
    # 3. 成功删除
    return success_response(message="历史记录已成功删除")
    pass