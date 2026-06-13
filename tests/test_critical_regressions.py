import asyncio
import os
import runpy
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


def test_main_creates_static_output_dir_before_mount(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)

    fastapi_module = types.ModuleType("fastapi")
    cors_module = types.ModuleType("fastapi.middleware.cors")
    staticfiles_module = types.ModuleType("fastapi.staticfiles")
    middleware_module = types.ModuleType("fastapi.middleware")

    class FakeFastAPI:
        def __init__(self, *args, **kwargs):
            self.mounts = []

        def add_middleware(self, *args, **kwargs):
            pass

        def include_router(self, *args, **kwargs):
            pass

        def mount(self, path, app, name=None):
            self.mounts.append((path, app, name))

        def get(self, path):
            def decorator(func):
                return func

            return decorator

    class FakeStaticFiles:
        def __init__(self, directory):
            if not Path(directory).is_dir():
                raise RuntimeError(f"Directory '{directory}' does not exist")

    fastapi_module.FastAPI = FakeFastAPI
    cors_module.CORSMiddleware = object
    staticfiles_module.StaticFiles = FakeStaticFiles

    database_module = types.ModuleType("database")
    database_module.engine = object()
    database_module.init_db = lambda: None

    services_module = types.ModuleType("services")
    ai_engine_module = types.ModuleType("services.ai_engine")
    ai_engine_module.ai_engine = SimpleNamespace(initialize=lambda **kwargs: None)

    routers_module = types.ModuleType("routers")
    for name in ("auth", "dataset", "task", "history", "payment"):
        router_module = types.ModuleType(f"routers.{name}")
        router_module.router = object()
        setattr(routers_module, name, router_module)
        monkeypatch.setitem(sys.modules, f"routers.{name}", router_module)

    monkeypatch.setitem(sys.modules, "fastapi", fastapi_module)
    monkeypatch.setitem(sys.modules, "fastapi.middleware", middleware_module)
    monkeypatch.setitem(sys.modules, "fastapi.middleware.cors", cors_module)
    monkeypatch.setitem(sys.modules, "fastapi.staticfiles", staticfiles_module)
    monkeypatch.setitem(sys.modules, "database", database_module)
    monkeypatch.setitem(sys.modules, "models", types.ModuleType("models"))
    monkeypatch.setitem(sys.modules, "routers", routers_module)
    monkeypatch.setitem(sys.modules, "services", services_module)
    monkeypatch.setitem(sys.modules, "services.ai_engine", ai_engine_module)

    runpy.run_path(str(repo_root / "main.py"))

    assert (tmp_path / "data" / "outputs").is_dir()
