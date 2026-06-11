import importlib
import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_login_unknown_user_returns_401(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    auth_router = importlib.import_module("routers.auth")

    monkeypatch.setattr(auth_router.crud_user, "get_user_by_email", lambda db, email: None)

    with pytest.raises(HTTPException) as exc_info:
        auth_router.login(SimpleNamespace(email="missing@example.com", password="pw"), db=object())

    assert exc_info.value.status_code == 401


def test_dataset_path_components_are_sanitized(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    dataset_router = importlib.import_module("routers.dataset")

    assert dataset_router._safe_path_component("../../../tmp/pwn", "cloud") == "pwn"
    assert dataset_router._safe_path_component("..", "cloud") == "cloud"
    assert dataset_router._safe_path_component("room 1/scan A", "cloud") == "scan_A"


def test_payment_notify_url_ignores_request_host(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    monkeypatch.setitem(sys.modules, "alipay", _fake_alipay_module())

    payment_service = importlib.import_module("services.payment_service")
    monkeypatch.setattr(payment_service, "NOTIFY_URL", "https://trusted.example/api/payment/callback")

    assert (
        payment_service._build_notify_url("https://evil.example")
        == "https://trusted.example/api/payment/callback"
    )


def test_active_subscription_requires_future_expiry(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    _install_task_import_stubs(monkeypatch)
    task_router = importlib.import_module("routers.task")

    expired_user = SimpleNamespace(
        is_subscribed=True,
        vip_expire_time=datetime.now() - timedelta(seconds=1),
    )
    active_user = SimpleNamespace(
        is_subscribed=True,
        vip_expire_time=datetime.now() + timedelta(days=1),
    )

    assert not task_router._has_active_subscription(expired_user)
    assert task_router._has_active_subscription(active_user)


def _fake_alipay_module():
    module = types.ModuleType("alipay")

    class FakeAliPay:
        def __init__(self, *args, **kwargs):
            pass

        def verify(self, *args, **kwargs):
            return False

        def api_alipay_trade_page_pay(self, *args, **kwargs):
            return "order_string"

    module.AliPay = FakeAliPay
    return module


def _install_task_import_stubs(monkeypatch):
    worker = types.ModuleType("worker")
    worker.celery_app = object()
    worker.run_ai_segmentation_task = SimpleNamespace(apply_async=lambda **kwargs: None)
    monkeypatch.setitem(sys.modules, "worker", worker)

    celery = types.ModuleType("celery")
    celery_result = types.ModuleType("celery.result")
    celery_result.AsyncResult = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "celery", celery)
    monkeypatch.setitem(sys.modules, "celery.result", celery_result)
