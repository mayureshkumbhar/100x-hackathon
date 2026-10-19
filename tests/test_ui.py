import re
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app import app, demo
from ui_logic import compare_runs, inspect_case, validate_draft


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [["Plan onboarding", "A measurable experiment", "max_words:300; has_number"]]

    def test_valid_draft(self):
        self.assertIn("1 of 10", validate_draft("https://example.com/api", "input", "output", self.rows))

    def test_invalid_urls(self):
        for url in [None, "http://example.com", "https://localhost", "https://127.0.0.1",
                    "https://user:secret@example.com", "https://example.com?key=secret",
                    "https://example.com:bad", "https://[::1]"]:
            with self.subTest(url=url):
                self.assertIn("public HTTPS", validate_draft(url, "input", "output", self.rows))

    def test_invalid_rows(self):
        for rows in [[["x", "", ""]], [["x", "y", "judge:"]], [["x", "y", "max_words:0"]], [[1, "y", "has_number"]], []]:
            self.assertNotIn("validated", validate_draft("https://example.com", "input", "output", rows))

    def test_selection_guards_and_cases(self):
        self.assertEqual(inspect_case(None), ("", "", "", []))
        self.assertNotEqual(inspect_case("GP-01"), inspect_case("GP-02"))
        for selection in [(None, None), ("Sample run 1", "Sample run 1"), ("Sample run 2", "Sample run 1")]:
            self.assertEqual(compare_runs(*selection)[1], [])
        self.assertEqual(compare_runs("Sample run 1", "Sample run 2")[1][0][-1], "Fixed")


class AppTests(unittest.TestCase):
    def test_live_gradio_callback(self):
        index = next(i for i, fn in demo.fns.items() if fn.fn and fn.fn.__name__ == "evaluate_request")
        with TestClient(app) as client, \
             patch.dict("os.environ", {"GROQ_API_KEY": "groq-fake", "JEV_API_KEY": "jev-fake"}), \
             patch("evaluation.generate", new=AsyncMock(return_value="A 7 day plan.")), \
             patch("evaluation.judge", new=AsyncMock(return_value=[["Has a number", "PASS", "90%"]])):
            response = client.post("/gradio_api/run/predict", json={
                "fn_index": index, "data": ["Give me a plan", "Has a number"]})
            self.assertEqual(response.status_code, 200)
            answer, verdict, rows = response.json()["data"]
            self.assertEqual(answer, "A 7 day plan.")
            self.assertTrue(verdict.startswith("PASS"))
            self.assertEqual(rows["data"][0][1], "PASS")

    def test_assets_and_stateless_callbacks(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/healthz").json(), {"status": "ok", "mode": "groq-jev"})
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            config = client.get("/config").json()
            self.assertFalse(any(item["queue"] for item in config["dependencies"]))
            asset = re.search(r'(?:src|href)="([^\"]*/assets/[^\"]+)"', response.text)
            self.assertIsNotNone(asset)
            self.assertEqual(client.get(asset.group(1)).status_code, 200)
            for name, data in [("inspect_case", ["GP-01"]), ("inspect_case", ["GP-02"]),
                               ("load_demo", []), ("compare_runs", ["Sample run 1", "Sample run 2"])]:
                index = next(i for i, fn in demo.fns.items() if fn.fn and fn.fn.__name__ == name)
                result = client.post("/gradio_api/run/predict", json={"fn_index": index, "data": data})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertTrue(result.json()["data"])


if __name__ == "__main__":
    unittest.main()
