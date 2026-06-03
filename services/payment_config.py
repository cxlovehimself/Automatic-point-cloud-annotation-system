def get_alipay_notify_url(configured_notify_url: str) -> str:
    notify_url = (configured_notify_url or "").strip()
    if not notify_url:
        raise RuntimeError("ALIPAY_NOTIFY_URL 未配置，无法创建支付订单")
    return notify_url
