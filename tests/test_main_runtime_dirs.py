import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class FastAPIStub:
    def __init__(self, *args, **kwargs):
        self.mounts = []

    def add_middleware(self, *args, **kwargs):
        pass

    def include_router(self, *args, **kwargs):
        pass

    def mount(self, path, app, name=None):
        self.mounts.append((path, app, name))

    def get(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class StaticFilesStub:
    def __init__(self, directory):
        if not Path(directory).is_dir():
            raise RuntimeError(f"Directory '{directory}' does not exist")
        self.directory = directory


def install_main_import_stubs():
    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.FastAPI = FastAPIStub

    cors_module = types.ModuleType("fastapi.middleware.cors")
    cors_module.CORSMiddleware = object

    staticfiles_module = types.ModuleType("fastapi.staticfiles")
    staticfiles_module.StaticFiles = StaticFilesStub

    database_module = types.ModuleType("database")
    database_module.engine = object()
    database_module.init_db = lambda: None

    models_module = types.ModuleType("models")

    routers_module = types.ModuleType("routers")
    router_modules = {}
    for router_name in ("auth", "dataset", "task", "history", "payment"):
        module = types.ModuleType(f"routers.{router_name}")
        module.router = object()
        setattr(routers_module, router_name, module)
        router_modules[f"routers.{router_name}"] = module

    ai_engine_module = types.ModuleType("services.ai_engine")
    ai_engine_module.ai_engine = object()

    services_module = types.ModuleType("services")
    services_module.ai_engine = ai_engine_module

    return {
        "fastapi": fastapi_module,
        "fastapi.middleware": types.ModuleType("fastapi.middleware"),
        "fastapi.middleware.cors": cors_module,
        "fastapi.staticfiles": staticfiles_module,
        "database": database_module,
        "models": models_module,
        "routers": routers_module,
        "services": services_module,
        "services.ai_engine": ai_engine_module,
        **router_modules,
    }


class MainStartupDirectoryTests(unittest.TestCase):
    def test_import_creates_static_output_directory_from_empty_cwd(self):
        with TemporaryDirectory() as tmp_dir, patch.dict(
            sys.modules, install_main_import_stubs()
        ):
            spec = importlib.util.spec_from_file_location(
                "main_runtime_dir_test", REPO_ROOT / "main.py"
            )
            module = importlib.util.module_from_spec(spec)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_dir)
                self.assertFalse((Path(tmp_dir) / "data" / "outputs").exists())
                spec.loader.exec_module(module)
            finally:
                os.chdir(original_cwd)

            self.assertTrue((Path(tmp_dir) / "data" / "outputs").is_dir())


if __name__ == "__main__":
    unittest.main()
