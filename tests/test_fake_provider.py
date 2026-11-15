import unittest
from src.wan_platform.fake_provider import FakeGpuProvider


class FakeProviderTests(unittest.TestCase):
    def test_ambiguous_create_is_discoverable(self):
        provider = FakeGpuProvider()
        provider.timeout_after_create = True
        with self.assertRaises(TimeoutError):
            provider.create("batch-1", "request-1")
        self.assertEqual(len(provider.find("batch-1", "request-1")), 1)
        self.assertEqual(provider.find("batch-2", "request-1"), [])

    def test_blind_retry_exposes_duplicate_allocations(self):
        provider = FakeGpuProvider()
        provider.create("batch-1", "request-1")
        provider.create("batch-1", "request-1")
        self.assertEqual(len(provider.find("batch-1", "request-1")), 2)

    def test_failed_delete_preserves_resource_until_retry(self):
        provider = FakeGpuProvider()
        pod = provider.create("batch-1", "request-1")
        provider.fail_next_delete = True
        with self.assertRaises(ConnectionError):
            provider.delete(pod.id)
        self.assertIsNotNone(provider.get(pod.id))
        provider.delete(pod.id)
        self.assertIsNone(provider.get(pod.id))

    def test_repeated_delete_succeeds(self):
        provider = FakeGpuProvider()
        pod = provider.create("batch-1", "request-1")
        provider.delete(pod.id)
        provider.delete(pod.id)
        self.assertEqual(provider.find("batch-1", "request-1"), [])
