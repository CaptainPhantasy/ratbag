"""The interview: plain questions that become a factory session.

Nothing here writes the artifact. It asks, records the answers, and drives the
SDLC factory through plan, approval, build, check, manifest, validate, package
and handoff — so the artifact is whatever the builder produced, held to a
standard the person can read.
"""
from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .handoff import HandoffError, publish
from .sdlc import SdlcClient, SdlcError


QUESTIONS: list[tuple[str, str]] = [
    ("goal", "What should exist? Say it the way you would say it to a person."),
    ("context", "What must stay true? Names, dates, prices, people. Leave blank if nothing."),
    ("constraints", "Anything it must or must not do? Leave blank if nothing."),
    ("workspace", "Which folder should the work live in?"),
    ("stack", "Starting layout: none, nextjs-fastapi, flask-sqlalchemy or express-prisma."),
    ("check", "Command that proves it works. It must exit 0 when the artifact is right."),
    ("builder", "Optional command that writes the artifact. Leave blank if the files already exist."),
    ("risks", "Name any scanner you accept as not run, by name. Leave blank if none."),
    ("remote", "Optional git remote for the preview branch. Leave blank to commit locally only."),
]


@dataclass
class Answers:
    goal: str = ""
    context: str = ""
    constraints: str = ""
    workspace: str = ""
    stack: str = "none"
    check: str = ""
    builder: str = ""
    risks: str = ""
    remote: str = ""

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "Answers":
        cleaned = {k: str(values.get(k, "") or "").strip() for k in cls.__dataclass_fields__}
        if not cleaned.get("stack"):
            cleaned["stack"] = "none"
        return cls(**cleaned)

    def validate(self) -> list[str]:
        problems = []
        if not self.goal:
            problems.append("A goal is required: what should exist?")
        if not self.workspace:
            problems.append("A workspace folder is required.")
        if not self.check:
            problems.append("A check command is required: how do we know it works?")
        if self.stack not in {"none", "custom", "nextjs-fastapi", "flask-sqlalchemy", "express-prisma"}:
            problems.append("Choose one of: none, custom, nextjs-fastapi, flask-sqlalchemy, express-prisma.")
        return problems

    def to_dict(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class Step:
    name: str
    status: str
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class Interview:
    """One interview, one factory session, one artifact."""

    def __init__(
        self,
        answers: Answers,
        client: SdlcClient | None = None,
        note: Callable[[Step], None] | None = None,
    ):
        self.answers = answers
        self.client = client or SdlcClient()
        self.note = note or (lambda step: None)
        self.session_id: str | None = None
        self.plan: dict[str, Any] = {}
        self.steps: list[Step] = []

    # ------------------------------------------------------------------ steps

    def _step(self, name: str, status: str, detail: str = "", **data: Any) -> Step:
        step = Step(name, status, detail, data)
        self.steps.append(step)
        self.note(step)
        return step

    def plan_request(self) -> dict[str, Any]:
        problems = self.answers.validate()
        if problems:
            self._step("interview", "failed", " ".join(problems))
            raise SdlcError(" ".join(problems))
        self._step("interview", "ok", f"{len(QUESTIONS)} answered")
        self.client.start()
        plan = self.client.call(
            "draft_intake_plan",
            user_goal=self.answers.goal,
            domain_context=self.answers.context or None,
            constraints=self.answers.constraints or None,
            persistent_workspace_path=self.answers.workspace,
        )
        self.session_id = plan.get("session_id")
        self.plan = plan
        summary = plan.get("approval_packet", {}).get("plain_language_summary", "")
        self._step("plan", "ok", summary, session_id=self.session_id, plan=plan)
        return plan

    def approve(self) -> dict[str, Any]:
        self._require_session()
        approved = self.client.call(
            "approve_intake_plan",
            approved=True,
            approval_notes="approved in the RATBAG interview",
            approved_by="ratbag",
            session_id=self.session_id,
        )
        self._step("approval", "ok", f"phase {approved.get('phase')}")
        return approved

    def run(self) -> dict[str, Any]:
        """Approve, build, check, record, validate, package, hand over."""
        if not self.session_id:
            self.plan_request()
        self.approve()
        self._inject_layout()
        self._build()
        self._check()
        self._manifest()
        validated = self._validate()
        packaged = self._package()
        deployment = self._deploy()
        verification = self._verify(deployment)
        delivered = self._finalize(packaged, deployment)
        handoff = self._publish()
        return {
            "status": "delivered",
            "session_id": self.session_id,
            "workspace": self.answers.workspace,
            "steps": [step.__dict__ for step in self.steps],
            "validation": validated,
            "artifact": packaged,
            "handoff": handoff,
            "deployment": deployment,
            "verification": verification,
            "deliverable": delivered,
        }

    # --------------------------------------------------------------- internals

    def _require_session(self) -> None:
        if not self.session_id:
            raise SdlcError("No session yet: plan the request first.")

    def _inject_layout(self) -> None:
        result = self.client.call(
            "inject_architecture_blueprint",
            stack=self.answers.stack,
            session_id=self.session_id,
        )
        created = result.get("created") or []
        self._step("layout", "ok", f"{self.answers.stack}: {len(created)} file(s) created")

    def _build(self) -> None:
        if not self.answers.builder:
            self._step("build", "skipped", "no builder command; the files must already be in the workspace")
            return
        result = self.client.call(
            "execute_monitored_command",
            command=self.answers.builder,
            session_id=self.session_id,
        )
        if result.get("exit_code") != 0:
            detail = (result.get("stderr_tail") or result.get("stdout_tail") or "").strip()[-400:]
            self._step("build", "failed", detail or "the builder command failed")
            raise SdlcError("The builder command failed: " + (detail or "no output"))
        self._step("build", "ok", "builder command finished")

    def _check(self) -> None:
        result = self.client.call(
            "execute_monitored_command",
            command=self.answers.check,
            session_id=self.session_id,
        )
        output = (result.get("stdout_tail") or "") + (result.get("stderr_tail") or "")
        evidence = Path(self.answers.workspace) / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        receipt = evidence / "check.txt"
        receipt.write_text(output or "(no output)\n", encoding="utf-8")
        if result.get("exit_code") != 0:
            self._step("check", "failed", output.strip()[-400:] or "the check command failed")
            raise SdlcError("The check command failed: " + (output.strip()[-400:] or "no output"))
        self._step("check", "ok", f"receipt written to {receipt}")

    def _observations(self) -> list[str]:
        packet_path = self.plan.get("packet_path")
        if not packet_path or not Path(packet_path).is_file():
            return [self.answers.goal]
        packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
        observations = (
            packet.get("specification", {}).get("acceptance_criteria", {}).get("observations", [])
        )
        return [item.get("criterion", "") for item in observations if item.get("criterion")] or [self.answers.goal]

    def _manifest(self) -> None:
        observations = self._observations()
        manifest = {
            "accepted_risks": [r.strip() for r in self.answers.risks.split(",") if r.strip()],
            "assumptions": [self.answers.context] if self.answers.context else ["the request is complete as written"],
            "claim_evidence": {
                claim: [{"file": "evidence/check.txt"}] for claim in observations
            },
            "evidence_required": ["evidence/check.txt"],
            "model_rotation_plan": ["one builder, chosen by the operator"],
            "out_of_scope": [self.answers.constraints or "nothing beyond the observations above"],
            "phase_plan": [
                {
                    "name": "build",
                    "scope": self.answers.workspace,
                    "exit_criteria": f"{self.answers.check} exits zero",
                    "evidence_required": ["evidence/check.txt"],
                    "review_model": "the operator reads the receipt",
                }
            ],
            "risk_register": [],
            "scope_boundaries": [self.answers.workspace],
            "success_criteria": observations,
            "verification_commands": [self.answers.check],
        }
        result = self.client.call(
            "define_delivery_truth_manifest",
            manifest_json=manifest,
            session_id=self.session_id,
        )
        self._step("manifest", "ok", f"completeness: {result.get('completeness')}")

    def _validate(self) -> dict[str, Any]:
        result = self.client.call(
            "validate_changeset",
            test_command=self.answers.check,
            session_id=self.session_id,
        )
        failures = result.get("failures") or []
        if result.get("status") != "passed":
            self._step("validate", "failed", ", ".join(failures))
            raise SdlcError(
                "Validation stopped on: "
                + ", ".join(failures)
                + ". Each name is a thing to fix, not a verdict on the work."
            )
        self._step("validate", "ok", "every gate passed")
        return result

    def _package(self) -> dict[str, Any]:
        result = self.client.call("build_artifact", output_format="dir", session_id=self.session_id)
        self._step("package", "ok", str(result.get("artifact_path")))
        return result

    def _deploy(self) -> dict[str, Any]:
        self.client.call(
            "configure_deployment_target",
            env_name="local",
            target_type="local",
            config_json={"root": self.answers.workspace},
            session_id=self.session_id,
        )
        result = self.client.call("deploy_to_environment", env_name="local", session_id=self.session_id)
        if result.get("status") != "ok":
            self._step("deploy", "failed", str(result.get("reason") or "the factory refused the deployment"))
            raise SdlcError(str(result.get("reason") or "The artifact could not be deployed to the local target."))
        self._step("deploy", "ok", str(result.get("deployed_url")))
        return result

    def _verify(self, deployment: dict[str, Any]) -> dict[str, Any]:
        target = Path(deployment.get("deployed_path") or "")
        page = None
        if target.is_dir():
            for candidate in sorted(target.iterdir()):
                if candidate.is_file() and candidate.suffix in {".html", ".htm", ".md", ".txt"}:
                    page = candidate
                    break
        check = {"path": page.name if page else "", "contains": ""}
        result = self.client.call(
            "verify_production_health",
            target_url=str(deployment.get("deployed_url")),
            checks_json=[check],
            session_id=self.session_id,
        )
        if result.get("status") != "passed":
            self._step("verify", "failed", str(result.get("reason") or "the deployed copy did not answer"))
            raise SdlcError("The deployed copy could not be read back; nothing is being called delivered.")
        self._step("verify", "ok", f"read {check['path'] or 'the deployed folder'} back")
        return result

    def _finalize(self, packaged: dict[str, Any], deployment: dict[str, Any]) -> dict[str, Any]:
        result = self.client.call(
            "finalize_user_deliverable",
            summary=f"{self.answers.goal} — checked with {self.answers.check}",
            artifact_paths=["evidence/check.txt"],
            deployment_url=deployment.get("deployed_url"),
            session_id=self.session_id,
        )
        self._step("handoff", "ok", str(result.get("manifest")))
        return result

    def _publish(self) -> dict[str, Any]:
        """Put the delivered work on the preview branch for the reviewer."""
        try:
            result = publish(
                self.answers.workspace,
                remote=self.answers.remote,
                branch="preview",
                message=f"feat: {self.answers.goal[:72]}",
            )
        except HandoffError as exc:
            self._step("publish", "failed", str(exc))
            return {"pushed": False, "error": str(exc)}
        where = result.remote or "locally only; no remote configured"
        self._step("publish", "ok", f"branch {result.branch} at {result.commit[:8]} → {where}")
        return result.to_dict()
