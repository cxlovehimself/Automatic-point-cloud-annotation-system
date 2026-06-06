import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("DB_URL", "sqlite://")

from models import UserLogin  # noqa: E402
from routers import auth  # noqa: E402


def test_login_missing_user_returns_401(monkeypatch):
    monkeypatch.setattr(
        auth.crud_user,
        "get_user_by_email",
        lambda db, email: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.login(UserLogin(email="missing@example.com", password="bad"), db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "邮箱或密码错误"


def test_get_current_user_info_missing_user_returns_404(monkeypatch):
    monkeypatch.setattr(
        auth.crud_user,
        "get_user_by_email",
        lambda db, email: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_info(db=object(), current_user_email="missing@example.com")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "用户不存在"


def test_login_existing_user_still_returns_profile(monkeypatch):
    db_user = SimpleNamespace(
        email="user@example.com",
        password_hash="hash",
        role="normal",
        is_subscribed=False,
        vip_expire_time=None,
        register_time=None,
    )

    monkeypatch.setattr(
        auth.crud_user,
        "get_user_by_email",
        lambda db, email: db_user,
    )
    monkeypatch.setattr(auth.security, "verify_password", lambda password, password_hash: True)
    monkeypatch.setattr(auth.security, "create_access_token", lambda data: "token")
    monkeypatch.setattr(auth.crud_user, "update_last_login", lambda db, db_user: db_user)

    response = auth.login(UserLogin(email="user@example.com", password="secret"), db=object())

    assert response["code"] == 200
    assert response["message"] == "登录成功"
    assert response["data"]["token"] == "token"
    assert response["data"]["email"] == "user@example.com"
