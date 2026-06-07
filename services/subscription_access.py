from datetime import datetime
from typing import Optional


TRIAL_DAYS = 14


def has_active_subscription(user, now: Optional[datetime] = None) -> bool:
    """Return whether a paid subscription is currently valid."""
    if not getattr(user, "is_subscribed", False):
        return False

    vip_expire_time = getattr(user, "vip_expire_time", None)
    if vip_expire_time is None:
        return True

    return vip_expire_time > (now or datetime.now())


def has_trial_access(user, now: Optional[datetime] = None) -> bool:
    register_time = getattr(user, "register_time", None)
    if not register_time:
        return True

    return ((now or datetime.now()) - register_time).days <= TRIAL_DAYS


def can_predict_pointcloud(user, now: Optional[datetime] = None) -> bool:
    current_time = now or datetime.now()
    return has_active_subscription(user, current_time) or has_trial_access(user, current_time)
