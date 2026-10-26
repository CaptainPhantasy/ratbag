"""Real HTTP checks at the user-facing control boundary."""
import asyncio
from concurrent.futures import Future
from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch
import urllib.request
import urllib.error

from swarm.engine import SwarmEngine, ControlBoundary
from swarm.server import Application, create_server
from swarm.store import RunStore


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="swarm-http-evidence-"))
        self.web = self.root / "web"
        self.web.mkdir()
        (self.web / "index.html").write_text("<html><title>Swarm</title></html>")
        self.app = Application(self.root / "state", self.web, access_token="local-fixture-access")
        self.server = create_server(self.app, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.app.shutdown()

    def request(self, path, method="GET", body=None, authorized=True, headers=None):
        hdr = {"Content-Type": "application/json"}
        if authorized:
            hdr["Authorization"] = "Bearer local-fixture-access"
        hdr.update(headers or {})
        req = urllib.request.Request(self.base + path, headers=hdr, method=method,
                                     data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as response:
            return response.code, response.read(), response.headers

    def test_auth_protects_run_records_but_allows_signin_page(self):
        self.assertEqual(self.request("/", authorized=False)[0], 200)
        self.assertEqual(self.request("/api/health", authorized=False)[0], 200)
        self.assertEqual(self.request("/api/runs", authorized=False)[0], 401)
        self.assertEqual(self.request("/api/runs")[0], 200)

    def test_keys_are_not_returned_or_written_with_settings(self):
        status, body, _ = self.request("/api/providers/scout", "PUT", {"api_key": "fixture-session-secret-12345"})
        self.assertEqual(status, 200, body)
        status, body, _ = self.request("/api/providers")
        self.assertEqual(status, 200)
        self.assertNotIn(b"fixture-session-secret", body)
        for file in (self.root / "state").glob("*.json"):
            self.assertNotIn("fixture-session-secret", file.read_text())

    def test_missing_provider_keys_do_not_start_a_job(self):
        status, body, _ = self.request("/api/runs", "POST", {"task": "Fix example", "repo_path": str(self.root)})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.app.store.list_runs(), [])

    def test_host_and_cross_origin_are_rejected(self):
        self.assertEqual(self.request("/api/runs", headers={"Host": "untrusted.invalid"})[0], 403)
        self.assertEqual(self.request("/api/providers/scout", "PUT", {}, headers={"Origin": "https://untrusted.invalid"})[0], 403)

    def test_persisted_evidence_is_available_and_has_safe_type(self):
        run = self.app.store.create_run({"task": "Fixture", "repo_path": str(self.root)})
        self.app.store.save_artifact(run["id"], "candidate.patch", "safe exact patch\n")
        status, data, headers = self.request(f"/api/runs/{run['id']}/artifacts/candidate.patch")
        self.assertEqual(status, 200)
        self.assertEqual(data, b"safe exact patch\n")
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_glm_endpoint_cannot_be_changed_to_china(self):
        status, body, _ = self.request("/api/providers/architect", "PUT", {"base_url": "https://open.bigmodel.cn/api/paas/v4"})
        self.assertEqual(status, 400, body)

    def test_remote_binding_requires_access_key(self):
        app = Application(self.root / "other-state", self.web)
        try:
            with self.assertRaises(ValueError):
                create_server(app, "0.0.0.0", 0)
        finally:
            app.shutdown()


class ServerStateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="swarm-server-state-evidence-"))
        self.web = self.root / "web"
        self.web.mkdir()
        self.state = self.root / "state"
        self.app = Application(self.state, self.web)

    def tearDown(self):
        self.app.shutdown()

    def saved_run(self, status="paused"):
        run = self.app.store.create_run({"task": "Retain fixture work", "repo_path": str(self.root)})
        self.app.store.save_artifact(run["id"], "candidate.patch", "retained fixture patch\n")
        return self.app.store.update_run(run["id"], status=status, stage="checking",
                                         checkpoint="candidate_saved", pause_requested=status == "paused")

    def test_busy_resume_leaves_saved_state_and_can_be_retried(self):
        waiting = self.saved_run()
        active = self.saved_run("running")
        busy = Future()
        self.app._future = busy
        self.app.running_run_id = active["id"]
        try:
            with self.assertRaisesRegex(ValueError, "already active"):
                self.app.control(waiting["id"], "resume")
            self.assertEqual(self.app.store.get_run(waiting["id"]), waiting)
            self.assertEqual(self.app.running_run_id, active["id"])
        finally:
            busy.set_result(None)
            self.app.running_run_id = None

        with patch("swarm.server.SwarmEngine") as factory:
            factory.return_value.execute = AsyncMock()
            self.app.control(waiting["id"], "resume")
            self.app._future.result(timeout=2)
            factory.return_value.execute.assert_awaited_once_with(waiting["id"])
        self.assertEqual(self.app.store.read_artifact(waiting["id"], "candidate.patch"), "retained fixture patch\n")

    def test_resume_submission_failure_restores_saved_state(self):
        waiting = self.saved_run("interrupted")
        waiting = self.app.store.update_run(waiting["id"], interrupt_requested=True)
        with patch.object(self.app._pool, "submit", side_effect=RuntimeError("fixture worker unavailable")):
            with self.assertRaisesRegex(RuntimeError, "fixture worker unavailable"):
                self.app.control(waiting["id"], "resume")
        restored = self.app.store.get_run(waiting["id"])
        for field in ("status", "pause_requested", "cancel_requested", "interrupt_requested", "checkpoint", "artifacts"):
            self.assertEqual(restored[field], waiting[field], field)
        self.assertIsNone(self.app.running_run_id)

    def shutdown_at_boundary(self, owner_cancel=False):
        run = self.saved_run("running")
        started = threading.Event()
        client = AsyncMock()
        client.complete.side_effect = AssertionError("This control fixture must not call a provider.")
        engine = SwarmEngine(self.app.store, self.app.registry, client=client)

        async def controlled_execution(run_id):
            engine.run_id = run_id
            started.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                current = engine._run()
                if current.get("interrupt_requested") or current.get("cancel_requested"):
                    break
                await asyncio.sleep(0.01)
            try:
                await engine._boundary("checking")
            except ControlBoundary:
                pass

        engine.execute = controlled_execution
        with patch("swarm.server.SwarmEngine", return_value=engine):
            self.app.start(run["id"])
            self.assertTrue(started.wait(2), "The control fixture did not start.")
            if owner_cancel:
                self.app.control(run["id"], "cancel")
            self.app.shutdown()
        client.complete.assert_not_awaited()

        saved = RunStore(self.state)
        try:
            persisted = saved.get_run(run["id"])
            self.assertEqual(saved.read_artifact(run["id"], "candidate.patch"), "retained fixture patch\n")
            self.assertEqual(persisted["checkpoint"], "candidate_saved")
            return persisted
        finally:
            saved.close()

    def test_shutdown_interrupts_and_reopened_run_can_resume(self):
        persisted = self.shutdown_at_boundary()
        self.assertEqual(persisted["status"], "interrupted")
        self.assertFalse(persisted["cancel_requested"])
        self.app = Application(self.state, self.web)
        observed = {}

        async def resumed_execution(run_id):
            observed.update(self.app.store.get_run(run_id))

        with patch("swarm.server.SwarmEngine") as factory:
            factory.return_value.execute = resumed_execution
            self.app.control(persisted["id"], "resume")
            self.app._future.result(timeout=2)
        self.assertFalse(observed["interrupt_requested"])
        self.assertFalse(observed["cancel_requested"])
        self.assertEqual(observed["checkpoint"], "candidate_saved")
        self.assertEqual(observed["artifacts"], persisted["artifacts"])

    def test_shutdown_preserves_explicit_owner_cancel(self):
        persisted = self.shutdown_at_boundary(owner_cancel=True)
        self.assertEqual(persisted["status"], "cancelled")
        self.assertTrue(persisted["cancel_requested"])
        self.assertFalse(persisted.get("interrupt_requested", False))


if __name__ == "__main__":
    unittest.main()
