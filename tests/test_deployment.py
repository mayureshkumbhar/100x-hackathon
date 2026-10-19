"""Deployment checks with no real database, target API, or Groq requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import unittest
from unittest.mock import Mock, patch

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

from fastapi.testclient import TestClient
from app import app
from hackathon.ui.ui import core


class DeploymentTests(unittest.TestCase):
    def test_explicit_vercel_entrypoint_exports_the_mounted_application(self):
        root = Path(__file__).resolve().parent.parent
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["vercel"]["entrypoint"], "app:app")
        pins = (root / "hackathon/requirements.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sorted(config["project"]["dependencies"]), sorted(pins))
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
        self.assertIn("gradio", {package["name"] for package in lock["package"]})
        from fastapi import FastAPI
        self.assertIsInstance(app, FastAPI)
        self.assertTrue(any(getattr(route, "path", None) == "/health" for route in app.routes))
        self.assertTrue(any(getattr(route, "path", None) == "" for route in app.routes))

    def test_vercel_build_uses_a_real_source_file_without_framework_discovery(self):
        root = Path(__file__).resolve().parent.parent
        config = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
        self.assertNotIn("framework", config)
        build, = config["builds"]
        self.assertTrue((root / build["src"]).is_file())
        self.assertEqual(build["src"], "app.py")
        self.assertEqual(build["config"]["functions"]["app.py"]["maxDuration"], 300)
        self.assertEqual(config["routes"], [{"src": "/(.*)", "dest": build["src"]}])

    def test_page_health_and_direct_callback_configuration(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            config = client.get("/config").json()
            self.assertTrue(config["dependencies"])
            self.assertTrue(all(not dep["queue"] for dep in config["dependencies"]))

    def test_full_run_and_dropdown_callback_on_fresh_session(self):
        result = {"pair_id": 11, "user_input": "trip to France", "rules": "Names France",
                  "answer": '{"destination":"France"}', "passed": True,
                  "checks": [{"check": "Names France", "passed": True, "reason": "Present"}]}
        with patch.object(core, "connect", return_value=Mock()), \
             patch.object(core, "get_groq_key", return_value="test-key"), \
             patch.object(core, "upsert_app", return_value=7), \
             patch.object(core, "save_pairs", return_value=[11]) as save, \
             patch.object(core, "run_cases", return_value=23), \
             patch.object(core, "run_results", return_value=[result]), \
             patch.object(core, "list_pairs", return_value=[{"id": 11, "user_input": "trip to France"}]), \
             patch.object(core, "list_runs", return_value=[]), TestClient(app) as client:
            response = client.post("/gradio_api/api/run_all", json={
                "data": ["https://example.test/api", {
                    "headers": ["Input", "Checks"], "data": [["trip to France", "Names France"]]
                }], "session_hash": "instance-a"
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("1 of 1 passed", response.json()["data"][0])
            self.assertEqual(save.call_args.args[2], [("trip to France", "Names France")])

            # No choices have been populated for this new session/instance.
            with patch.object(core, "latest_result", return_value={**result, "run_id": 23}):
                response = client.post("/gradio_api/api/show_case", json={
                    "data": [11], "session_hash": "fresh-instance"
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("PASS", response.json()["data"][0])

    def test_compare_accepts_dropdown_ids_without_server_session_choices(self):
        with patch.object(core, "connect", return_value=Mock()), \
             patch.object(core, "compare_runs", return_value=[["case", "fail", "pass", "fixed"]]), \
             TestClient(app) as client:
            response = client.post("/gradio_api/api/compare", json={
                "data": [1, 2], "session_hash": "never-seen-before"
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"][0]["data"][0][-1], "fixed")

    def test_database_connections_close_after_outer_callback_and_errors(self):
        connection = Mock()

        @core.database_session
        def inner():
            connection.close.assert_not_called()

        @core.database_session
        def outer():
            core._local.conn = connection
            inner()
            connection.close.assert_not_called()
            raise ValueError("callback failed")

        with self.assertRaises(ValueError):
            outer()
        connection.close.assert_called_once()
        self.assertIsNone(core._local.conn)

    def test_vercel_database_requires_ssl_and_skips_runtime_schema_creation(self):
        connection = Mock()
        core._local.conn = None
        with patch.dict(os.environ, {"VERCEL": "1", "DATABASE_URL": "postgresql://example"}), \
             patch.object(core.psycopg2, "connect", return_value=connection) as connect:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AUTO_INIT_SCHEMA", None)
                self.assertIs(core.connect(), connection)
            self.assertEqual(connect.call_args.kwargs["sslmode"], "require")
            connection.cursor.assert_not_called()
        core._local.conn = None

    def test_expired_run_budget_stores_unverified_results_without_network_calls(self):
        rows = [{"url": "https://example.test"}, {"id": 1},
                {"user_input": "trip", "rules": "Names France"}]
        cursors = [Mock(fetchone=Mock(return_value=row)) for row in rows] + [Mock()]
        with patch.dict(os.environ, {"EVAL_RUN_TIMEOUT_SECONDS": "1"}), \
             patch.object(core, "time", Mock(monotonic=Mock(side_effect=[0, 2]))), \
             patch.object(core, "_exec", side_effect=cursors) as execute, \
             patch.object(core, "call_app") as call, \
             patch.object(core, "judge_with_groq") as judge:
            self.assertEqual(core.run_cases(Mock(), 7, [11], "test"), 1)
            call.assert_not_called()
            judge.assert_not_called()
            self.assertFalse(execute.call_args.args[2][3])
            self.assertIn("Run time budget exhausted", execute.call_args.args[2][2])

    def test_expired_judge_budget_makes_no_request(self):
        with patch.object(core, "time", Mock(monotonic=Mock(return_value=2))), \
             patch.object(core.requests, "post") as post:
            verdicts = core.judge_with_groq("trip", "answer", ["check"], "test", deadline=1)
            self.assertIsNone(verdicts[0]["passed"])
            post.assert_not_called()

    def test_target_api_data_array_and_json_string_decoding(self):
        itinerary = {"destination": "France", "days": [{"day": 1, "base": "Paris"}]}
        response = Mock(status_code=200, text=json.dumps({"data": [json.dumps(itinerary)]}))
        response.json.return_value = {"data": [json.dumps(itinerary)]}
        with patch.object(core.requests, "post", return_value=response) as post:
            answer, error = core.call_app("https://example.test/api", "trip to France")
            self.assertIsNone(error)
            self.assertEqual(json.loads(answer), itinerary)
            post.assert_called_once_with("https://example.test/api",
                                         json={"data": ["trip to France"]}, timeout=60)

    def test_hosted_import_has_no_file_logger_or_local_credential_fallback(self):
        script = '''
import os
from unittest.mock import patch
os.environ['VERCEL'] = '1'
for key in ('DATABASE_URL', 'GROQ_API_KEY', 'GROQ_API'):
    os.environ.pop(key, None)
with patch('dotenv.load_dotenv'), patch('logging.handlers.RotatingFileHandler', side_effect=AssertionError('file write')):
    from hackathon.api import api as core
    assert not core.get_database_url()
    assert not core.get_groq_key()
    assert len(core.logger.handlers) == 1
print('hosted import passed')
'''
        result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True,
                                text=True, cwd=Path(__file__).resolve().parent.parent, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
