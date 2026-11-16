import json
import unittest
from deployment.deadline_guard import validate, terminate_matches
from deployment.cleanup_monitor import CleanupOnlyProvider
from tests.test_live_execution import HTTP


class DeadlineGuardTests(unittest.TestCase):
    def test_deadline_and_binding_are_bounded(self):
        self.assertEqual(validate('["owner", "project"]', 'batch', 2800, 1000), '["owner","project"]')
        for deadline in (1000, 2801):
            with self.assertRaises(ValueError): validate('["owner","project"]', 'batch', deadline, 1000)
        with self.assertRaises(ValueError): validate('[]', 'batch', 2000, 1000)

    def test_only_exact_matching_pod_is_terminated_and_late_create_is_found(self):
        http = HTTP()
        provider = CleanupOnlyProvider('fictional-token', scope='["owner","project"]', transport=http)
        observed = set()
        self.assertFalse(terminate_matches(provider, 'batch', observed))
        http.pods['other'] = {'id': 'other', 'name': 'unrelated-pod'}
        http.pods['mine'] = {'id': 'mine', 'name': provider._name('batch', 'batch')}
        self.assertTrue(terminate_matches(provider, 'batch', observed))
        self.assertEqual(set(http.pods), {'other'})
        self.assertTrue(terminate_matches(provider, 'batch', observed))
        self.assertEqual(http.posts, 0)


if __name__ == '__main__': unittest.main()
