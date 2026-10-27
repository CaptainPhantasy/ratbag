"""Small authenticated, same-origin server for the native workbench."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit, parse_qs

from . import __version__
from .store import RunStore
from .providers import ProviderRegistry, LLMClient, ProviderError, ConfigurationError, model_catalog
from .engine import SwarmEngine
from .projects import ProjectCatalog
from .workbench import WorkbenchSetup, CORE_ROLES
from .interview import QUESTIONS, Answers, Interview
from .sdlc import SdlcClient, SdlcError
from . import gitops

TERMINAL = {"ready_for_review", "failed", "needs_input", "cancelled", "interrupted"}


class Application:
    def __init__(self, data_dir: Path, web_dir: Path, access_token: str = "", allowed_hosts=None,
                 base_path: str = "", project_roots: list[Path] | None = None):
        self.store = RunStore(data_dir)
        self.store.mark_interrupted()
        self.registry = ProviderRegistry(data_dir)
        self.projects = ProjectCatalog(data_dir, roots=project_roots)
        self.setup = WorkbenchSetup(data_dir, self.registry)
        self.web_dir = Path(web_dir).resolve()
        self.access_token = access_token
        self.allowed_hosts = set(allowed_hosts or {"localhost", "127.0.0.1", "::1"})
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="swarm-run")
        self._future = None
        self.running_run_id = None
        self._shutting_down = False
        self._settings_busy = False
        base_path = base_path.strip().rstrip("/")
        if base_path and (not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", base_path) or len(base_path) > 120):
            raise ValueError("Use a simple base path such as /swarm.")
        self.base_path = base_path

    def _check_can_start(self):
        # Call with _lock held, before changing a saved run or submitting work.
        if self._shutting_down:
            raise ValueError("The server is shutting down. Restart it before starting or resuming a task.")
        if self._future and not self._future.done():
            raise ValueError("A task is already active. Pause keeps its place; stop it before starting another.")
        if self._settings_busy:
            raise ValueError("The model connection check is still running. Wait for its results before starting a task.")

    def _check_can_configure(self):
        self._check_can_start()

    def setup_status(self) -> dict:
        with self._lock:
            can_change = not self._shutting_down and not self._settings_busy and not (self._future and not self._future.done())
            return self.setup.status(project_count=len(self.projects.list()["projects"]), can_change_settings=bool(can_change))

    def update_provider(self, role: str, body: dict) -> dict:
        with self._lock:
            self._check_can_configure()
            values = dict(body)
            key = values.pop("api_key", None)
            result = self.registry.update(role, values, key)
            if values and role in CORE_ROLES:
                self.setup.save(routing_mode="manual")
            return result

    def save_accounts(self, body: dict) -> dict:
        with self._lock:
            self._check_can_configure()
            self.registry.set_account_keys(body)
            return self.setup_status()

    def apply_routing(self, body: dict) -> dict:
        if set(body) != {"mode"}:
            raise ValueError("Choose Smart or Manual routing.")
        with self._lock:
            self._check_can_configure()
            router = self.setup.apply_routing(body["mode"])
            return {"router": router, "providers": self.registry.public_configs(), "setup": self.setup_status()}

    def complete_setup(self) -> dict:
        with self._lock:
            self._check_can_configure()
            self.setup.complete()
            return self.setup_status()

    async def _connection_checks(self, roles: tuple[str, ...]) -> dict:
        client = LLMClient(self.registry)

        async def check(role):
            try:
                reply = await client.complete(role, "Connection check. Return only READY.", "Return READY.")
            except ProviderError as exc:
                self.registry.record_check(role, False)
                return {"ok": False, "message": self.redact(str(exc))[:1500], "code": exc.code,
                        "provider_status": exc.http_status}
            self.registry.record_check(role, True, model=reply.model, elapsed_ms=reply.elapsed_ms)
            return {"ok": True, "model": reply.model, "elapsed_ms": reply.elapsed_ms,
                    "message": "The model returned a completed response.", "usage": reply.usage}

        try:
            values = await asyncio.gather(*(check(role) for role in roles))
            return dict(zip(roles, values))
        finally:
            await client.close()

    def check_connections(self, roles: tuple[str, ...] = CORE_ROLES) -> dict:
        with self._lock:
            self._check_can_configure()
            if any(role not in self.registry.public_configs() for role in roles):
                raise ValueError("Unknown model role.")
            self._settings_busy = True
        try:
            results = asyncio.run(self._connection_checks(roles))
        finally:
            with self._lock:
                self._settings_busy = False
        return {"ok": all(value["ok"] for value in results.values()), "results": results, "setup": self.setup_status()}

    def _model_settings(self) -> dict:
        return {role: self.registry.get_config(role) for role in self.registry.public_configs()}

    def _resume_routing_change(self, run: dict) -> dict | None:
        """Record an owner's changed settings without rewriting earlier run evidence."""
        previous_assignments = run.get("model_assignments")
        if not isinstance(previous_assignments, list):
            return None  # Older runs did not save assignment metadata to compare.
        current_settings = self._model_settings()
        previous_settings = run.get("model_settings")
        # Manual preview describes the actual currently saved role settings,
        # without applying a preset or changing the owner's selections.
        current_assignments = self.setup.routing("manual")["assignments"]
        if isinstance(previous_settings, dict):
            changed_roles = [role for role in current_settings if previous_settings.get(role) != current_settings[role]]
        else:
            # Earlier v2 runs saved the assignment list but not every public limit.
            previous_by_role = {item["role"]: item for item in previous_assignments if isinstance(item, dict) and "role" in item}
            compared_fields = ("model_id", "provider", "effort", "enabled")
            changed_roles = [item["role"] for item in current_assignments
                             if any(previous_by_role.get(item["role"], {}).get(field) != item[field] for field in compared_fields)]
        mode = self.setup.saved["routing_mode"]
        if not changed_roles and run.get("routing_mode", mode) == mode:
            return None
        return {"source": "owner_resume", "changed_roles": changed_roles,
                "previous_mode": run.get("routing_mode"), "mode": mode,
                "previous_assignments": previous_assignments, "assignments": current_assignments,
                "previous_settings": previous_settings, "settings": current_settings}

    def start(self, run_id: str):
        with self._lock:
            self._check_can_start()
            future = self._pool.submit(self._execute, run_id)
            self.running_run_id = run_id
            self._future = future

    def _execute(self, run_id: str):
        try:
            asyncio.run(SwarmEngine(self.store, self.registry).execute(run_id))
        except Exception as exc:
            message = self.redact(str(exc))[:1500] or type(exc).__name__
            self.store.update_run(run_id, status="failed", next_action=message)
            self.store.add_event(run_id, "error", "system", message)
        finally:
            with self._lock:
                if self.running_run_id == run_id:
                    self.running_run_id = None

    def redact(self, text: str) -> str:
        result = self.registry.redact(text)
        if self.access_token:
            result = result.replace(self.access_token, "[redacted]")
        return result

    def create_task(self, body: dict) -> dict:
        body = dict(body)
        fields = {"repo_path", "task", "symbol", "test_command", "max_attempts", "max_model_calls", "test_timeout",
                  "project_id", "test_choice", "routing_mode"}
        if set(body) - fields:
            raise ValueError("Unknown task setting: " + ", ".join(sorted(set(body) - fields)))
        task = str(body.get("task", "")).strip()
        repo = str(body.get("repo_path", "")).strip()
        project = None
        if body.get("project_id"):
            project = self.projects.inspect(body["project_id"])
            if repo and str(Path(repo).expanduser().resolve()) != project["path"]:
                raise ValueError("The selected project and entered folder do not match.")
            repo = project["path"]
        if not task or len(task) > 12000:
            raise ValueError("Enter a task between 1 and 12,000 characters.")
        if not repo or len(repo) > 4096 or "\x00" in repo:
            raise ValueError("Choose a repository path on the server.")
        repo_path = Path(repo).expanduser().resolve()
        if not repo_path.is_dir():
            raise ValueError("That repository folder is not available on this server.")
        repo_path = gitops.repository_root(repo_path)
        choice = body.get("test_choice")
        if choice and choice != "custom":
            project = project or self.projects.inspect_path(repo_path)
            option = next((option for option in project["test_options"] if option["id"] == choice), None)
            if option is None:
                raise ValueError("That test choice is no longer available. Inspect the project again.")
            if body.get("test_command") and body["test_command"] != option["command"]:
                raise ValueError("The selected test choice and custom command do not match.")
            body["test_command"] = option["command"]
        mode = body.get("routing_mode", self.setup.saved["routing_mode"])
        if mode not in {"smart", "manual"}:
            raise ValueError("Choose Smart or Manual routing.")
        for field, default, low, high in (("max_attempts", 3, 1, 5), ("max_model_calls", 24, 8, 60),
                                          ("test_timeout", 120, 10, 600)):
            value = body.get(field, default)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{field.replace('_', ' ')} must be between {low} and {high}.")
            body[field] = value
        for field, limit in (("symbol", 300), ("test_command", 1000)):
            if not isinstance(body.get(field, ""), str) or len(body.get(field, "")) > limit:
                raise ValueError(f"{field.replace('_', ' ')} is too long.")
        if body.get("test_command"):
            gitops.parse_test_command(body["test_command"])
        with self._lock:
            self._check_can_start()
            routing = self.setup.routing(mode)
            if not routing["ready"]:
                missing = routing["missing_roles"] + routing["failed_roles"]
                raise ValueError("Review the model connection for: " + ", ".join(missing) + ". Open Models to add or check its key.")
            self.setup.apply_routing(mode)
            body.update(task=task, repo_path=str(repo_path), routing_mode=mode,
                        model_assignments=routing["assignments"], model_settings=self._model_settings())
            run = self.store.create_run(body)
            self.store.add_event(run["id"], "queued", "system", "Task saved and queued.")
            self.store.add_event(run["id"], "routing", "router", routing["explanation"],
                                 {"mode": mode, "assignments": routing["assignments"]})
            self.start(run["id"])
            return self.store.get_run(run["id"])

    def control(self, run_id: str, action: str) -> dict:
        with self._lock:
            run = self.store.get_run(run_id)
            active = self.running_run_id == run_id and self._future and not self._future.done()
            if action == "pause":
                if not active or run["status"] in TERMINAL:
                    raise ValueError("Only an active task can be paused.")
                run = self.store.update_run(run_id, pause_requested=True)
                self.store.add_event(run_id, "control", "owner", "Pause requested. Work will pause at the next safe boundary.")
            elif action == "cancel":
                if run["status"] in {"ready_for_review", "cancelled"}:
                    raise ValueError("This task has already finished.")
                if active:
                    run = self.store.update_run(run_id, cancel_requested=True, pause_requested=False)
                    self.store.add_event(run_id, "control", "owner", "Stop requested. Waiting for the current operation to end.")
                else:
                    run = self.store.update_run(run_id, status="cancelled", cancel_requested=True, pause_requested=False)
                    self.store.add_event(run_id, "cancelled", "owner", "Task stopped. Saved work remains available.")
            elif action == "resume":
                if active:
                    if not run.get("pause_requested") and run["status"] != "paused":
                        raise ValueError("This task is already running.")
                    run = self.store.update_run(run_id, pause_requested=False)
                    self.store.add_event(run_id, "control", "owner", "Resume requested.")
                elif run["status"] in {"interrupted", "paused", "needs_input"}:
                    self._check_can_start()
                    routing_change = self._resume_routing_change(run)
                    previous = {field: run.get(field, False) for field in
                                ("status", "cancel_requested", "pause_requested", "interrupt_requested")}
                    route_fields = {}
                    if routing_change:
                        route_fields = {"routing_mode": routing_change["mode"],
                                        "model_assignments": routing_change["assignments"],
                                        "model_settings": routing_change["settings"]}
                        previous.update({field: run.get(field) for field in route_fields})
                    run = self.store.update_run(run_id, cancel_requested=False, pause_requested=False,
                                                interrupt_requested=False, status="queued", **route_fields)
                    try:
                        self.start(run_id)
                    except Exception:
                        self.store.update_run(run_id, **previous)
                        raise
                    if routing_change:
                        self.store.add_event(run_id, "routing_changed", "router",
                                             "You resumed after changing model settings. New requests use the currently saved roles; earlier plans, patches, and checks remain as recorded.",
                                             routing_change)
                else:
                    raise ValueError("This task cannot be resumed. Create a new task using its saved evidence.")
            else:
                raise ValueError("Unknown task action.")
            return run

    def shutdown(self):
        interrupted_run_id = None
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True
            if self.running_run_id and self._future and not self._future.done():
                run = self.store.get_run(self.running_run_id)
                if not run.get("cancel_requested") and run["status"] not in TERMINAL:
                    interrupted_run_id = run["id"]
                    self.store.update_run(run["id"], interrupt_requested=True, pause_requested=False)
                    self.store.add_event(run["id"], "control", "system",
                                         "Server shutdown requested. Current work will stop with saved evidence available to resume.")
        # The worker needs _lock to finish; never hold it while joining the pool.
        self._pool.shutdown(wait=True, cancel_futures=False)
        if interrupted_run_id:
            run = self.store.get_run(interrupted_run_id)
            if run["status"] not in TERMINAL:
                self.store.update_run(interrupted_run_id, status="interrupted", pause_requested=False,
                                      next_action="Resume to continue from the retained snapshot and completed evidence.")
                self.store.add_event(interrupted_run_id, "interrupted", "system",
                                     "The server stopped. Saved work and evidence remain available to resume.")
        self.store.close()


