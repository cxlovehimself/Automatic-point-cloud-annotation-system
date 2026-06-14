# services/payment_service.py
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from alipay import AliPay
from dotenv import load_dotenv
from sqlmodel import Session, select

from models import Order, User

load_dotenv()

logger = logging.getLogger(__name__)

APP_ID = (os.getenv("ALIPAY_APP_ID") or "").strip()
RETURN_URL = (os.getenv("ALIPAY_RETURN_URL") or "").strip()
NOTIFY_URL = (os.getenv("ALIPAY_NOTIFY_URL") or "").strip()
SELLER_ID = (os.getenv("ALIPAY_SELLER_ID") or "").strip()
SELLER_EMAIL = (os.getenv("ALIPAY_SELLER_EMAIL") or "").strip()

# 从项目根目录下的 certs 读取支付宝密钥
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "certs", "alipay_private_key.pem")
PUBLIC_KEY_PATH = os.path.join(BASE_DIR, "certs", "alipay_public_key.pem")

try:
    with open(PRIVATE_KEY_PATH, "r") as f:
        APP_PRIVATE_KEY = f.read()
    with open(PUBLIC_KEY_PATH, "r") as f:
        ALIPAY_PUBLIC_KEY = f.read()
except FileNotFoundError:
    logger.warning(
        "找不到支付宝密钥文件，请确保 certs 目录下有 alipay_private_key.pem 与 alipay_public_key.pem"
    )
    APP_PRIVATE_KEY = ""
    ALIPAY_PUBLIC_KEY = ""

alipay = AliPay(
    appid=APP_ID,
    app_notify_url=None,
    app_private_key_string=APP_PRIVATE_KEY,
    alipay_public_key_string=ALIPAY_PUBLIC_KEY,
    sign_type="RSA2",
    debug=True,
)


def _build_notify_url(base_url: str = "") -> str:
    """Return the configured Alipay callback URL without trusting request hosts."""
    if not NOTIFY_URL:
        raise RuntimeError("ALIPAY_NOTIFY_URL 未配置，无法创建支付回调地址")
    return NOTIFY_URL


def _callback_identity_matches(data: dict) -> bool:
    if not APP_ID:
        logger.error("ALIPAY_APP_ID 未配置，拒绝处理支付宝回调")
        return False
    if data.get("app_id") != APP_ID:
        logger.warning("支付宝回调 app_id 不匹配: %s", data.get("app_id"))
        return False
    if SELLER_ID and data.get("seller_id") != SELLER_ID:
        logger.warning("支付宝回调 seller_id 不匹配: %s", data.get("seller_id"))
        return False
    if SELLER_EMAIL and data.get("seller_email") != SELLER_EMAIL:
        logger.warning("支付宝回调 seller_email 不匹配: %s", data.get("seller_email"))
        return False
    return True


def create_payment_order(db: Session, user_id: int, amount: str = "9.90", base_url: str = "") -> tuple:
    notify_url = _build_notify_url(base_url)
    random_str = uuid.uuid4().hex[:6]
    out_trade_no = f"ORDER_{int(time.time())}_{user_id}_{random_str}"

    new_order = Order(
        user_id=user_id,
        out_trade_no=out_trade_no,
        total_amount=amount,
        status="pending",
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    order_string = alipay.api_alipay_trade_page_pay(
        out_trade_no=out_trade_no,
        total_amount=amount,
        subject="PointCloud Annotator Pro 包月会员",
        return_url=RETURN_URL,
        notify_url=notify_url,
    )
    payurl = f"https://openapi-sandbox.dl.alipaydev.com/gateway.do?{order_string}"
    return payurl, out_trade_no


def process_callback(db: Session, data: dict) -> Tuple[bool, Optional[Tuple[str, str]]]:
    """处理支付宝异步回调。成功且首次完成支付时返回 (True, (email, 到期日))；已支付订单重复回调返回 (True, None)。"""
    signature = data.pop("sign", None)
    if not alipay.verify(data, signature):
        logger.warning("支付宝回调验签失败")
        return False, None

    if not _callback_identity_matches(data):
        return False, None

    if data.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        out_trade_no = data.get("out_trade_no")
        alipay_trade_no = data.get("trade_no")

        statement_order = select(Order).where(Order.out_trade_no == out_trade_no)
        order = db.exec(statement_order).first()
        if not order:
            logger.warning("支付宝回调订单不存在: %s", out_trade_no)
            return False, None

        if order.status != "pending":
            return True, None

        if float(data.get("total_amount", 0)) != float(order.total_amount):
            logger.error("订单金额校验失败(可能被篡改): %s", out_trade_no)
            return False, None

        order.status = "paid"
        order.alipay_trade_no = alipay_trade_no
        db.add(order)

        statement_user = select(User).where(User.id == order.user_id)
        user = db.exec(statement_user).first()

        if user:
            user.is_subscribed = True
            now = datetime.now()
            if not user.vip_expire_time or user.vip_expire_time < now:
                user.vip_expire_time = now + timedelta(days=30)
            else:
                user.vip_expire_time = user.vip_expire_time + timedelta(days=30)
            db.add(user)

        db.commit()

        if user:
            expire_str = (
                user.vip_expire_time.strftime("%Y-%m-%d") if user.vip_expire_time else ""
            )
            return True, (user.email, expire_str)
        return True, None

    return False, None
