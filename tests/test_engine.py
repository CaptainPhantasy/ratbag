import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from swarm.engine import SwarmEngine, failure_signature, parse_review, test_evidence
from swarm.store import RunStore
from swarm import gitops, sandbox
from test_gitops import fixture_repo, value_patch


APPROVED = json.dumps({"approved": True, "summary": "The supplied evidence supports proceeding.", "issues": []})
REJECTED = json.dumps({"approved": False, "summary": "The requested behavior is not yet satisfied.", "issues": ["Correct the requested behavior before proceeding."]})


class FixtureRegistry:
    def __init__(self, missing=None, router=False):
        self.missing = missing
        self.router = router

    def resolve_key(self, role):
        if role == self.missing:
            raise RuntimeError("Add the missing " + role + " key.")
        return "offline-fixture-key-never-sent"

    def get_config(self, role):
        return {"enabled": self.router if role == "router" else True}


class FixtureClient:
    def __init__(self, patches=None, plan_reviews=None, final_reviews=None, audit_reviews=None, callback=None):
        self.patches = patches or [value_patch()]
        self.plan_reviews = list(plan_reviews or [APPROVED])
        self.final_reviews = list(final_reviews or [APPROVED])
        self.audit_reviews = list(audit_reviews or [APPROVED])
        self.callback = callback
        self.calls = []
        self.patch_count = 0
        self.plan_count = 0
        self.final_count = 0
        self.closed = 0

    async def complete(self, role, system, prompt):
        self.calls.append((role, system, prompt))
        if role == "scout":
            text = "app.py contains value(); tests/test_value.py verifies it."
        elif role == "lead" and "Draft a concise" in system:
            self.plan_count += 1
            text = "Change app.py value() to return 2, preserve unrelated source, and run the existing unittest suite."
        elif role == "lead":
            text = self.patches[min(self.patch_count, len(self.patches) - 1)]
            self.patch_count += 1
        elif role == "architect" and prompt.startswith("Review this plan"):
            text = self.plan_reviews.pop(0) if len(self.plan_reviews) > 1 else self.plan_reviews[0]
        elif role == "architect" and prompt.startswith("Final review"):
            self.final_count += 1
            text = self.final_reviews.pop(0) if len(self.final_reviews) > 1 else self.final_reviews[0]
        elif role == "auditor":
            text = self.audit_reviews.pop(0) if len(self.audit_reviews) > 1 else self.audit_reviews[0]
        elif role == "router":
            text = json.dumps({"command": [sys.executable, "-m", "unittest", "discover", "-s", "tests"], "reason": "The supplied files include unittest tests."})
        else:
            text = APPROVED
        if self.callback:
            self.callback(role, system, prompt)
        return SimpleNamespace(text=text, usage={}, elapsed_ms=0.0, model="offline-fixture")

    async def close(self):
        self.closed += 1


