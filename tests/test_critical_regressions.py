import asyncio
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("DB_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-regression-tests-12345")
os.environ.setdefault("ALIPAY_NOTIFY_URL", "https://payments.example.com/api/payment/callback")


def _install_fake_alipay() -> None:
    module = types.ModuleType("alipay")

    class FakeAliPay:
        def __init__(self, *args, **kwargs):
            pass

        def api_alipay_trade_page_pay(self, *args, **kwargs):
            return "signed_order=1"

        def verify(self, *args, **kwargs):
            return True

    module.AliPay = FakeAliPay
    sys.modules.setdefault("alipay", module)


_install_fake_alipay()

import security
from models import PointData, SaveDatasetRequest
from routers import dataset as dataset_router
from services import payment_service


def test_rejects_public_default_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", security.DEFAULT_INSECURE_SECRET_KEY)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError):
        security._load_secret_key()


def test_dataset_save_rejects_path_traversal_cloud_name(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_router, "STORAGE_PATH", tmp_path)
    outside_path = tmp_path.parent / "escaped_labels"
    req = SaveDatasetRequest(
        task_id="task-1",
        data=[
            PointData(
                cloud_name=str(outside_path),
                scene_type="indoor",
                points_data=[[1, 2, 3, 4]],
            )
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dataset_router.save_annotated_dataset(req, current_user=SimpleNamespace(id=1)))

    assert exc_info.value.status_code == 400
    assert not outside_path.with_name(f"{outside_path.name}_labels.txt").exists()
    assert list(tmp_path.iterdir()) == []


def test_dataset_save_writes_only_under_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_router, "STORAGE_PATH", tmp_path)
    req = SaveDatasetRequest(
        task_id="task-1",
        data=[
            PointData(
                cloud_name="scan.ply",
                scene_type="indoor",
                points_data=[[1, 2, 3, 4]],
            )
        ],
    )

    response = asyncio.run(dataset_router.save_annotated_dataset(req, current_user=SimpleNamespace(id=1)))
    save_dir = Path(response["data"]["path"])
    saved_files = list(save_dir.iterdir())

    assert save_dir.is_relative_to(tmp_path)
    assert [file.name for file in saved_files] == ["scan.ply_labels.txt"]
    assert saved_files[0].read_text(encoding="utf-8") == "1 2 3 4\n"


def test_payment_notify_url_ignores_untrusted_request_host(monkeypatch):
    configured_url = "https://payments.example.com/api/payment/callback"
    monkeypatch.setattr(payment_service, "NOTIFY_URL", configured_url)

    assert payment_service._build_notify_url("https://attacker.example") == configured_url


def test_payment_notify_url_requires_server_configuration(monkeypatch):
    monkeypatch.setattr(payment_service, "NOTIFY_URL", "")

    with pytest.raises(RuntimeError):
        payment_service._build_notify_url("https://payments.example.com")
