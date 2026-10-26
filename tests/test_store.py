import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from swarm.store import RunStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp(prefix="swarm-store-evidence-"))
        self.store = RunStore(self.path)
        self.run = self.store.create_run({"task": "Fix an example", "repo_path": str(self.path)})

    def tearDown(self):
        self.store.close()

    def test_persistence_and_interrupted_state(self):
        self.store.update_run(self.run["id"], status="running", checkpoint={"plan": "saved"})
        self.store.close()
        self.store = RunStore(self.path)
        self.store.mark_interrupted()
        run = self.store.get_run(self.run["id"])
        self.assertEqual(run["status"], "interrupted")
        self.assertEqual(run["checkpoint"], {"plan": "saved"})

    def test_exact_artifact_and_metadata_survive(self):
        payload = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        self.store.save_artifact(self.run["id"], "attempt-1/candidate.patch", payload)
        self.assertEqual(self.store.read_artifact(self.run["id"], "attempt-1/candidate.patch"), payload)
        self.assertEqual(self.store.get_run(self.run["id"])["artifacts"][0]["size_bytes"], len(payload.encode()))

    def test_evidence_cannot_escape_run(self):
        for name in ("../outside", "/tmp/outside", "test/../../outside", "x\\outside"):
            with self.assertRaises(ValueError):
                self.store.save_artifact(self.run["id"], name, "bad")

    def test_concurrent_events_keep_distinct_ids(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: self.store.add_event(self.run["id"], "test", "worker", str(i)), range(40)))
        events = self.store.events(self.run["id"])
        self.assertEqual(len(events), 40)
        self.assertEqual(len({e["id"] for e in events}), 40)
        self.assertEqual(len(self.store.events(self.run["id"], events[19]["id"])), 20)


if __name__ == "__main__":
    unittest.main()
