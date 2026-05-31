from datetime import datetime, timedelta
from types import SimpleNamespace

from services import crud_user


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        self.refreshed.append(item)


def make_user(is_subscribed, vip_expire_time):
    return SimpleNamespace(
        is_subscribed=is_subscribed,
        vip_expire_time=vip_expire_time,
    )


def test_refresh_subscription_status_clears_expired_flag():
    now = datetime(2026, 5, 31, 11, 0, 0)
    db = FakeDb()
    user = make_user(True, now - timedelta(seconds=1))

    refreshed = crud_user.refresh_subscription_status(db, user, now=now)

    assert refreshed is user
    assert user.is_subscribed is False
    assert db.added == [user]
    assert db.commits == 1
    assert db.refreshed == [user]
    assert crud_user.is_subscription_active(user, now=now) is False


def test_refresh_subscription_status_keeps_active_subscription():
    now = datetime(2026, 5, 31, 11, 0, 0)
    db = FakeDb()
    user = make_user(True, now + timedelta(days=1))

    refreshed = crud_user.refresh_subscription_status(db, user, now=now)

    assert refreshed is user
    assert user.is_subscribed is True
    assert db.added == []
    assert db.commits == 0
    assert db.refreshed == []
    assert crud_user.is_subscription_active(user, now=now) is True
