"""Real Git/HTTP boundaries for guided setup and source-grounded task choices."""
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from swarm import gitops
from swarm.projects import ProjectCatalog, test_options
from swarm.providers import ConfigurationError, ProviderRegistry, ZAI_CODING_BASE, model_catalog
from swarm.server import Application, create_server
from swarm.workbench import CORE_ROLES, WorkbenchSetup


def committed_project(path: Path, files: dict[str, str]):
    path.mkdir(parents=True)
    for name, text in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    gitops.git(path, "init", "--initial-branch=main")
    gitops.git(path, "add", "--", ".")
    gitops.git(path, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "-c", "commit.gpgsign=false",
               "commit", "-m", "Fixture start")


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="swarm-guided-projects-evidence-"))
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.catalog = ProjectCatalog(self.root / "state", [self.projects])

    def test_real_projects_are_bounded_and_symlink_dependencies_are_ignored(self):
        committed_project(self.projects / "actual", {"README.md": "A real fixture\n"})
        committed_project(self.projects / "node_modules" / "dependency", {"README.md": "Dependency\n"})
        committed_project(self.projects / "nested" / "one" / "too-deep", {"README.md": "Too deep\n"})
        committed_project(self.root / "outside", {"README.md": "Outside configured project root\n"})
        (self.projects / "link").symlink_to(self.root / "outside", target_is_directory=True)
        result = self.catalog.list()
        self.assertEqual([item["name"] for item in result["projects"]], ["actual"])
        self.assertEqual(result["limits"]["depth"], 2)
        project = self.catalog.inspect(result["projects"][0]["id"])
        self.assertEqual(project["branch"], "main")
        self.assertEqual(project["test_options"], [])
        self.assertIsNone(project["recommended_test_id"])

    def test_filesystem_root_is_never_scanned(self):
        catalog = ProjectCatalog(self.root / "state2", [Path("/")])
        self.assertNotIn(Path("/"), catalog.roots)
        self.assertEqual(catalog.list()["projects"], [])

    def test_declared_test_scripts_are_choices_without_executing_them(self):
        repo = self.projects / "node-example"
        committed_project(repo, {"package.json": json.dumps({"scripts": {
            "test": "node --test", "test:unit": "vitest run", "test:watch": "vitest --watch", "start": "node server.js"}}),
            "pnpm-lock.yaml": "lockfileVersion: 9\n"})
        project = self.catalog.inspect(self.catalog.list()["projects"][0]["id"])
        self.assertEqual([item["command"] for item in project["test_options"]], ["pnpm test", "pnpm run test:unit"])
        self.assertIn("not been run", project["notes"][0])

    def test_python_choices_use_actual_unittest_or_pytest_evidence(self):
        repo = self.projects / "python-example"
        committed_project(repo, {"pyproject.toml": "[project]\nname = 'fixture'\n",
                                 "tests/test_simple.py": "import unittest\n"})
        self.assertEqual([item["command"] for item in test_options(repo)], ["python3 -m unittest discover -s tests -v"])
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        self.assertEqual([item["command"] for item in test_options(repo)],
                         ["python3 -m pytest -q", "python3 -m unittest discover -s tests -v"])

    def test_unrecognized_runner_is_not_offered_as_an_automatic_check(self):
        repo = self.projects / "go-example"
        committed_project(repo, {"go.mod": "module fixture.example/sample\n\ngo 1.22\n"})
        self.assertEqual(test_options(repo), [])

    def test_sample_is_real_committed_and_does_not_overwrite_owner_edits(self):
        sample = self.catalog.create_sample()
        repo = Path(sample["project"]["path"])
        original_commit = gitops.git(repo, "rev-parse", "HEAD")
        proc = subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=repo,
                              env=gitops.minimal_env(), capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Ran 3 tests", proc.stderr)
        self.assertIn("normalize_label", sample["suggested_task"]["task"])
        with open(repo / "README.md", "a") as handle:
            handle.write("\nOwner addition stays.\n")
        reopened = self.catalog.create_sample()
        self.assertEqual(sample["project"]["id"], reopened["project"]["id"])
        self.assertIn("Owner addition stays.", (repo / "README.md").read_text())
        self.assertEqual(original_commit, gitops.git(repo, "rev-parse", "HEAD"))
        self.assertEqual(self.catalog.inspect(sample["project"]["id"])["kind"], "sample")

    def test_interrupted_sample_creation_is_retained_and_next_attempt_can_proceed(self):
        partial = self.catalog.samples / "label-workshop"
        partial.mkdir(parents=True)
        (partial / "owner-note.txt").write_text("Retain this unfinished attempt.\n")
        gitops.git(partial, "init", "--initial-branch=main")
        sample = self.catalog.create_sample()
        self.assertNotEqual(Path(sample["project"]["path"]), partial)
        self.assertEqual((partial / "owner-note.txt").read_text(), "Retain this unfinished attempt.\n")
        self.assertTrue((partial / ".git").is_dir())


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="swarm-guided-setup-evidence-"))
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.registry = ProviderRegistry(self.root)
        self.setup = WorkbenchSetup(self.root, self.registry)

    def tearDown(self):
        self.env.stop()

    def keys(self):
        self.registry.set_account_keys({"glm": "fixture-glm-account", "deepseek": "fixture-deepseek-account", "minimax": "fixture-minimax-account"})

    def test_shared_glm_key_stays_in_memory_and_setup_survives_without_keys(self):
        self.keys()
        self.assertEqual(self.registry.resolve_key("architect"), "fixture-glm-account")
        self.assertEqual(self.registry.resolve_key("auditor"), "fixture-glm-account")
        status = self.setup.status()
        self.assertTrue(status["ready"])
        self.assertFalse(status["verified"])
        self.assertEqual(status["accounts"][0]["status"], "unchecked")
        self.setup.complete()
        reopened = WorkbenchSetup(self.root, ProviderRegistry(self.root))
        self.assertTrue(reopened.status()["completed"])
        self.assertFalse(reopened.status()["ready"])
        for path in self.root.glob("*.json"):
            self.assertNotIn("fixture-glm-account", path.read_text())
        self.assertNotIn("fixture-glm-account", json.dumps(self.registry.public_configs()))

    def test_invalid_second_account_never_partially_changes_first(self):
        self.keys()
        with self.assertRaises(ConfigurationError):
            self.registry.set_account_keys({"glm": "new-fixture-account", "deepseek": "bad\nkey"})
        self.assertEqual(self.registry.resolve_key("architect"), "fixture-glm-account")

    def test_account_key_is_never_sent_to_a_custom_provider_host(self):
        self.keys()
        self.registry.configure("lead", {"base_url": "https://custom.example/v1", "model_id": "custom-model"})
        with self.assertRaises(ConfigurationError):
            self.registry.resolve_key("lead")
        self.setup.apply_routing("smart")
        self.assertEqual(self.registry.resolve_key("lead"), "fixture-deepseek-account")
        self.assertEqual(self.registry.get_config("architect")["base_url"], ZAI_CODING_BASE)
        self.assertEqual(self.registry.get_config("architect")["effort"], "max")

    def test_smart_and_manual_never_call_models_and_report_missing_accounts(self):
        with patch("swarm.providers.LLMClient.complete", side_effect=AssertionError("Routing must not call a model.")):
            preview = self.setup.routing("smart")
            self.assertFalse(preview["ready"])
            self.assertEqual(preview["missing_roles"], list(CORE_ROLES))
            self.keys()
            self.registry.configure("lead", {"effort": "max"})
            manual = self.setup.apply_routing("manual")
            self.assertEqual(manual["assignments"][1]["effort"], "max")
            smart = self.setup.apply_routing("smart")
            self.assertEqual(smart["assignments"][1]["effort"], "high")
            self.assertTrue(smart["ready"])
            self.assertNotIn("confidence", json.dumps(smart))

    def test_failed_check_does_not_count_as_ready_and_clear_setting_change_resets_it(self):
        self.keys()
        self.registry.record_check("lead", False)
        self.assertFalse(self.setup.status()["ready"])
        self.assertEqual(self.setup.status()["failed_roles"], ["lead"])
        with self.assertRaisesRegex(ValueError, "Builder"):
            self.setup.complete()
        self.registry.set_account_keys({"deepseek": "replacement-fixture-account"})
        self.assertTrue(self.setup.status()["ready"])
        self.assertFalse(self.setup.status()["verified"])

    def test_router_cannot_partially_apply_an_invalid_model_endpoint(self):
        before = self.registry.public_configs()
        with self.assertRaises(ConfigurationError):
            self.registry.configure_many({"lead": {"effort": "max"}, "architect": {"base_url": "https://open.bigmodel.cn/api/paas/v4"}})
        self.assertEqual(before, self.registry.public_configs())
        self.assertEqual(model_catalog()["models"][0]["base_url"], ZAI_CODING_BASE)


class GuidedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="swarm-guided-http-evidence-"))
        self.web = self.root / "web"
        (self.web / "help").mkdir(parents=True)
        (self.web / "index.html").write_text("<title>Workbench fixture</title>")
        (self.web / "help" / "index.html").write_text("<title>Help fixture</title>")
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.app = Application(self.root / "state", self.web, "fixture-access", base_path="/swarm", project_roots=[])
        self.server = create_server(self.app, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.app.shutdown()
        self.env.stop()

    def request(self, path, method="GET", body=None, authorized=True):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer fixture-access"
        req = urllib.request.Request(self.base + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as response:
            return response.code, response.read(), response.headers

    def test_prefixed_routes_keep_auth_and_serve_real_help(self):
        self.assertEqual(self.request("/swarm/api/projects", authorized=False)[0], 401)
        self.assertEqual(self.request("/swarm/help/", authorized=False)[1], b"<title>Help fixture</title>")
        status, body, _ = self.request("/swarm/api/health", authorized=False)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["base_path"], "/swarm")
        self.assertEqual(self.request("/api/setup")[0], 200)  # Proxy may strip the prefix.
        self.assertEqual(self.request("/swarm/../../state/setup.json")[0], 404)

    def test_guided_flow_prepares_real_task_using_ids_without_starting_models(self):
        status, body, _ = self.request("/swarm/api/projects/sample", "POST", {})
        self.assertEqual(status, 201, body)
        sample = json.loads(body)
        status, body, _ = self.request("/swarm/api/setup/accounts", "PUT", {
            "glm": "fixture-glm-account", "deepseek": "fixture-deepseek-account", "minimax": "fixture-minimax-account"})
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["setup"]["ready"])
        self.assertEqual(self.request("/swarm/api/router/apply", "POST", {"mode": "smart"})[0], 200)
        self.assertEqual(self.request("/swarm/api/setup/complete", "POST", {})[0], 200)
        request = {"project_id": sample["project"]["id"], "test_choice": sample["suggested_task"]["test_choice"],
                   "routing_mode": "smart", "task": sample["suggested_task"]["task"]}
        with patch.object(self.app, "start") as start:
            status, body, _ = self.request("/swarm/api/runs", "POST", request)
            self.assertEqual(status, 201, body)
            run = json.loads(body)["run"]
            start.assert_called_once_with(run["id"])
        self.assertEqual(run["test_command"], "python3 -m unittest discover -s tests -v")
        self.assertEqual(run["repo_path"], sample["project"]["path"])
        self.assertEqual(len(run["model_assignments"]), 4)
        self.assertEqual(run["model_calls"], 0)
        self.assertNotIn("fixture-glm-account", body.decode())

    def test_stale_test_choice_and_shell_command_are_rejected_before_model_calls(self):
        sample = self.app.projects.create_sample()
        request = {"project_id": sample["project"]["id"], "task": "A small change", "test_choice": "t_invalid"}
        self.assertEqual(self.request("/swarm/api/runs", "POST", request)[0], 400)
        request.update(test_choice="custom", test_command="python3 -m unittest; echo bad")
        self.assertEqual(self.request("/swarm/api/runs", "POST", request)[0], 400)
        self.assertEqual(self.app.store.list_runs(), [])

    def test_active_task_blocks_account_model_and_route_changes(self):
        future = Future()
        self.app._future = future
        try:
            for path, method, body in (("/api/setup/accounts", "PUT", {"glm": "fixture-new-key"}),
                                       ("/api/providers/lead", "PUT", {"effort": "max"}),
                                       ("/api/router/apply", "POST", {"mode": "smart"}),
                                       ("/api/providers/check-core", "POST", {})):
                status, data, _ = self.request(path, method, body)
                self.assertEqual(status, 400, data)
                self.assertIn("already active", data.decode())
            self.assertFalse(json.loads(self.request("/api/setup")[1])["can_change_settings"])
        finally:
            future.set_result(None)

    def test_optional_router_change_keeps_smart_but_core_change_selects_manual(self):
        self.assertEqual(self.app.setup.saved["routing_mode"], "smart")
        core_before = {role: self.app.registry.get_config(role) for role in CORE_ROLES}
        status, body, _ = self.request("/api/providers/router", "PUT", {"enabled": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.app.setup.saved["routing_mode"], "smart")
        self.assertEqual(core_before, {role: self.app.registry.get_config(role) for role in CORE_ROLES})
        status, body, _ = self.request("/api/providers/lead", "PUT", {"effort": "max"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.app.setup.saved["routing_mode"], "manual")

    def test_resume_records_changed_roles_and_preserves_prior_evidence(self):
        sample = self.app.projects.create_sample()
        self.app.save_accounts({"glm": "fixture-glm-account", "deepseek": "fixture-deepseek-account", "minimax": "fixture-minimax-account"})
        with patch.object(self.app, "start"):
            initial = self.app.create_task({"project_id": sample["project"]["id"], "task": "A small fixture change",
                                            "test_choice": sample["suggested_task"]["test_choice"], "routing_mode": "smart"})
        self.app.store.save_artifact(initial["id"], "retained.patch", "Exact prior proposal\n")
        self.app.store.update_run(initial["id"], status="paused", checkpoint="plan_approved")
        previous_events = self.app.store.events(initial["id"])
        self.app.update_provider("lead", {"model_id": "deepseek-fixture", "effort": "max", "timeout_seconds": 180})
        with patch.object(self.app, "start") as start:
            status, body, _ = self.request(f"/api/runs/{initial['id']}/resume", "POST", {})
            self.assertEqual(status, 200, body)
            start.assert_called_once_with(initial["id"])
        resumed = json.loads(body)["run"]
        self.assertEqual(resumed["routing_mode"], "manual")
        self.assertEqual(resumed["model_settings"]["lead"]["timeout_seconds"], 180)
        self.assertEqual(next(item for item in resumed["model_assignments"] if item["role"] == "lead")["model_id"], "deepseek-fixture")
        self.assertEqual(resumed["checkpoint"], "plan_approved")
        self.assertEqual(self.app.store.read_artifact(initial["id"], "retained.patch"), "Exact prior proposal\n")
        events = self.app.store.events(initial["id"])
        self.assertEqual(events[:len(previous_events)], previous_events)
        changes = [event for event in events if event["kind"] == "routing_changed"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["detail"]["changed_roles"], ["lead"])
        self.assertEqual(changes[0]["detail"]["previous_assignments"], initial["model_assignments"])
        self.assertEqual(changes[0]["detail"]["previous_settings"], initial["model_settings"])
        self.assertNotIn("fixture-glm-account", json.dumps(events))
        self.assertNotIn("fixture-deepseek-account", json.dumps(events))
        # A new connection-check timestamp is not a model-settings change.
        self.app.registry.record_check("lead", True)
        self.app.store.update_run(initial["id"], status="paused")
        with patch.object(self.app, "start"):
            self.app.control(initial["id"], "resume")
        self.assertEqual(len([event for event in self.app.store.events(initial["id"]) if event["kind"] == "routing_changed"]), 1)

    def test_failed_resume_submission_does_not_rewrite_assignment_history(self):
        run = self.app.store.create_run({"task": "Fixture", "repo_path": str(self.root), "routing_mode": "smart",
                                         "model_assignments": self.app.setup.routing("smart")["assignments"],
                                         "model_settings": self.app._model_settings()})
        self.app.store.update_run(run["id"], status="paused")
        before = self.app.store.get_run(run["id"])
        self.app.update_provider("lead", {"effort": "max"})
        with patch.object(self.app, "start", side_effect=RuntimeError("fixture scheduling failure")):
            with self.assertRaisesRegex(RuntimeError, "fixture scheduling failure"):
                self.app.control(run["id"], "resume")
        after = self.app.store.get_run(run["id"])
        for field in ("status", "routing_mode", "model_assignments", "model_settings"):
            self.assertEqual(after[field], before[field])
        self.assertEqual(self.app.store.events(run["id"]), [])

    def test_explicit_check_all_reports_actual_local_provider_results(self):
        observed = []

        class ProviderFixture(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append(request["model"])
                failure = request["model"] == "fixture-scout"
                data = {"error": {"message": "fixture failure"}} if failure else {
                    "model": request["model"], "choices": [{"message": {"content": "READY"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}
                raw = json.dumps(data).encode()
                self.send_response(503 if failure else 200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        fixture = ThreadingHTTPServer(("127.0.0.1", 0), ProviderFixture)
        thread = threading.Thread(target=fixture.serve_forever, daemon=True)
        thread.start()
        try:
            for role in CORE_ROLES:
                self.app.update_provider(role, {"model_id": "fixture-" + role,
                                               "base_url": "http://127.0.0.1:" + str(fixture.server_port) + "/v1",
                                               "api_key": "fixture-account-value"})
            self.assertEqual(observed, [])
            status, body, _ = self.request("/api/providers/check-core", "POST", {})
            self.assertEqual(status, 200, body)
            result = json.loads(body)
            self.assertFalse(result["ok"])
            self.assertEqual(sorted(observed), ["fixture-" + role for role in sorted(CORE_ROLES)])
            self.assertFalse(result["results"]["scout"]["ok"])
            self.assertTrue(result["results"]["architect"]["ok"])
            self.assertEqual(result["results"]["lead"]["usage"]["total_tokens"], 11)
            self.assertEqual(result["setup"]["failed_roles"], ["scout"])
            self.assertFalse(result["setup"]["ready"])
            self.assertNotIn("fixture-account-value", body.decode())
        finally:
            fixture.shutdown()
            fixture.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
