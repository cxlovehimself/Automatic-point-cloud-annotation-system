import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from services.dataset_storage import resolve_dataset_path, safe_path_component
from services.payment_config import get_alipay_notify_url
from services.subscription import has_active_subscription


class ModuleStubs:
    def __init__(self, modules):
        self.modules = modules
        self.originals = {}

    def __enter__(self):
        for name, module in self.modules.items():
            self.originals[name] = sys.modules.get(name)
            sys.modules[name] = module
        return self

    def __exit__(self, exc_type, exc, tb):
        for name, original in self.originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class FakeAPIRouter:
    def __init__(self, *args, **kwargs):
        pass

    def post(self, *args, **kwargs):
        return lambda func: func

    def get(self, *args, **kwargs):
        return lambda func: func


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail=None, headers=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers


def fake_depends(dependency=None):
    return None


class CriticalFixTests(unittest.TestCase):
    def test_auth_login_unknown_email_returns_401_instead_of_crashing(self):
        auth = self._import_auth_router_with_missing_user()
        login_request = types.SimpleNamespace(email="missing@example.com", password="bad")

        with self.assertRaises(auth.HTTPException) as caught:
            auth.login(login_request, db=None)

        self.assertEqual(caught.exception.status_code, 401)

    def test_auth_me_deleted_user_returns_404_instead_of_crashing(self):
        auth = self._import_auth_router_with_missing_user()

        with self.assertRaises(auth.HTTPException) as caught:
            auth.get_current_user_info(db=None, current_user_email="deleted@example.com")

        self.assertEqual(caught.exception.status_code, 404)

    def test_expired_subscription_is_not_active(self):
        user = types.SimpleNamespace(
            is_subscribed=True,
            vip_expire_time=datetime(2026, 1, 1, 12, 0, 0),
        )

        self.assertFalse(has_active_subscription(user, now=datetime(2026, 1, 2, 12, 0, 0)))

    def test_future_subscription_is_active(self):
        user = types.SimpleNamespace(
            is_subscribed=True,
            vip_expire_time=datetime.utcnow() + timedelta(days=1),
        )

        self.assertTrue(has_active_subscription(user))

    def test_dataset_path_components_reject_traversal(self):
        for bad_value in ("", ".", "..", "../outside", "nested/name", "nested\\name"):
            with self.subTest(value=bad_value):
                with self.assertRaises(ValueError):
                    safe_path_component(bad_value, "task_id")

    def test_dataset_paths_stay_under_storage_root(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "datasets"
            root.mkdir()

            safe_path = resolve_dataset_path(root, "task_1", "cloud_labels.txt")
            self.assertEqual(safe_path, (root / "task_1" / "cloud_labels.txt").resolve())

            with self.assertRaises(ValueError):
                resolve_dataset_path(root, "..", "outside.txt")

    def test_payment_notify_url_uses_configured_value_only(self):
        self.assertEqual(
            get_alipay_notify_url(" https://pay.example.com/api/payment/callback "),
            "https://pay.example.com/api/payment/callback",
        )
        with self.assertRaises(RuntimeError):
            get_alipay_notify_url("")

    def test_payment_service_ignores_request_host_for_notify_url(self):
        payment_service = self._import_payment_service_with_notify_url(
            "https://pay.example.com/api/payment/callback"
        )

        self.assertEqual(
            payment_service._build_notify_url("https://attacker.example"),
            "https://pay.example.com/api/payment/callback",
        )

    def _import_auth_router_with_missing_user(self):
        sys.modules.pop("routers.auth", None)

        fastapi_stub = types.ModuleType("fastapi")
        fastapi_stub.APIRouter = FakeAPIRouter
        fastapi_stub.BackgroundTasks = object
        fastapi_stub.Depends = fake_depends
        fastapi_stub.HTTPException = FakeHTTPException

        sqlmodel_stub = types.ModuleType("sqlmodel")
        sqlmodel_stub.Session = object

        models_stub = types.ModuleType("models")
        for name in (
            "UserCreate",
            "UserLogin",
            "ChangePasswordRequest",
            "SendCodeRequest",
            "ResetPasswordRequest",
        ):
            setattr(models_stub, name, object)

        security_stub = types.ModuleType("security")
        security_stub.verify_password = lambda plain, hashed: False
        security_stub.create_access_token = lambda data: "token"
        security_stub.get_current_user_email = lambda: "missing@example.com"

        database_stub = types.ModuleType("database")
        database_stub.get_db = lambda: None

        crud_user_stub = types.ModuleType("services.crud_user")
        crud_user_stub.get_user_by_email = lambda db, email: None
        crud_user_stub.update_last_login = lambda db, db_user: None

        email_service_stub = types.ModuleType("services.email_service")

        with ModuleStubs(
            {
                "fastapi": fastapi_stub,
                "sqlmodel": sqlmodel_stub,
                "models": models_stub,
                "security": security_stub,
                "database": database_stub,
                "services.crud_user": crud_user_stub,
                "services.email_service": email_service_stub,
            }
        ):
            return importlib.import_module("routers.auth")

    def _import_payment_service_with_notify_url(self, notify_url):
        sys.modules.pop("services.payment_service", None)
        previous_notify_url = os.environ.get("ALIPAY_NOTIFY_URL")
        os.environ["ALIPAY_NOTIFY_URL"] = notify_url

        alipay_stub = types.ModuleType("alipay")

        class FakeAliPay:
            def __init__(self, *args, **kwargs):
                pass

            def verify(self, data, signature):
                return True

            def api_alipay_trade_page_pay(self, **kwargs):
                return "order_string"

        alipay_stub.AliPay = FakeAliPay

        dotenv_stub = types.ModuleType("dotenv")
        dotenv_stub.load_dotenv = lambda: None

        sqlmodel_stub = types.ModuleType("sqlmodel")
        sqlmodel_stub.Session = object
        sqlmodel_stub.select = lambda model: None

        models_stub = types.ModuleType("models")
        models_stub.Order = object
        models_stub.User = object

        try:
            with ModuleStubs(
                {
                    "alipay": alipay_stub,
                    "dotenv": dotenv_stub,
                    "sqlmodel": sqlmodel_stub,
                    "models": models_stub,
                }
            ):
                return importlib.import_module("services.payment_service")
        finally:
            if previous_notify_url is None:
                os.environ.pop("ALIPAY_NOTIFY_URL", None)
            else:
                os.environ["ALIPAY_NOTIFY_URL"] = previous_notify_url


if __name__ == "__main__":
    unittest.main()
