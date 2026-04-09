# services/payment_service.py
from alipay import AliPay
from sqlmodel import Session, select  # 💡 替换：引入 SQLModel 的 select
from models import Order, User
import uuid 
import time
from datetime import datetime, timedelta

import os
from dotenv import load_dotenv
# ... 其他导包保持不变 ...

load_dotenv()

# 从环境变量读取
APP_ID = os.getenv("ALIPAY_APP_ID")
RETURN_URL = os.getenv("ALIPAY_RETURN_URL")
NOTIFY_URL = os.getenv("ALIPAY_NOTIFY_URL")
# ==========================================
# 💡 核心升级：动态读取本地的 .pem 证书文件
# ==========================================
# 获取当前文件所在目录的上一级目录（即项目根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 拼接出证书的绝对路径
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "certs", "alipay_private_key.pem")
PUBLIC_KEY_PATH = os.path.join(BASE_DIR, "certs", "alipay_public_key.pem")

# 读取文件内容
try:
    with open(PRIVATE_KEY_PATH, "r") as f:
        APP_PRIVATE_KEY = f.read()
    with open(PUBLIC_KEY_PATH, "r") as f:
        ALIPAY_PUBLIC_KEY = f.read()
except FileNotFoundError:
    print("⚠️ 警告：找不到支付宝密钥文件，请确保 certs 目录下有对应的 .pem 文件！")
    APP_PRIVATE_KEY = ""
    ALIPAY_PUBLIC_KEY = ""

alipay = AliPay(
    appid=APP_ID,
    app_notify_url=None,
    app_private_key_string=APP_PRIVATE_KEY,
    alipay_public_key_string=ALIPAY_PUBLIC_KEY,
    sign_type="RSA2",
    debug=True  
)

def create_payment_order(db: Session, user_id: int, amount: str = "9.90", base_url: str = "") -> str:
    # 生成唯一订单号
    random_str = uuid.uuid4().hex[:6] 
    out_trade_no = f"ORDER_{int(time.time())}_{user_id}_{random_str}"
    
    # 创建订单
    new_order = Order(
        user_id=user_id,
        out_trade_no=out_trade_no,
        total_amount=amount, 
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # ==========================================
    # 💡 核心升级：在 Service 层拼接出绝对准确的动态回调地址！
    # ==========================================
    dynamic_notify_url = f"{base_url}/api/payment/callback"
    print(f"👉 本次发给支付宝的回调地址是: {dynamic_notify_url}")

    # 去支付宝要链接
    order_string = alipay.api_alipay_trade_page_pay(
        out_trade_no=out_trade_no,
        total_amount=amount,
        subject="PointCloud Annotator Pro 包月会员",
        return_url=RETURN_URL, 
        # 💡 2. 替换掉死板的 NOTIFY_URL，用我们刚刚动态生成的！
        notify_url=dynamic_notify_url 
    )
    payurl = f"https://openapi-sandbox.dl.alipaydev.com/gateway.do?{order_string}"
    print(f"💡 生成的支付链接: {payurl}")
    return payurl, out_trade_no


def process_callback(db: Session, data: dict) -> bool:
    """处理支付宝回调"""
    signature = data.pop("sign", None)
    if not alipay.verify(data, signature):
        return False  

    if data.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        out_trade_no = data.get("out_trade_no")
        alipay_trade_no = data.get("trade_no") 

        # 💡 升级 1：用 SQLModel 语法查询订单
        statement_order = select(Order).where(Order.out_trade_no == out_trade_no)
        order = db.exec(statement_order).first()
        
        if order and order.status == "pending":
            # 金额防篡改校验
            if float(data.get("total_amount", 0)) != float(order.total_amount):
                print(f"⚠️ 严重警告：订单 {out_trade_no} 金额被篡改！")
                return False 

            # 更新订单状态
            order.status = "paid"
            order.alipay_trade_no = alipay_trade_no
            db.add(order) # 显式告诉 SQLModel 这个对象脏了(被修改了)
            
            # 💡 升级 2：用 SQLModel 语法查询用户
            statement_user = select(User).where(User.id == order.user_id)
            user = db.exec(statement_user).first()
            
            if user:
                user.is_subscribed = True  # 💡 你的大一统模型里改成了 bool，所以这里用 True
                
                # 续费逻辑
                now = datetime.now()
                if not user.vip_expire_time or user.vip_expire_time < now:
                    user.vip_expire_time = now + timedelta(days=30)
                else:
                    user.vip_expire_time = user.vip_expire_time + timedelta(days=30)
                db.add(user) # 显式加入会话
                
            db.commit() # 一次性提交订单和用户的修改
        return True, user.email if user else None
        
    # 💡 修改这里：失败时，返回 False 和 None
    return False, None