"""Bounded startup race handling with a synthetic clock; no transport calls."""
import signal
import unittest
from unittest.mock import Mock, patch

from workers.gpu.cli import stop_worker, wait_for_claim
from workers.gpu.client import WorkerAPIError


class ClaimWaitTests(unittest.TestCase):
    def clock(self):
        now = [0.0]
        def sleep(seconds):
            now[0] += seconds
        return now, sleep

    def test_empty_then_ready_returns_first_assignment(self):
        now, sleep = self.clock()
        claim = {'attempt':'fictional'}
        client = Mock(); client.claim.side_effect = [None, None, claim]
        with patch('workers.gpu.cli.time.monotonic', side_effect=lambda:now[0]), patch('workers.gpu.cli.time.sleep', side_effect=sleep):
            self.assertIs(wait_for_claim(client,60,2),claim)
        self.assertEqual(client.claim.call_count,3)
        self.assertEqual(now[0],4)

    def test_polls_stop_at_deadline_without_last_request(self):
        now, sleep = self.clock()
        client = Mock(); client.claim.return_value = None
        with patch('workers.gpu.cli.time.monotonic', side_effect=lambda:now[0]), patch('workers.gpu.cli.time.sleep', side_effect=sleep):
            self.assertIsNone(wait_for_claim(client,5,2))
        self.assertEqual(now[0],5)
        self.assertEqual(client.claim.call_count,3)

    def test_default_zero_wait_never_sleeps(self):
        client=Mock();client.claim.return_value=None
        with patch('workers.gpu.cli.time.sleep') as sleep:
            self.assertIsNone(wait_for_claim(client,0,2))
        sleep.assert_not_called();client.claim.assert_called_once_with()

    def test_auth_and_ambiguous_transport_errors_are_not_retried(self):
        for status in (401,403,409,503):
            client=Mock();client.claim.side_effect=WorkerAPIError(status)
            with patch('workers.gpu.cli.time.sleep') as sleep:
                with self.assertRaises(WorkerAPIError):wait_for_claim(client,60,2)
            client.claim.assert_called_once_with();sleep.assert_not_called()

    def test_nonfinite_and_unbounded_configuration_rejected_before_claim(self):
        for wait,poll in ((121,2),(-1,2),(float('nan'),2),(float('inf'),2),(60,0),(60,11),(60,float('nan'))):
            client=Mock()
            with self.assertRaises(ValueError):wait_for_claim(client,wait,poll)
            client.claim.assert_not_called()

    def test_sigterm_interrupts_wait_immediately(self):
        client=Mock();client.claim.return_value=None
        with patch('workers.gpu.cli.time.sleep', side_effect=lambda _:stop_worker(signal.SIGTERM,None)):
            with self.assertRaises(SystemExit) as error:wait_for_claim(client,60,2)
        self.assertEqual(error.exception.code,143)
        client.claim.assert_called_once_with()

    def test_slow_empty_reply_does_not_extend_window(self):
        now=[0.0]
        def claim():
            now[0]=8
            return None
        client=Mock();client.claim.side_effect=claim
        with patch('workers.gpu.cli.time.monotonic', side_effect=lambda:now[0]), patch('workers.gpu.cli.time.sleep') as sleep:
            self.assertIsNone(wait_for_claim(client,5,2))
        sleep.assert_not_called();client.claim.assert_called_once_with()
