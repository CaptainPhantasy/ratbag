"""The interview drives the factory in a fixed order, and stops on refusal."""
import tempfile
import unittest
from pathlib import Path

from swarm.interview import Answers, Interview
from swarm.sdlc import SdlcError


class FakeClient:
    def __init__(self, fail_validate=False, fail_check=False):
        self.calls = []
        self.fail_validate = fail_validate
        self.fail_check = fail_check
        self.closed = False

    def start(self):
        pass

    def close(self):
        self.closed = True

    def call(self, tool, **arguments):
        self.calls.append((tool, arguments))
        if tool == "draft_intake_plan":
            return {
                "session_id": "session_1",
                "packet_path": None,
                "approval_packet": {"plain_language_summary": "A page with three dates."},
                "specification_preview": "# Specification",
            }
        if tool == "approve_intake_plan":
            return {"phase": "spec_locked"}
        if tool == "inject_architecture_blueprint":
            return {"created": [], "status": "ok"}
        if tool == "execute_monitored_command":
            if self.fail_check and "check.py" in str(arguments.get("command")):
                return {"exit_code": 1, "stdout_tail": "", "stderr_tail": "boom"}
            return {"exit_code": 0, "stdout_tail": "dates: one, two, three\n", "stderr_tail": ""}
        if tool == "define_delivery_truth_manifest":
            return {"completeness": "complete"}
        if tool == "validate_changeset":
            if self.fail_validate:
                return {"status": "failed", "failures": ["tests", "delivery_evidence"]}
            return {"status": "passed", "failures": []}
        if tool == "build_artifact":
            return {"artifact_path": "/tmp/artifact-directory"}
        if tool == "configure_deployment_target":
            return {"status": "ok"}
        if tool == "deploy_to_environment":
            return {"status": "ok", "deployed_url": "file:///tmp/deployed", "deployed_path": "/tmp/deployed"}
        if tool == "verify_production_health":
            return {"status": "passed"}
        if tool == "finalize_user_deliverable":
            return {"manifest": "/tmp/deliverable_manifest.json"}
        return {}


def answers(workspace, **overrides):
    values = {
        "goal": "A page listing three meetings.",
        "context": "December 9, January 13, February 10.",
        "constraints": "",
        "workspace": str(workspace),
        "stack": "none",
        "check": "python3 check.py",
        "builder": "python3 make.py",
        "risks": "security",
    }
    values.update(overrides)
    return Answers.from_mapping(values)


class InterviewTests(unittest.TestCase):
    def test_answers_require_a_goal_workspace_and_check(self):
        problems = Answers.from_mapping({"goal": "", "workspace": "", "check": ""}).validate()
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("goal" in problem.lower() for problem in problems))

    def test_run_walks_the_pipeline_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            result = Interview(answers(tmp), client=client).run()
            tools = [name for name, _ in client.calls]
            self.assertEqual(tools[:3], ["draft_intake_plan", "approve_intake_plan", "inject_architecture_blueprint"])
            self.assertEqual(
                tools[-3:], ["deploy_to_environment", "verify_production_health", "finalize_user_deliverable"]
            )
            self.assertIn("validate_changeset", tools)
            self.assertEqual(result["status"], "delivered")
            self.assertFalse(client.closed, "the caller owns the client's lifetime")

    def test_check_writes_a_receipt_the_manifest_can_point_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient()
            Interview(answers(tmp), client=client).run()
            receipt = Path(tmp) / "evidence" / "check.txt"
            self.assertTrue(receipt.is_file())
            self.assertIn("dates: one, two, three", receipt.read_text(encoding="utf-8"))
            manifest = dict(client.calls)["define_delivery_truth_manifest"]["manifest_json"]
            self.assertEqual(manifest["evidence_required"], ["evidence/check.txt"])
            self.assertEqual(manifest["accepted_risks"], ["security"])
            self.assertEqual(manifest["verification_commands"], ["python3 check.py"])

    def test_validation_failure_stops_before_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient(fail_validate=True)
            with self.assertRaises(SdlcError) as caught:
                Interview(answers(tmp), client=client).run()
            self.assertIn("tests", str(caught.exception))
            self.assertNotIn("build_artifact", [name for name, _ in client.calls])

    def test_a_failed_check_stops_the_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient(fail_check=True)
            with self.assertRaises(SdlcError) as caught:
                Interview(answers(tmp), client=client).run()
            self.assertIn("boom", str(caught.exception))
            self.assertNotIn("define_delivery_truth_manifest", [name for name, _ in client.calls])


if __name__ == "__main__":
    unittest.main()
