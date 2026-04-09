# routers/payment.py
from fastapi import APIRouter, Depends, Request,BackgroundTasks
from sqlmodel import Session,select  # 💡 修改 1：替换为 SQLModel 的 Session
from response import success_response
from dependencies import get_current_user, get_db
from services import payment_service 
from services.notification_service import send_vip_welcome_email
from models import Order

router = APIRouter(prefix="/api/payment", tags=["支付模块"])

# 💡 修改 2：去掉 async，提升同步数据库驱动的执行效率
@router.post("/create")
def create_payment(
    request: Request, # 💡 1. 注入 request，用来抓取动态域名
    user=Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """获取支付链接，并创建本地订单"""
    
    # 💡 2. 抓取当前后端的公网基础 URL (比如 https://my-alipay-test.loca.lt)
    base_url = str(request.base_url).rstrip('/')
    
    # 💡 3. 把 base_url 传给 service 层！
    pay_url, out_trade_no = payment_service.create_payment_order(
        db=db, 
        user_id=user.id, 
        amount="9.90",
        base_url=base_url # 👈 新增这个参数
    )
    
    return success_response(
        message="订单已生成，请前往支付", 
        data={"pay_url": pay_url, "out_trade_no": out_trade_no}
    )
@router.post("/callback")
async def alipay_callback(
    request: Request, 
    background_tasks: BackgroundTasks, # 💡 3. 注入后台任务对象
    db: Session = Depends(get_db)
):
    """支付宝异步回调验证"""
    body = await request.form() 
    data = dict(body)
    
    # 💡 4. 接收两个返回值
    is_success, user_email = payment_service.process_callback(db=db, data=data)
    
    if is_success:
        if user_email:
            background_tasks.add_task(send_vip_welcome_email, user_email)
        return "success" 
    else:
        return "fail"
    
@router.get("/status/{out_trade_no}")
def check_payment_status(out_trade_no: str, db: Session = Depends(get_db)):
    statement = select(Order).where(Order.out_trade_no == out_trade_no)
    order = db.exec(statement).first()
    
    if not order:
        return success_response(message="订单不存在", data={"status": "not_found"})
        
    return success_response(
        message="查询成功", 
        data={"status": order.status} # 这里会返回 "pending" 或 "paid"
    )    