def make_handler(app: Application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SwarmControl"

        def log_message(self, fmt, *args):
            # Logs contain request method, status, and safe path only; never request bodies or headers.
            return

        def send_data(self, status, content: bytes, content_type="application/json; charset=utf-8", filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{Path(filename).name}"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(content)

        def json_response(self, status, value):
            self.send_data(status, json.dumps(value, allow_nan=False).encode())

        def read_json(self):
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                raise ValueError("Send settings as JSON.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid request size.") from None
            if not 0 <= length <= 65536:
                raise ValueError("Request is too large.")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Expected a settings object.")
            return body

        def check_origin(self):
            host = self.headers.get("Host", "")
            parsed = urlsplit("//" + host)
            if parsed.hostname not in app.allowed_hosts:
                self.json_response(403, {"error": "This server address is not allowed. Configure SWARM_ALLOWED_HOSTS for your chosen address."})
                return False
            origin = self.headers.get("Origin")
            if origin:
                source = urlsplit(origin)
                if source.netloc != host or source.scheme not in {"http", "https"}:
                    self.json_response(403, {"error": "This action must come from the workbench's own page."})
                    return False
            return True

        def authenticated(self, path):
            if not path.startswith("/api/") or path == "/api/health" or not app.access_token:
                return True
            expected = "Bearer " + app.access_token
            given = self.headers.get("Authorization", "")
            if not hmac.compare_digest(given.encode(), expected.encode()):
                self.json_response(401, {"error": "Enter the workbench access key to connect."})
                return False
            return True

        def route(self):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if app.base_path and (path == app.base_path or path.startswith(app.base_path + "/")):
                if path == app.base_path:
                    if not self.check_origin():
                        return
                    self.send_response(308)
                    self.send_header("Location", app.base_path + "/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                path = path[len(app.base_path):]
            if not self.check_origin() or not self.authenticated(path):
                return
            method = self.command
            try:
                if path == "/api/health" and method in {"GET", "HEAD"}:
                    return self.json_response(200, dict(ok=True, version=__version__, auth_required=bool(app.access_token), running_run_id=app.running_run_id, base_path=app.base_path))
                if path == "/api/projects" and method == "GET":
                    return self.json_response(200, app.projects.list())
                if path == "/api/projects/sample" and method == "POST":
                    self.read_json()
                    return self.json_response(201, app.projects.create_sample())
                project_match = re.fullmatch(r"/api/projects/(p_[a-f0-9]{16})", path)
                if project_match and method == "GET":
                    return self.json_response(200, {"project": app.projects.inspect(project_match[1])})
                if path == "/api/projects/inspect" and method == "POST":
                    body = self.read_json()
                    if set(body) != {"repo_path"} or not isinstance(body["repo_path"], str) or not body["repo_path"].strip():
                        raise ValueError("Enter the full project folder on this server.")
                    return self.json_response(200, {"project": app.projects.inspect_path(Path(body["repo_path"]))})
                if path == "/api/models/catalog" and method == "GET":
                    return self.json_response(200, model_catalog())
                if path == "/api/setup" and method == "GET":
                    return self.json_response(200, app.setup_status())
                if path == "/api/setup/accounts" and method == "PUT":
                    return self.json_response(200, {"setup": app.save_accounts(self.read_json())})
                if path == "/api/setup/complete" and method == "POST":
                    self.read_json()
                    return self.json_response(200, {"setup": app.complete_setup()})
                if path == "/api/router" and method == "GET":
                    mode = parse_qs(parsed.query).get("mode", [None])[0]
                    return self.json_response(200, app.setup.routing(mode))
                if path == "/api/router/apply" and method == "POST":
                    return self.json_response(200, app.apply_routing(self.read_json()))
                if path == "/api/providers/check-core" and method == "POST":
                    self.read_json()
                    return self.json_response(200, app.check_connections())
                if path == "/api/providers" and method == "GET":
                    return self.json_response(200, {"providers": app.registry.public_configs()})
                provider = re.fullmatch(r"/api/providers/([a-z]+)(/check)?", path)
                if provider:
                    role = provider[1]
                    if provider[2] and method == "POST":
                        self.read_json()
                        result = app.check_connections((role,))["results"][role]
                        if not result["ok"]:
                            return self.json_response(502, {**result, "error": result["message"]})
                        return self.json_response(200, result)
                    if not provider[2] and method == "PUT":
                        return self.json_response(200, {"provider": app.update_provider(role, self.read_json())})
                if path == "/api/runs" and method == "GET":
                    return self.json_response(200, {"runs": app.store.list_runs()})
                if path == "/api/runs" and method == "POST":
                    return self.json_response(201, {"run": app.create_task(self.read_json())})
                run_match = re.fullmatch(r"/api/runs/(r_[a-f0-9]{16})(?:/(.*))?", path)
                if run_match:
                    run_id, extra = run_match.groups()
                    if extra is None and method == "GET":
                        return self.json_response(200, {"run": app.store.get_run(run_id)})
                    if extra == "events" and method == "GET":
                        after = int(parse_qs(parsed.query).get("after", ["0"])[0])
                        return self.json_response(200, {"events": app.store.events(run_id, after)})
                    if extra and extra.startswith("artifacts/") and method == "GET":
                        name = extra[len("artifacts/"):]
                        content = app.store.read_artifact(run_id, name)
                        return self.send_data(200, content.encode("utf-8"), "text/plain; charset=utf-8")
                    if extra in {"pause", "resume", "cancel"} and method == "POST":
                        self.read_json()
                        return self.json_response(200, {"run": app.control(run_id, extra)})
                if path == "/api/sdlc/status" and method == "GET":
                    return self.json_response(200, SdlcClient().status())
                if path == "/api/interview/questions" and method == "GET":
                    return self.json_response(
                        200, {"questions": [{"key": key, "question": text} for key, text in QUESTIONS]}
                    )
                if path == "/api/interview/plan" and method == "POST":
                    interview = Interview(Answers.from_mapping(self.read_json()))
                    try:
                        plan = interview.plan_request()
                    except SdlcError as exc:
                        return self.json_response(502, {"error": str(exc)})
                    finally:
                        interview.client.close()
                    return self.json_response(200, {"session_id": interview.session_id, "plan": plan})
                if path == "/api/interview/run" and method == "POST":
                    steps: list[dict] = []
                    interview = Interview(
                        Answers.from_mapping(self.read_json()),
                        note=lambda step: steps.append(step.__dict__),
                    )
                    try:
                        result = interview.run()
                    except SdlcError as exc:
                        return self.json_response(502, {"error": str(exc), "steps": steps})
                    finally:
                        interview.client.close()
                    return self.json_response(200, {"result": result, "steps": steps})
                if method not in {"GET", "HEAD"} or path.startswith("/api/"):
                    return self.json_response(404, {"error": "This action was not found."})
                if path == "/wireframe":
                    target = app.web_dir.parent / "docs" / "wireframe.html"
                else:
                    relative = "index.html" if path == "/" else path.lstrip("/")
                    target = (app.web_dir / relative).resolve()
                    if not target.is_relative_to(app.web_dir):
                        return self.json_response(404, {"error": "Page was not found."})
                    if target.is_dir():
                        if not path.endswith("/"):
                            self.send_response(308)
                            self.send_header("Location", app.base_path + path + "/")
                            self.send_header("Content-Length", "0")
                            self.end_headers()
                            return
                        target = (target / "index.html").resolve()
                        if not target.is_relative_to(app.web_dir):
                            return self.json_response(404, {"error": "Page was not found."})
                if not target.is_file():
                    return self.json_response(404, {"error": "Page was not found."})
                return self.send_data(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            except (ValueError, json.JSONDecodeError, ConfigurationError, gitops.GitError) as exc:
                self.json_response(400, {"error": app.redact(str(exc))[:1500]})
            except ProviderError as exc:
                self.json_response(502, {"error": app.redact(str(exc))[:1500], "code": exc.code,
                                         "provider_status": exc.http_status})
            except (KeyError, FileNotFoundError):
                self.json_response(404, {"error": "The requested record was not found."})
            except Exception as exc:
                self.json_response(503, {"error": app.redact(str(exc))[:1500] or "The operation did not complete. Its saved work remains available."})

        do_GET = route
        do_HEAD = route
        do_POST = route
        do_PUT = route

    return Handler


def create_server(app: Application, host: str, port: int):
    if host not in {"127.0.0.1", "localhost", "::1"} and not app.access_token:
        raise ValueError("Set SWARM_ACCESS_TOKEN before listening on a remote address.")
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    return server