@unittest.skipUnless(sandbox.available(), 'bubblewrap must be installed and usable')
class EngineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.root, self.repo = fixture_repo()
        self.store = RunStore(self.root / "run-data")
        self.run = self.store.create_run({"task": "Change value() to return 2.", "repo_path": str(self.repo), "test_command": sys.executable + " -m unittest discover -s tests -v", "max_attempts": 2, "max_model_calls": 24, "test_timeout": 10})

    def tearDown(self):
        self.store.close()

    async def execute(self, client=None, registry=None):
        client = client or FixtureClient()
        result = await SwarmEngine(self.store, registry or FixtureRegistry(), client).execute(self.run["id"])
        return result, client

    async def test_passing_patch_preserved_and_real_source_supplied(self):
        before = gitops.git(self.repo, "status", "--porcelain=v1", "-z")
        result, client = await self.execute()
        self.assertEqual(result["status"], "ready_for_review", result.get("next_action"))
        patch = self.store.read_artifact(self.run["id"], "final.patch")
        self.assertEqual(hashlib.sha256(patch.encode()).hexdigest(), result["patch_hash"])
        self.assertEqual(result["reviews"]["final"]["patch_hash"], result["patch_hash"])
        self.assertTrue(Path(result["candidate_path"]).is_dir())
        self.assertEqual((self.repo / "app.py").read_text(), "def value():\n    return 1\n")
        self.assertEqual(gitops.git(self.repo, "status", "--porcelain=v1", "-z"), before)
        build_prompt = next(prompt for role, system, prompt in client.calls if role == "lead" and "unified Git diff" in system)
        self.assertIn("def value():\n    return 1", build_prompt)
        self.assertIn("APPROVED PLAN", build_prompt)
        self.assertIn("Ran 1 test", self.store.read_artifact(self.run["id"], result["test_stderr_artifact"]))
        self.assertEqual(result["tests_summary"]["observed_test_count"], 1)
        for role, system, prompt in client.calls:
            if role == "lead":
                self.assertLessEqual(len((system + prompt).encode("utf-8")), 9000)
        self.assertIsNone(result["lead_context"]["token_count"])

    async def test_transport_normalization_preserves_raw_evidence_and_one_canonical_patch(self):
        proposal = value_patch()[:-1]
        fenced_review = "```json\n" + APPROVED + "\n```"
        self.store.update_run(self.run["id"], max_attempts=1)
        result, client = await self.execute(FixtureClient(patches=[proposal], plan_reviews=[fenced_review], audit_reviews=[fenced_review], final_reviews=[fenced_review]))
        self.assertEqual(result["status"], "ready_for_review", result.get("next_action"))
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(client.patch_count, 1)
        self.assertEqual(result["model_calls"], 7)
        self.assertEqual(self.store.artifact_path(self.run["id"], "attempt-1-proposed.patch").read_bytes(), proposal.encode())
        model_responses = [self.store.artifact_path(self.run["id"], artifact["name"]).read_bytes() for artifact in result["artifacts"] if artifact["name"].startswith("model-")]
        self.assertIn(proposal.encode(), model_responses)
        self.assertEqual(model_responses.count(fenced_review.encode()), 3)
        canonical = gitops.git(Path(result["candidate_path"]), "diff", "--cached", "--full-index", "--binary", result["snapshot_commit"])
        self.assertEqual(self.store.artifact_path(self.run["id"], "attempt-1.patch").read_bytes(), canonical)
        self.assertEqual(self.store.artifact_path(self.run["id"], "final.patch").read_bytes(), canonical)
        self.assertEqual(result["patch_hash"], hashlib.sha256(canonical).hexdigest())
        self.assertTrue(result["tests_summary"]["passed"])
        self.assertEqual(result["tests_summary"]["candidate_hash"], result["candidate_hash"])
        for phase in ("audit", "final"):
            self.assertTrue(result["reviews"][phase]["approved"])
            self.assertEqual(result["reviews"][phase]["patch_hash"], result["patch_hash"])
            self.assertEqual(result["reviews"][phase]["candidate_hash"], result["candidate_hash"])
        review_prompts = [prompt for role, _, prompt in client.calls if role == "auditor" or prompt.startswith("Final review")]
        self.assertEqual(len(review_prompts), 2)
        for prompt in review_prompts:
            self.assertIn("COMPLETE PATCH:\n" + canonical.decode(), prompt)
        normalizations = [event["detail"]["normalization"] for event in self.store.events(self.run["id"]) if event["kind"] == "response_normalized"]
        self.assertEqual(normalizations.count("patch_final_newline"), 1)
        self.assertEqual(normalizations.count("json_code_fence"), 3)
        self.assertEqual((self.repo / "app.py").read_bytes(), b"def value():\n    return 1\n")

    async def test_plan_rejection_prevents_build(self):
        self.store.update_run(self.run["id"], max_attempts=1)
        result, client = await self.execute(FixtureClient(plan_reviews=[REJECTED]))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["reviews"]["plan"]["approved"])
        self.assertEqual(client.patch_count, 0)
        self.assertEqual(result["attempt"], 0)

    async def test_final_rejection_prevents_ready_and_preserves_patch(self):
        self.store.update_run(self.run["id"], max_attempts=1)
        result, client = await self.execute(FixtureClient(final_reviews=[REJECTED]))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["reviews"]["final"]["approved"])
        self.assertIn("return 2", self.store.read_artifact(self.run["id"], result["attempt_patch_artifact"]))
        self.assertNotIn("final.patch", {a["name"] for a in result["artifacts"]})

    async def test_malformed_final_review_is_rejection(self):
        self.store.update_run(self.run["id"], max_attempts=1)
        result, _ = await self.execute(FixtureClient(final_reviews=["APPROVED"]))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["reviews"]["final"]["approved"])

    async def test_failed_attempts_record_failure_and_full_output(self):
        result, client = await self.execute(FixtureClient(patches=[value_patch(new=7)]))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(client.patch_count, 2)
        self.assertEqual(client.final_count, 0)
        self.assertIn("AssertionError: 7 != 2", self.store.read_artifact(self.run["id"], "test-1.stderr.txt"))
        self.assertTrue((self.root / "run-data" / "workspaces" / self.run["id"] / "attempt-1").is_dir())
        self.assertEqual(max(result["failure_signatures"].values()), 2)

    async def test_pause_resume_reuses_discovery_and_approved_plan(self):
        def pause_after_plan(role, system, prompt):
            if role == "architect" and prompt.startswith("Review this plan"):
                self.store.update_run(self.run["id"], pause_requested=True)
        client = FixtureClient(callback=pause_after_plan)
        result, _ = await self.execute(client)
        self.assertEqual(result["status"], "paused")
        self.assertTrue(result["plan_approved"])
        self.assertEqual(client.patch_count, 0)
        snapshot = result["snapshot_commit"]
        self.store.update_run(self.run["id"], pause_requested=False)
        client.callback = None
        result, _ = await self.execute(client)
        self.assertEqual(result["status"], "ready_for_review", result.get("next_action"))
        self.assertEqual(result["snapshot_commit"], snapshot)
        self.assertEqual(client.plan_count, 1)
        self.assertEqual(sum(role == "scout" for role, _, _ in client.calls), 2)

    async def test_missing_key_prevents_all_model_requests(self):
        client = FixtureClient()
        result, _ = await self.execute(client, FixtureRegistry(missing="architect"))
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(client.calls, [])
        self.assertEqual(result["model_calls"], 0)

    async def test_pause_after_proposal_reuses_exact_response(self):
        def pause_after_proposal(role, system, prompt):
            if role == "lead" and "unified Git diff" in system:
                self.store.update_run(self.run["id"], pause_requested=True)
        client = FixtureClient(callback=pause_after_proposal)
        result, _ = await self.execute(client)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["candidate_phase"], "proposed")
        self.assertEqual(client.patch_count, 1)
        self.store.update_run(self.run["id"], pause_requested=False)
        client.callback = None
        result, _ = await self.execute(client)
        self.assertEqual(result["status"], "ready_for_review", result.get("next_action"))
        self.assertEqual(client.patch_count, 1)
        self.assertEqual(result["attempt"], 1)

    async def test_lead_required_evidence_over_budget_sends_no_lead_request(self):
        self.store.update_run(self.run["id"], task="Change value() to return 2. " + "x" * 9200)
        result, client = await self.execute()
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(client.plan_count, 0)
        self.assertEqual(client.patch_count, 0)
        self.assertIn("budget", result["next_action"])

    async def test_server_interruption_stops_process_and_keeps_resume_checkpoint(self):
        tests = self.repo / "tests" / "test_value.py"
        tests.write_text("import unittest,time\nclass Slow(unittest.TestCase):\n    def test_wait(self):\n        print('interruption evidence',flush=True)\n        time.sleep(30)\n")
        client = FixtureClient()
        task = asyncio.create_task(SwarmEngine(self.store, FixtureRegistry(), client).execute(self.run["id"]))
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            current = self.store.get_run(self.run["id"])
            if current.get("test_process_pid"):
                break
            await asyncio.sleep(0.05)
        self.assertIsNotNone(current.get("test_process_pid"))
        await asyncio.sleep(0.2)
        self.store.update_run(self.run["id"], interrupt_requested=True)
        result = await asyncio.wait_for(task, 5)
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["candidate_phase"], "saved")
        self.assertEqual(result["tests_summary"]["stopped_reason"], "interrupted")
        self.assertIn("interruption evidence", self.store.read_artifact(self.run["id"], "test-1.stdout.txt"))
        self.assertFalse(result["cancel_requested"])

    async def test_zero_test_output_cannot_be_a_pass(self):
        self.store.update_run(self.run["id"], test_command=sys.executable + " -c \"print('Ran 0 tests in 0s')\"")
        result, client = await self.execute()
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["tests_summary"]["status"], "unknown")
        self.assertEqual(client.final_count, 0)

    async def test_model_keys_not_inherited_by_test_process(self):
        tests = self.repo / "tests" / "test_value.py"
        tests.write_text(tests.read_text() + "\n    def test_minimal_environment(self):\n        import os\n        self.assertIsNone(os.environ.get('DEEPSEEK_API_KEY'))\n")
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-parent-env-value"}):
            result, _ = await self.execute()
        self.assertEqual(result["status"], "ready_for_review", result.get("next_action"))
        self.assertEqual(result["tests_summary"]["observed_test_count"], 2)
        for artifact in result["artifacts"]:
            self.assertNotIn("fixture-parent-env-value", self.store.read_artifact(self.run["id"], artifact["name"]))

    async def test_cancel_stops_real_process_and_retains_output(self):
        tests = self.repo / "tests" / "test_value.py"
        tests.write_text("import unittest\nimport time\nclass Slow(unittest.TestCase):\n    def test_wait(self):\n        print('observed test start', flush=True)\n        time.sleep(30)\n")
        client = FixtureClient()
        task = asyncio.create_task(SwarmEngine(self.store, FixtureRegistry(), client).execute(self.run["id"]))
        deadline = time.monotonic() + 8
        pid = None
        while time.monotonic() < deadline:
            current = self.store.get_run(self.run["id"])
            pid = current.get("test_process_pid")
            if pid:
                break
            await asyncio.sleep(0.05)
        self.assertIsNotNone(pid)
        await asyncio.sleep(0.2)
        self.store.update_run(self.run["id"], cancel_requested=True)
        result = await asyncio.wait_for(task, 5)
        self.assertEqual(result["status"], "cancelled")
        self.assertIn("observed test start", self.store.read_artifact(self.run["id"], "test-1.stdout.txt"))
        self.assertTrue(Path(result["candidate_path"]).is_dir())
        if os.name == "posix":
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    async def test_changed_candidate_source_invalidates_test_pass(self):
        tests = self.repo / "tests" / "test_value.py"
        tests.write_text(tests.read_text() + "\n    def test_mutation(self):\n        from pathlib import Path\n        path = Path('app.py')\n        path.write_text(path.read_text() + '# mutated by test\\n')\n")
        self.store.update_run(self.run["id"], max_attempts=1)
        result, client = await self.execute()
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["tests_summary"]["candidate_unchanged"])
        self.assertEqual(client.final_count, 0)


