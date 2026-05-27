# routers/payment.py
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlmodel import Session, select

from dependencies import get_current_user, get_db
from models import Order
from response import success_response
from services import payment_service
from services.notification_service import send_vip_welcome_email

router = APIRouter(prefix="/api/payment", tags=["支付模块"])


@router.post("/create")
def create_payment(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取支付链接，并创建本地订单"""
    base_url = str(request.base_url).rstrip("/")
    pay_url, out_trade_no = payment_service.create_payment_order(
        db=db,
        user_id=user.id,
        amount="9.90",
        base_url=base_url,
    )

    return success_response(
        message="订单已生成，请前往支付",
        data={"pay_url": pay_url, "out_trade_no": out_trade_no},
    )


@router.post("/callback")
async def alipay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """支付宝异步回调验证"""
    body = await request.form()
    data = dict(body)

    is_success, notify_payload = payment_service.process_callback(db=db, data=data)

    if is_success:
        if notify_payload:
            email, expire_str = notify_payload
            background_tasks.add_task(send_vip_welcome_email, email, expire_str)
        return "success"
    return "fail"


@router.get("/status/{out_trade_no}")
def check_payment_status(out_trade_no: str, db: Session = Depends(get_db)):
    statement = select(Order).where(Order.out_trade_no == out_trade_no)
    order = db.exec(statement).first()

    if not order:
        return success_response(message="订单不存在", data={"status": "not_found"})

    return success_response(
        message="查询成功",
        data={"status": order.status},
    )
