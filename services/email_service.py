# services/email_service.py
import os
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from typing import Tuple
from email.utils import formataddr  # 💡 新增这个工具
from email.mime.text import MIMEText
from email.header import Header
# ==========================================
# 💡 验证码内存缓存 (放进 Service 层保管)
# ==========================================
OTP_STORE = {}

def send_real_email(receiver_email: str, code: str):
    """底层服务：负责真正调用 SMTP 发送邮件"""
    sender = os.getenv("SMTP_SENDER")
    password = os.getenv("SMTP_PASSWORD")
    smtp_server = 'smtp.qq.com'

    if not sender or not password:
        print("⚠️ 邮件发送失败：没有配置 SMTP_SENDER 或 SMTP_PASSWORD")
        return False

    mail_msg = f"""
    <h3>CloudLabel Pro 安全中心</h3>
    <p>您正在尝试修改/重置密码。您的验证码是：<strong style="color: #58a6ff; font-size: 20px;">{code}</strong></p>
    <p>验证码在 5 分钟内有效。如果不是您本人的操作，请忽略此邮件。</p>
    """
    message = MIMEText(mail_msg, 'html', 'utf-8')
    message['From'] = formataddr(("CloudLabel Pro", sender))
    message['To'] = receiver_email # 收件人直接写邮箱字符串就行，千万别用 Header 包裹！
    message['Subject'] = Header('【验证码】密码重置验证', 'utf-8') # 标题如果有中文，继续保留 Header

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465)
        server.login(sender, password)
        server.sendmail(sender, [receiver_email], message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"邮件发送报错: {e}")
        return False

def generate_and_store_code(email: str) -> str:
    """业务服务：生成 6 位验证码并存入缓存"""
    code = str(random.randint(100000, 999999))
    OTP_STORE[email] = {
        "code": code,
        "expire": time.time() + 300 # 300秒有效期
    }
    return code

def verify_code(email: str, code: str) -> Tuple[bool, str]:
    """业务服务：校验验证码是否正确/过期"""
    record = OTP_STORE.get(email)
    if not record:
        return False, "验证码无效或未发送"
    if time.time() > record["expire"]:
        return False, "验证码已过期，请重新获取"
    if record["code"] != code:
        return False, "验证码错误"

    # 校验通过，销毁验证码
    del OTP_STORE[email]
    return True, "校验通过"