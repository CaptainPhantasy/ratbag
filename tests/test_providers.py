"""Offline provider boundary tests. Every HTTP request goes to a local fixture."""

import asyncio
import copy
import json
import math
import os
import socket
import ssl
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from swarm.providers import (
    ConfigurationError,
    LLMClient,
    LLMReply,
    ProviderError,
    ProviderRegistry,
    ZAI_CODING_BASE,
    _NoRedirect,
    _build_payload,
    _make_opener,
    endpoint_url,
    normalize_base_url,
)


# This string authenticates nothing outside the fixture and is never a live key.
FIXTURE_KEY = "offline-fixture-auth-sentinel"


def completion(text="A completed answer.", finish="stop"):
    return {
        "model": "fixture-model",
        "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": text, "reasoning_content": "private reasoning must not escape"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
        spec = self.server.responses.pop(0)
        if spec.get("delay"):
            time.sleep(spec["delay"])
        data = spec.get("raw")
        if data is None:
            data = json.dumps(spec.get("json", completion())).encode()
        self.send_response(spec.get("status", 200))
        self.send_header("Content-Type", "application/json")
        if not spec.get("no_length"):
            self.send_header("Content-Length", str(spec.get("declared_length", len(data))))
        for key, value in spec.get("headers", {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class FixtureOpener:
    """Keep the production URL visible but route the HTTP exchange locally."""

    def __init__(self, base):
        self.base = base
        self.original_urls = []
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def open(self, request, timeout):
        self.original_urls.append(request.full_url)
        rewritten = urllib.request.Request(
            self.base + "/fixture", data=request.data, headers=dict(request.header_items()), method=request.method,
        )
        return self.opener.open(rewritten, timeout=timeout)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="swarm-provider-settings-test-"))
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        # Test directories are retained, in keeping with the repository rule.
        self.registry = ProviderRegistry(self.temp)

    def test_defaults_pin_glm_coding_and_exact_model_names(self):
        public = self.registry.public_configs()
        self.assertEqual(set(public), {"architect", "lead", "scout", "auditor", "router"})
        for role in ("architect", "auditor"):
            self.assertEqual(public[role]["base_url"], ZAI_CODING_BASE)
            self.assertTrue(public[role]["endpoint_locked"])
        self.assertEqual(public["architect"]["effort"], "max")
        self.assertEqual(public["lead"]["model_id"], "deepseek-flash")
        self.assertEqual(public["scout"]["model_id"], "MiniMax-M3.1-Flash")
        self.assertEqual(public["scout"]["effort"], "low")
        self.assertEqual(public["router"]["model_id"], "z-ai/glm-5.3-flash")
        self.assertTrue(public["router"]["optional"])
        self.assertFalse(public["router"]["enabled"])
        self.assertTrue(all(v["last_check"] is None for v in public.values()))

    def test_key_resolution_is_session_then_env_and_never_persisted(self):
        os.environ["DEEPSEEK_API_KEY"] = "offline-environment-sentinel"
        self.assertEqual(self.registry.resolve_key("lead"), "offline-environment-sentinel")
        self.registry.set_key("lead", FIXTURE_KEY)
        self.assertEqual(self.registry.resolve_key("lead"), FIXTURE_KEY)
        self.registry.configure("lead", {"max_tokens": 4096})
        self.assertNotIn(FIXTURE_KEY, json.dumps(self.registry.public_configs()))
        self.assertNotIn(FIXTURE_KEY, json.dumps(self.registry.get_config("lead")))
        self.assertNotIn(FIXTURE_KEY, (self.temp / "providers.json").read_text())
        restored = ProviderRegistry(self.temp)
        self.assertEqual(restored.resolve_key("lead"), "offline-environment-sentinel")
        self.assertEqual(restored.get_config("lead")["max_tokens"], 4096)
        self.registry.set_key("lead", "")
        self.assertEqual(self.registry.resolve_key("lead"), "offline-environment-sentinel")

    def test_missing_and_placeholder_keys_are_clear_errors(self):
        with self.assertRaisesRegex(ConfigurationError, "DEEPSEEK_API_KEY"):
            self.registry.resolve_key("lead")
        with self.assertRaises(ConfigurationError):
            self.registry.set_key("lead", "sk-placeholder-key")
        with self.assertRaises(ConfigurationError):
            self.registry.set_key("lead", "abc\ndef")

    def test_changes_in_endpoint_clear_session_key_and_check(self):
        self.registry.set_key("lead", FIXTURE_KEY)
        self.registry.record_check("lead", True, model="fixture-model", elapsed_ms=3.1)
        self.registry.configure("lead", {"base_url": "https://other.example/v1"})
        public = self.registry.public_configs()["lead"]
        self.assertFalse(public["key_present"])
        self.assertIsNone(public["last_check"])

    def test_key_presence_does_not_claim_success(self):
        self.registry.set_key("lead", FIXTURE_KEY)
        public = self.registry.public_configs()["lead"]
        self.assertTrue(public["key_present"])
        self.assertEqual(public["key_source"], "session")
        self.assertIsNone(public["last_check"])
        self.registry.record_check("lead", False, message=FIXTURE_KEY)
        public = self.registry.public_configs()["lead"]
        self.assertFalse(public["last_check"]["ok"])
        self.assertNotIn(FIXTURE_KEY, json.dumps(public))

    def test_native_glm_cannot_switch_to_standard_or_bigmodel(self):
        for base in ("https://api.z.ai/api/paas/v4", "https://open.bigmodel.cn/api/paas/v4", "https://other.example/v1", "https://openrouter.ai/api/v1"):
            with self.subTest(base=base), self.assertRaisesRegex(ConfigurationError, "USA Coding"):
                self.registry.configure("architect", {"base_url": base})
        with self.assertRaisesRegex(ConfigurationError, "USA Coding"):
            self.registry.configure("auditor", {"protocol": "anthropic"})
        self.assertEqual(self.registry.get_config("architect")["base_url"], ZAI_CODING_BASE)

    def test_rejects_malformed_configs_without_persisting(self):
        bad_values = [
            {"api_key": FIXTURE_KEY}, {"unknown": True}, {"model_id": "bad model"},
            {"model_id": "sk-secret-accidentally-pasted"}, {"protocol": []}, {"effort": []},
            {"max_tokens": True}, {"max_tokens": 0}, {"timeout_seconds": math.inf},
            {"timeout_seconds": math.nan}, {"timeout_seconds": 0}, {"api_key_env": "actual-key-value"}, {"enabled": "yes"},
        ]
        for values in bad_values:
            with self.subTest(values=values), self.assertRaises(ConfigurationError):
                self.registry.configure("lead", values)
        self.assertFalse((self.temp / "providers.json").exists())

    def test_config_cannot_hide_known_key_in_public_fields(self):
        self.registry.set_key("lead", FIXTURE_KEY)
        with self.assertRaises(ConfigurationError):
            self.registry.configure("scout", {"model_id": FIXTURE_KEY})

    def test_public_config_mutation_cannot_change_registry(self):
        public = self.registry.public_configs()
        public["lead"]["base_url"] = "https://malicious.example"
        self.assertEqual(self.registry.get_config("lead")["base_url"], "https://api.deepseek.com/v1")

    def test_corrupt_saved_config_is_preserved_and_rejected(self):
        path = self.temp / "providers.json"
        path.write_text('{"lead":{"api_key":"not-a-real-key"}}')
        with self.assertRaisesRegex(ConfigurationError, "Saved provider settings"):
            ProviderRegistry(self.temp)
        self.assertIn("not-a-real-key", path.read_text())


class EndpointTests(unittest.TestCase):
    def test_opener_honors_environment_proxy_and_retains_redirect_guard(self):
        with patch.dict(os.environ, {"https_proxy": "http://offline-proxy.invalid:3128", "no_proxy": "127.0.0.1,localhost"}, clear=True):
            opener = _make_opener()
        proxy = next(handler for handler in opener.handlers if isinstance(handler, urllib.request.ProxyHandler))
        self.assertEqual(proxy.proxies["https"], "http://offline-proxy.invalid:3128")
        self.assertTrue(any(isinstance(handler, _NoRedirect) for handler in opener.handlers))

    def test_protocol_paths_do_not_duplicate_v1_or_operation(self):
        samples = [
            ("openai", "https://api.deepseek.com/v1/", "https://api.deepseek.com/v1/chat/completions"),
            ("openai", "https://api.deepseek.com/chat/completions", "https://api.deepseek.com/chat/completions"),
            ("anthropic", "https://api.minimax.io/anthropic", "https://api.minimax.io/anthropic/v1/messages"),
            ("anthropic", "https://api.deepseek.com/anthropic/v1", "https://api.deepseek.com/anthropic/v1/messages"),
            ("anthropic", "https://fixture.example/v1/messages", "https://fixture.example/v1/messages"),
        ]
        for protocol, base, expected in samples:
            with self.subTest(base=base):
                self.assertEqual(endpoint_url({"protocol": protocol, "base_url": base}), expected)

    def test_http_only_loopback_and_rejects_url_secret_injection(self):
        for base in ("http://localhost:6000/v1", "http://127.0.0.1:6000/v1", "http://[::1]:6000/v1"):
            self.assertEqual(normalize_base_url(base, "openai"), base)
        for base in ("http://api.deepseek.com/v1", "https://user:password@example.com/v1", "https://example.com/v1?key=secret", "https://example.com/#secret", "https://example.com/../v1", "https://example.com/\nheader", "https://example.com:99999/v1"):
            with self.subTest(base=base), self.assertRaises(ConfigurationError):
                normalize_base_url(base, "openai")


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="swarm-provider-http-test-"))
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.registry = ProviderRegistry(self.temp)
        for role in self.registry.public_configs():
            self.registry.set_key(role, FIXTURE_KEY)
        self.server.requests = []
        self.server.responses = []
        self.opener = FixtureOpener(self.base)
        opener_patch = patch("swarm.providers._make_opener", return_value=self.opener)
        opener_patch.start()
        self.addCleanup(opener_patch.stop)
        self.client = LLMClient(self.registry)

    def run_reply(self, role="lead", spec=None):
        self.server.responses.append(spec or {"json": completion()})
        return asyncio.run(self.client.complete(role, "Be concise.", "Return an answer."))

    def test_openai_request_round_trip_and_measured_usage(self):
        reply = self.run_reply()
        self.assertIsInstance(reply, LLMReply)
        self.assertEqual(reply.text, "A completed answer.")
        self.assertEqual(reply.usage, {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20})
        self.assertGreater(reply.elapsed_ms, 0)
        self.assertNotIn("reasoning", reply.text)
        request = self.server.requests[0]
        self.assertEqual(request["headers"]["Authorization"], "Bearer " + FIXTURE_KEY)
        self.assertEqual(request["body"]["reasoning_effort"], "high")
        self.assertEqual(request["body"]["thinking"], {"type": "enabled"})
        self.assertNotIn("temperature", request["body"])
        self.assertEqual(self.opener.original_urls, ["https://api.deepseek.com/v1/chat/completions"])

    def test_glm_request_stays_on_locked_endpoint_with_max_effort(self):
        self.run_reply("architect")
        self.assertEqual(self.opener.original_urls[0], ZAI_CODING_BASE + "/chat/completions")
        self.assertEqual(self.server.requests[0]["body"]["reasoning_effort"], "max")

    def test_anthropic_round_trip_translates_effort_and_removes_thinking(self):
        self.registry.configure("scout", {"protocol": "anthropic", "base_url": "https://api.minimax.io/anthropic"})
        self.registry.set_key("scout", FIXTURE_KEY)
        data = {"model": "MiniMax-M3.1-Flash", "stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": "private"}, {"type": "text", "text": "Done."}], "usage": {"input_tokens": 4, "output_tokens": 7}}
        reply = self.run_reply("scout", {"json": data})
        self.assertEqual(reply.text, "Done.")
        request = self.server.requests[0]
        self.assertEqual(request["body"]["output_config"], {"effort": "low"})
        self.assertEqual(request["body"]["thinking"], {"type": "adaptive"})
        self.assertNotIn("reasoning_effort", request["body"])
        headers = {k.lower(): v for k, v in request["headers"].items()}
        self.assertEqual(headers["x-api-key"], FIXTURE_KEY)
        self.assertNotIn("authorization", headers)
        self.assertEqual(self.opener.original_urls[0], "https://api.minimax.io/anthropic/v1/messages")

    def test_deepseek_anthropic_effort_mapping(self):
        self.registry.configure("lead", {"protocol": "anthropic", "base_url": "https://api.deepseek.com/anthropic/v1", "effort": "xhigh"})
        self.registry.set_key("lead", FIXTURE_KEY)
        self.run_reply("lead", {"json": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}})
        self.assertEqual(self.server.requests[0]["body"]["output_config"], {"effort": "high"})

    def test_router_optional_enabling_and_openrouter_reasoning_shape(self):
        with self.assertRaisesRegex(ConfigurationError, "Enable"):
            asyncio.run(self.client.complete("router", "Guide", "Decide"))
        self.assertEqual(self.server.requests, [])
        self.registry.configure("router", {"enabled": True})
        self.run_reply("router")
        self.assertEqual(self.server.requests[0]["body"]["reasoning"], {"effort": "low", "exclude": True})
        self.assertNotIn("reasoning_effort", self.server.requests[0]["body"])

    def test_missing_key_prevents_any_http_request(self):
        self.registry.set_key("lead", "")
        with self.assertRaises(ConfigurationError):
            asyncio.run(self.client.complete("lead", "Guide", "Task"))
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.opener.original_urls, [])

    def test_provider_error_is_sanitized_and_not_retried(self):
        with self.assertRaises(ProviderError) as caught:
            self.run_reply(spec={"status": 401, "raw": ("echo " + FIXTURE_KEY + " secret body").encode()})
        self.assertEqual(caught.exception.http_status, 401)
        self.assertNotIn(FIXTURE_KEY, str(caught.exception))
        self.assertNotIn("secret body", str(caught.exception))
        self.assertEqual(len(self.server.requests), 1)

    def test_network_errors_have_safe_categories_without_addresses_or_keys(self):
        private_detail = "private-network-address " + FIXTURE_KEY
        cases = [
            (socket.gaierror(-3, private_detail), "dns_error"),
            (ssl.SSLCertVerificationError(1, private_detail), "tls_certificate_error"),
            (ssl.SSLError(1, private_detail), "tls_error"),
            (ConnectionRefusedError(111, private_detail), "connect_error"),
            (TimeoutError(private_detail), "timeout"),
            ("Tunnel connection failed: 407 " + private_detail, "proxy_auth_error"),
            ("Tunnel connection failed: 403 " + private_detail, "proxy_error"),
        ]
        for reason, expected in cases:
            with self.subTest(category=expected), patch.object(self.opener, "open", side_effect=urllib.error.URLError(reason)):
                with self.assertRaises(ProviderError) as caught:
                    asyncio.run(self.client.complete("lead", "Guide", "Task"))
                self.assertEqual(caught.exception.code, expected)
                self.assertNotIn(FIXTURE_KEY, str(caught.exception))
                self.assertNotIn("private-network-address", str(caught.exception))
        self.assertEqual(self.server.requests, [])

    def test_no_proxy_keeps_loopback_fixture_direct(self):
        self.registry.configure("lead", {"base_url": self.base + "/v1", "model_id": "fixture-model"})
        self.registry.set_key("lead", FIXTURE_KEY)
        self.server.responses.append({"json": completion()})
        env = {"http_proxy": "http://offline-proxy.invalid:3128", "https_proxy": "http://offline-proxy.invalid:3128", "no_proxy": "127.0.0.1,localhost"}
        with patch.dict(os.environ, env, clear=True), patch("swarm.providers._make_opener", side_effect=_make_opener):
            reply = asyncio.run(self.client.complete("lead", "Guide", "Task"))
        self.assertEqual(reply.text, "A completed answer.")
        self.assertEqual(self.server.requests[0]["path"], "/v1/chat/completions")

    def test_redirect_never_forwards_key(self):
        with self.assertRaisesRegex(ProviderError, "redirect"):
            self.run_reply(spec={"status": 307, "headers": {"Location": self.base + "/leak"}, "raw": b""})
        self.assertEqual(len(self.server.requests), 1)
        self.assertEqual(self.server.requests[0]["path"], "/fixture")

    def test_truncation_empty_refusal_and_tool_calls_are_not_success(self):
        samples = [completion(finish="length"), completion(text=" "), completion(finish="tool_calls")]
        refused = completion()
        refused["choices"][0]["message"]["refusal"] = "declined"
        samples.append(refused)
        samples.append({"stop_reason": "max_tokens", "content": [{"type": "text", "text": "partial"}]})
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaises(ProviderError):
                self.run_reply(spec={"json": sample})

    def test_usage_is_whitelisted_and_missing_counts_are_not_invented(self):
        data = completion()
        data["usage"] = {"prompt_tokens": 4, "secret": FIXTURE_KEY, "total_tokens": -1, "completion_tokens": True, "completion_tokens_details": {"reasoning_tokens": 3, "private": "text"}}
        reply = self.run_reply(spec={"json": data})
        self.assertEqual(reply.usage, {"prompt_tokens": 4, "completion_tokens_details": {"reasoning_tokens": 3}})
        data.pop("usage")
        self.assertEqual(self.run_reply(spec={"json": data}).usage, {})

    def test_inline_thinking_and_echoed_key_do_not_escape(self):
        reply = self.run_reply(spec={"json": completion("<think>private reasoning</think>Answer " + FIXTURE_KEY)})
        self.assertEqual(reply.text, "Answer [redacted]")
        with self.assertRaises(ProviderError):
            self.run_reply(spec={"json": completion("<think>unfinished private reasoning")})

    def test_json_and_response_size_are_bounded(self):
        with self.assertRaisesRegex(ProviderError, "JSON"):
            self.run_reply(spec={"raw": b"not json " + FIXTURE_KEY.encode()})
        self.client = LLMClient(self.registry, max_response_bytes=128)
        with self.assertRaisesRegex(ProviderError, "size"):
            self.run_reply(spec={"raw": b"x" * 129, "no_length": True})
        with self.assertRaisesRegex(ProviderError, "size"):
            self.run_reply(spec={"raw": b"x", "declared_length": 129})

    def test_timeout_is_finite_and_not_retried(self):
        self.registry.configure("lead", {"timeout_seconds": 1})
        started = time.monotonic()
        with self.assertRaisesRegex(ProviderError, "timed out"):
            self.run_reply(spec={"delay": 1.4})
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(self.server.requests), 1)

    def test_oversize_prompt_is_rejected_before_network(self):
        with self.assertRaisesRegex(ConfigurationError, "too large"):
            asyncio.run(self.client.complete("lead", "Guide", "x" * (2 * 1024 * 1024)))
        self.assertEqual(self.server.requests, [])


if __name__ == "__main__":
    unittest.main()
