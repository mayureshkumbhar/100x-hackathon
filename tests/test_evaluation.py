import json
import os
import unittest
from unittest.mock import patch

import httpx

from evaluation import evaluate_request


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def run_flow(self, *, choices=("pass", "pass"), groq_status=200, jev_status=200,
                       jev_code=0, malformed=False, timeout=False):
        requests = []

        def handler(request):
            requests.append(request)
            payload = json.loads(request.content)
            if request.url.host == "api.groq.com":
                self.assertEqual(request.headers["authorization"], "Bearer groq-test-key")
                self.assertEqual(payload["messages"], [{"role": "user", "content": "Give me a plan"}])
                if timeout:
                    raise httpx.ReadTimeout("private provider details", request=request)
                return httpx.Response(groq_status, json={"choices": [{"message": {"content": "Measure baseline for 7 days."}, "finish_reason": "stop"}]})
            self.assertEqual(str(request.url), "https://www.jevai.org/api/v1/decisions")
            self.assertEqual(request.headers["authorization"], "Bearer jev-test-key")
            self.assertEqual(payload["state"]["generated_answer"], "Measure baseline for 7 days.")
            self.assertEqual(payload["state"]["good_answer_criteria"], ["Has a number", "Has a baseline"])
            self.assertEqual(set(payload["questions"]["rule_1"]["criteria"]), {"pass", "fail"})
            if malformed:
                return httpx.Response(200, content=b"not json")
            return httpx.Response(jev_status, json={"code": jev_code, "data": {"answers": {
                f"rule_{i}": {"choice": choice, "confidence": 0.9} for i, choice in enumerate(choices, 1)
            }}})

        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-test-key", "JEV_API_KEY": "jev-test-key"}):
            result = await evaluate_request("Give me a plan", "Has a number\nHas a baseline", transport=httpx.MockTransport(handler))
        return result, requests

    async def test_pass_and_data_flow(self):
        (answer, verdict, rows), requests = await self.run_flow()
        self.assertIn("7 days", answer)
        self.assertTrue(verdict.startswith("PASS"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(requests), 2)

    async def test_one_failure_fails_overall(self):
        (_, verdict, rows), _ = await self.run_flow(choices=("pass", "fail"))
        self.assertTrue(verdict.startswith("FAIL"))
        self.assertEqual(rows[1][1], "FAIL")

    async def test_missing_judgment_never_passes(self):
        (answer, verdict, rows), _ = await self.run_flow(choices=("pass",))
        self.assertTrue(answer)
        self.assertTrue(verdict.startswith("Error"))
        self.assertEqual(rows, [])

    async def test_provider_errors_and_no_secret_leaks(self):
        for options in [{"groq_status": 401}, {"jev_status": 429}, {"jev_code": 1},
                        {"malformed": True}, {"timeout": True}, {"choices": ("maybe", "pass")}]:
            with self.subTest(options=options):
                (_, verdict, rows), _ = await self.run_flow(**options)
                self.assertTrue(verdict.startswith("Error"))
                self.assertEqual(rows, [])
                self.assertNotIn("test-key", verdict)
                self.assertNotIn("private provider details", verdict)

    async def test_missing_keys_and_invalid_inputs_make_no_calls(self):
        def forbidden(request):
            self.fail("Invalid input must not trigger requests")
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "JEV_API_KEY": ""}):
            for prompt, rules in [("A plan", "Has a number"), ("", "A rule"), ("A plan", ""),
                                  ("x" * 8001, "A rule"), ("A plan", "\n".join(["rule"] * 11))]:
                result = await evaluate_request(prompt, rules, transport=httpx.MockTransport(forbidden))
                self.assertTrue(result[1].startswith("Error"))

    async def test_jev_byte_limit(self):
        def handler(request):
            self.assertEqual(request.url.host, "api.groq.com")
            return httpx.Response(200, json={"choices": [{"message": {"content": "界" * 15000}, "finish_reason": "stop"}]})
        with patch.dict(os.environ, {"GROQ_API_KEY": "g", "JEV_API_KEY": "j"}):
            answer, verdict, rows = await evaluate_request("A plan", "A criterion", transport=httpx.MockTransport(handler))
        self.assertTrue(answer)
        self.assertIn("32 KiB", verdict)
        self.assertEqual(rows, [])
