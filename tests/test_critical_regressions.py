import os
from decimal import Decimal

import pytest
from fastapi import HTTPException

os.environ.setdefault("DB_URL", "sqlite:///./test.db")

from routers import dataset  # noqa: E402
from services import payment_service  # noqa: E402


def test_dataset_names_are_sanitized_before_building_paths():
    assert dataset._safe_name("../../../etc/passwd", "cloud_name") == "passwd"
    assert dataset._safe_name("sample cloud.ply", "cloud_name") == "sample_cloud.ply"

    safe_path = dataset._storage_path("task", "cloud_labels.txt")
    assert os.path.commonpath([dataset.STORAGE_ROOT, safe_path]) == dataset.STORAGE_ROOT

    with pytest.raises(HTTPException):
        dataset._safe_name("../../..", "cloud_name")


def test_payment_callback_invalid_signature_returns_router_tuple(monkeypatch):
    monkeypatch.setattr(payment_service.alipay, "verify", lambda data, signature: False)

    assert payment_service.process_callback(db=None, data={"sign": "bad"}) == (False, None)


def test_payment_callback_duplicate_paid_order_is_idempotent(monkeypatch):
    monkeypatch.setattr(payment_service.alipay, "verify", lambda data, signature: True)

    class Result:
        def __init__(self, value):
            self.value = value

        def first(self):
            return self.value

    class FakeDb:
        def exec(self, statement):
            return Result(order)

    order = payment_service.Order(
        user_id=1,
        out_trade_no="ORDER_1",
        total_amount=Decimal("9.90"),
        status="paid",
    )

    assert payment_service.process_callback(
        db=FakeDb(),
        data={
            "sign": "ok",
            "trade_status": "TRADE_SUCCESS",
            "out_trade_no": "ORDER_1",
            "trade_no": "ALI_1",
            "total_amount": "9.90",
        },
    ) == (True, None)
