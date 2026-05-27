# services/notification_service.py
from services import email_service


def send_vip_welcome_email(user_email: str, vip_expire_str: str) -> None:
    """支付成功后向用户发送会员开通欢迎邮件。"""
    html_body = f"""
    <h3>CloudLabel Pro</h3>
    <p>您好，</p>
    <p>您已成功开通 <strong>Point Cloud Annotator Pro 包月会员</strong>。</p>
    <p>当前会员到期时间：<strong>{vip_expire_str}</strong></p>
    <p>感谢您对本产品的支持。</p>
    """
    email_service.send_html_email(user_email, "会员开通成功", html_body)
