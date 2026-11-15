"""Evidence reporting must preserve unsuccessful checks and discovery gaps."""

import subprocess
import unittest
from unittest.mock import patch

from integration.run_checks import run_check


class EvidenceReportingTests(unittest.TestCase):
    def test_failed_command_is_preserved(self):
        result = subprocess.CompletedProcess(["check"], 1, "", "failure detail")
        with patch("integration.run_checks.subprocess.run", return_value=result):
            record = run_check(["check"])
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["returncode"], 1)
        self.assertEqual(record["stderr"], "failure detail")

    def test_missing_executable_and_timeout_are_failures(self):
        for error in (FileNotFoundError("missing check"), subprocess.TimeoutExpired(["check"], 180)):
            with self.subTest(error=error), patch("integration.run_checks.subprocess.run", side_effect=error):
                self.assertEqual(run_check(["check"])["status"], "FAIL")

    def test_empty_or_skipped_discovery_cannot_pass(self):
        for output in ("Ran 0 tests\nOK", "Ran 5 tests\nOK (skipped=1)", "no test report"):
            with self.subTest(output=output):
                result = subprocess.CompletedProcess(["check"], 0, "", output)
                with patch("integration.run_checks.subprocess.run", return_value=result):
                    self.assertEqual(run_check(["check"], is_test_suite=True)["status"], "BLOCKED")

    def test_successful_discovery_records_count(self):
        result = subprocess.CompletedProcess(["check"], 0, "", "Ran 3 tests in 0.1s\nOK")
        with patch("integration.run_checks.subprocess.run", return_value=result):
            record = run_check(["check"], is_test_suite=True)
        self.assertEqual((record["status"], record["tests_run"]), ("PASS", 3))
