"""Regression checks for application setup and shared model initialization."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class AppImportTests(unittest.TestCase):
    def test_app_import_does_not_import_native_inference_runtimes(self):
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import main; "
                "assert 'rembg' not in sys.modules; "
                "assert 'ultralytics' not in sys.modules; "
                "assert main.app is not main.create_app(); "
                "paths = set(main.app.openapi()['paths']); "
                "assert {'/health', '/images/process'} <= paths",
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class ModelInitializationTests(unittest.TestCase):
    def setUp(self):
        from services import model_runtime

        self.runtime = model_runtime
        self.enterContext(patch.object(model_runtime, "rembg_session", None))
        self.enterContext(patch.object(model_runtime, "yolo_model", None))

    def test_uninitialized_models_fail_explicitly(self):
        for getter in (
            self.runtime.get_detector,
            self.runtime.get_background_session,
        ):
            with self.subTest(getter=getter.__name__):
                with self.assertRaisesRegex(RuntimeError, "have not been loaded"):
                    getter()

    def test_startup_reuses_the_same_model_pair(self):
        session, detector = object(), object()
        yolo = Mock(return_value=detector)
        with (
            patch.object(
                self.runtime, "create_rembg_session", return_value=session
            ) as create_session,
            patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=yolo)}),
        ):
            self.runtime.load_models()
            self.runtime.load_models()
        create_session.assert_called_once_with("u2net_human_seg")
        yolo.assert_called_once_with(str(self.runtime.MODEL_PATH))
        self.assertIs(self.runtime.get_detector(), detector)
        self.assertIs(self.runtime.get_background_session(), session)

    def test_failed_startup_does_not_publish_a_partial_model_pair(self):
        yolo = Mock(side_effect=RuntimeError("detector startup failed"))
        with (
            patch.object(self.runtime, "create_rembg_session", return_value=object()),
            patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=yolo)}),
        ):
            with self.assertRaisesRegex(RuntimeError, "detector startup failed"):
                self.runtime.load_models()
        self.assertIsNone(self.runtime.yolo_model)
        self.assertIsNone(self.runtime.rembg_session)


class AppLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, method, path, headers=None):
        import main

        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "path": path,
            "root_path": "",
            "query_string": b"",
            "headers": headers or [],
            "server": ("test", 80),
            "client": ("test", 123),
        }
        await main.create_app()(scope, receive, send)
        return sent

    async def test_health_route_bypasses_upload_admission(self):
        with patch("request_limits.processing_pool.try_acquire") as acquire:
            messages = await self.request("GET", "/health")
        self.assertEqual(messages[0]["status"], 200)
        self.assertEqual(messages[1]["body"], b'{"status":"ready"}')
        acquire.assert_not_called()

    async def test_cors_preflight_preserves_local_frontend_access(self):
        headers = [
            (b"origin", b"http://localhost:3000"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ]
        with patch("request_limits.processing_pool.try_acquire") as acquire:
            messages = await self.request("OPTIONS", "/images/process", headers)
        self.assertEqual(messages[0]["status"], 200)
        response_headers = dict(messages[0]["headers"])
        self.assertEqual(
            response_headers[b"access-control-allow-origin"], b"http://localhost:3000"
        )
        acquire.assert_not_called()

    async def test_lifespan_loads_models_before_serving(self):
        import main

        application = main.create_app()
        with patch.object(main, "load_models") as load:
            async with main.lifespan(application):
                load.assert_called_once_with()

    async def test_failed_startup_never_yields_a_ready_application(self):
        import main

        with patch.object(
            main, "load_models", side_effect=RuntimeError("startup failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "startup failed"):
                async with main.lifespan(main.create_app()):
                    self.fail("A failed startup must not start serving requests")

    async def test_shutdown_is_logged_even_when_application_context_fails(self):
        import main

        with (
            patch.object(main, "load_models"),
            patch.object(main.logger, "info") as log,
        ):
            with self.assertRaisesRegex(RuntimeError, "request context failed"):
                async with main.lifespan(main.create_app()):
                    raise RuntimeError("request context failed")
        log.assert_any_call("Shutting down photo service")
