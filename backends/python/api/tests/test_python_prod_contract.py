import importlib
import os
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase


API_ROOT = Path(__file__).resolve().parents[1]


class PythonProdContractTest(SimpleTestCase):
    def test_config_uses_mysql_default_port_in_production(self):
        with patch.dict(
            os.environ,
            {
                "BUILD_TARGET": "production",
                "DB_TYPE": "mysql",
                "DB_NAME": "prod_db",
                "DB_USER": "prod_user",
                "DB_PASSWORD": "prod_password",
                "DB_HOST": "mysql.example.internal",
                "JWT_SECRET": "secret",
                "JWT_ALGORITHM": "HS256",
                "CLIENT_ID": "client",
                "CLIENT_SECRET": "client-secret",
                "VIRTUAL_HOST": "https://app.example.com",
            },
            clear=True,
        ):
            import config as config_module

            importlib.reload(config_module)

            self.assertFalse(config_module.config.debug)
            self.assertEqual(config_module.config.db_type, "mysql")
            self.assertEqual(config_module.config.db_port, 3306)
            self.assertEqual(config_module.config.db_host, "mysql.example.internal")
            self.assertEqual(
                set(config_module.Config.__annotations__),
                {
                    "debug",
                    "db_type",
                    "db_name",
                    "db_user",
                    "db_password",
                    "db_host",
                    "db_port",
                    "cloudpub_token",
                    "jwt_secret",
                    "jwt_algorithm",
                    "client_id",
                    "client_secret",
                    "app_base_url",
                    "otel_endpoint",
                    "otel_service_name",
                },
            )

        import config as config_module
        importlib.reload(config_module)

    def test_production_start_script_uses_gunicorn_without_dev_bootstrap_steps(self):
        script_path = API_ROOT / "scripts/start-production.sh"
        self.assertTrue(script_path.exists(), "Expected a dedicated production start script for Python API")

        script_source = script_path.read_text(encoding="utf-8")
        self.assertIn("gunicorn", script_source)
        self.assertNotIn("makemigrations", script_source)
        self.assertNotIn("createsuperuser", script_source)

    def test_worker_start_script_uses_celery(self):
        script_path = API_ROOT / "scripts/start-worker.sh"
        self.assertTrue(script_path.exists(), "Expected a dedicated worker start script for Celery")

        script_source = script_path.read_text(encoding="utf-8")
        self.assertIn("celery", script_source)
        self.assertNotIn("gunicorn", script_source)

    def test_production_dockerfile_uses_dedicated_start_script(self):
        dockerfile_path = API_ROOT / "Dockerfile"
        dockerfile_source = dockerfile_path.read_text(encoding="utf-8")

        self.assertIn('CMD ["sh", "./scripts/start-production.sh"]', dockerfile_source)
        self.assertNotIn('createsuperuser --noinput || true \\\n  && gunicorn', dockerfile_source)

    def test_python_runtime_no_longer_depends_on_legacy_support_reporting(self):
        self.assertFalse((API_ROOT / "error_reporting.py").exists())

        log_errors_source = (API_ROOT / "main/utils/decorators/log_errors.py").read_text(encoding="utf-8")
        self.assertNotIn("report_error", log_errors_source)
