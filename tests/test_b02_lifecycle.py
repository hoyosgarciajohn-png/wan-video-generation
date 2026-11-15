import tempfile
import unittest
from pathlib import Path

from services.controller.lifecycle import Lifecycle
from src.wan_platform.fake_provider import FakeGpuProvider


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "wan.sqlite"
        self.provider = FakeGpuProvider()
        self.controller = Lifecycle(self.path, self.provider)
        self.batch = self.controller.admit("project-a", "request-a", {"shot": 1}, 50, 0)

    def status(self):
        return self.controller.status("project-a", self.batch)

    def restart(self):
        self.controller = Lifecycle(self.path, self.provider)

    def test_duplicate_request_and_project_scope(self):
        self.restart()
        self.assertEqual(
            self.controller.admit("project-a", "request-a", {"shot": 1}, 50, 1),
            self.batch,
        )
        with self.assertRaises(ValueError):
            self.controller.admit("project-a", "request-a", {"shot": 2}, 50, 1)
        with self.assertRaises(KeyError):
            self.controller.cancel("project-b", self.batch)

    def test_ambiguous_create_reconciles_after_restart(self):
        self.provider.timeout_after_create = True
        self.controller.provision("project-a", self.batch, 1)
        self.assertEqual(self.status()["state"], "provisioning")
        self.restart()
        self.controller.provision("project-a", self.batch, 2)
        self.assertEqual(self.status()["state"], "rendering")
        self.assertEqual(len(self.provider.find(self.batch, self.batch)), 1)

    def test_cancel_and_failed_delete_are_independent(self):
        self.controller.provision("project-a", self.batch, 1)
        self.controller.cancel("project-a", self.batch)
        self.controller.cancel("project-a", self.batch)
        self.provider.fail_next_delete = True
        self.assertEqual(self.controller.watchdog(2), [self.batch])
        self.assertEqual(self.status()["state"], "canceled")
        self.assertEqual(self.status()["cleanup"], "failed")
        self.restart()
        self.assertEqual(self.controller.watchdog(3), [])
        self.assertEqual(self.status()["cleanup"], "confirmed")
        self.assertEqual(self.provider.find(self.batch, self.batch), [])

    def test_deadline_and_success_preserve_distinct_outcomes(self):
        self.controller.provision("project-a", self.batch, 1)
        self.controller.watchdog(50)
        self.assertEqual(self.status()["state"], "failed")
        self.assertEqual(self.status()["cleanup"], "confirmed")

        other = self.controller.admit("project-a", "request-b", {}, 80, 51)
        self.controller.provision("project-a", other, 52)
        self.controller.finish(other, "succeeded")
        self.controller.watchdog(53)
        row = self.controller.status("project-a", other)
        self.assertEqual((row["state"], row["cleanup"]), ("succeeded", "confirmed"))

    def test_unknown_dispatch_is_not_retried_or_marked_clean(self):
        def timeout_without_observable_pod(*args):
            raise TimeoutError

        self.provider.create = timeout_without_observable_pod
        self.controller.provision("project-a", self.batch, 1)
        self.restart()
        self.controller.provision("project-a", self.batch, 2)
        self.assertEqual(self.status()["state"], "provisioning")
        self.assertEqual(self.controller.watchdog(50), [self.batch])
        self.assertEqual(self.status()["cleanup"], "failed")

    def test_cancel_before_dispatch_and_late_pod_after_timeout(self):
        queued = self.controller.admit("project-a", "request-b", {}, 80, 0)
        self.controller.cancel("project-a", queued)
        self.controller.provision("project-a", queued, 1)
        self.assertEqual(self.provider.find(queued, queued), [])
        self.assertEqual(self.controller.status("project-a", queued)["cleanup"], "confirmed")

        self.provider.timeout_after_create = True
        self.controller.provision("project-a", self.batch, 1)
        self.controller.cancel("project-a", self.batch)
        self.assertEqual(self.controller.watchdog(2), [])
        self.assertEqual(self.status()["cleanup"], "confirmed")
        self.assertEqual(self.provider.find(self.batch, self.batch), [])
