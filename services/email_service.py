# services/email_service.py
import logging
import os
import random
import smtplib
import time
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Tuple

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
DEFAULT_FROM_NAME = "CloudLabel Pro"

# 验证码内存缓存 (放在 Service 层)
OTP_STORE = {}


def send_html_email(receiver_email: str, subject: str, html_body: str) -> bool:
    """通过 SMTP 发送 HTML 邮件（QQ 邮箱）。"""
    sender = os.getenv("SMTP_SENDER")
    password = os.getenv("SMTP_PASSWORD")

    if not sender or not password:
        logger.warning("邮件未发送: 未配置 SMTP_SENDER 或 SMTP_PASSWORD")
        return False

    message = MIMEText(html_body, "html", "utf-8")
    message["From"] = formataddr((DEFAULT_FROM_NAME, sender))
    message["To"] = receiver_email
    message["Subject"] = Header(subject, "utf-8")

    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        server.login(sender, password)
        server.sendmail(sender, [receiver_email], message.as_string())
        server.quit()
        return True
    except Exception:
        logger.exception("SMTP 发送失败, receiver=%s", receiver_email)
        return False


def send_real_email(receiver_email: str, code: str) -> bool:
    """发送密码重置验证码邮件。"""
    mail_msg = f"""
    <h3>CloudLabel Pro 安全中心</h3>
    <p>您正在尝试修改/重置密码。您的验证码是：<strong style="color: #58a6ff; font-size: 20px;">{code}</strong></p>
    <p>验证码在 5 分钟内有效。如果不是您本人的操作，请忽略此邮件。</p>
    """
    return send_html_email(receiver_email, "【验证码】密码重置验证", mail_msg)


def generate_and_store_code(email: str) -> str:
    """生成 6 位验证码并存入缓存"""
    code = str(random.randint(100000, 999999))
    OTP_STORE[email] = {
        "code": code,
        "expire": time.time() + 300,
    }
    return code


def verify_code(email: str, code: str) -> Tuple[bool, str]:
    """校验验证码是否正确/过期"""
    record = OTP_STORE.get(email)
    if not record:
        return False, "验证码无效或未发送"
    if time.time() > record["expire"]:
        return False, "验证码已过期，请重新获取"
    if record["code"] != code:
        return False, "验证码错误"

    del OTP_STORE[email]
    return True, "校验通过"