class EvidenceTests(unittest.TestCase):
    def test_single_whole_json_fence_preserves_review_values(self):
        value = {"approved": True, "summary": "Keep `value.strip()` and the literal \\n sequence unchanged.", "issues": []}
        payload = json.dumps(value)
        for text in (payload, "```json\n" + payload + "\n```", " \r\n```json \r\n" + payload + "\r\n```\t\n"):
            with self.subTest(text=text):
                self.assertEqual(parse_review(text), value)
        self.assertEqual(parse_review("```json\n" + REJECTED + "\n```"), json.loads(REJECTED))

    def test_review_fence_rejects_prose_multiple_objects_and_multiple_fences(self):
        fenced = "```json\n" + APPROVED + "\n```"
        invalid = (
            "Approved:\n" + fenced, fenced + "\nApproved.",
            "Approved:\n" + APPROVED, APPROVED + "\nApproved.",
            APPROVED + "\n" + APPROVED, "```json\n" + APPROVED + "\n" + APPROVED + "\n```",
            fenced + "\n" + fenced, "```json\n" + fenced + "\n```",
            "```json\n" + APPROVED, APPROVED + "\n```",
            "```python\n" + APPROVED + "\n```", "```\n" + APPROVED + "\n```",
            "````json\n" + APPROVED + "\n````", "```json\n" + APPROVED + "```",
            "```json\n" + APPROVED + "\n```\n{}",
        )
        for text in invalid:
            with self.subTest(text=text):
                self.assertFalse(parse_review(text)["approved"])

    def test_fenced_review_schema_and_rejection_gates_stay_strict(self):
        invalid = (
            '{"approved":"true","summary":"ok","issues":[]}',
            '{"approved":true,"summary":"ok","issues":["fix this"]}',
            '{"approved":true,"summary":"ok","issues":[],"extra":"field"}',
            '{"approved":true,"summary":null,"issues":[]}',
            '{"approved":true,"summary":"","issues":[]}',
            '{"approved":true,"summary":"ok","issues":"none"}',
            '{"approved":false,"approved":true,"summary":"ok","issues":[]}',
            '{"approved":true,"summary":"ok","issues":[],}',
            '[{"approved":true,"summary":"ok","issues":[]}]',
        )
        for payload in invalid:
            for text in (payload, "```json\n" + payload + "\n```"):
                with self.subTest(text=text):
                    self.assertFalse(parse_review(text)["approved"])

    def test_review_schema_requires_boolean_and_no_unresolved_issues(self):
        for text in ("APPROVED", '{"approved":"true","summary":"ok","issues":[]}', '{"approved":true,"summary":"ok","issues":["fix this"]}'):
            self.assertFalse(parse_review(text)["approved"])
        self.assertTrue(parse_review(APPROVED)["approved"])

    def test_output_alone_cannot_override_failing_exit(self):
        self.assertFalse(test_evidence("5 passed", 1)["passed"])
        self.assertFalse(test_evidence("all good", 0)["passed"])
        self.assertFalse(test_evidence("Ran 0 tests", 0)["passed"])
        self.assertTrue(test_evidence("Ran 2 tests in 0.002s\nOK", 0)["passed"])

    def test_failure_signature_preserves_distinct_assertions(self):
        self.assertNotEqual(failure_signature("tests", ["pytest"], 1, "AssertionError: 1 != 2"), failure_signature("tests", ["pytest"], 1, "AssertionError: 3 != 4"))
        self.assertEqual(failure_signature("tests", ["pytest"], 1, "AssertionError: 1 != 2\nRan 1 test in 0.012s"), failure_signature("tests", ["pytest"], 1, "AssertionError: 1 != 2\nRan 1 test in 0.876s"))

    def test_empty_secondary_suite_does_not_erase_actual_executed_tests(self):
        output = "test result: ok. 4 passed; 0 failed\nDoc-tests\nrunning 0 tests\ntest result: ok. 0 passed; 0 failed"
        result = test_evidence(output, 0)
        self.assertTrue(result["passed"])
        self.assertEqual(result["observed_test_count"], 4)
        self.assertIn("at least 4", result["message"])


if __name__ == "__main__":
    unittest.main()
