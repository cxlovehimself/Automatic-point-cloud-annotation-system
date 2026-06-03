from datetime import datetime
from typing import Optional


def has_active_subscription(user, now: Optional[datetime] = None) -> bool:
    """Return True only when a paid subscription has a future expiry time."""
    if not getattr(user, "is_subscribed", False):
        return False

    expire_time = getattr(user, "vip_expire_time", None)
    if expire_time is None:
        return False

    current_time = now
    if current_time is None:
        current_time = datetime.now(expire_time.tzinfo) if expire_time.tzinfo else datetime.now()

    return expire_time > current_time
