# ai-generated: 80% - Claude Code wrote the tests from my list of cases
"""svcdesk own tests (Stretch S3): wait for /health, run the pytest suite, summarise.

The last stdout line is exactly "ITSMLAB-TESTS: passed=<n> failed=<m>"; the exit code is 0 only when m == 0.
"""

import os
import sys
import time
import urllib.error

import pytest

from svc import call

HERE = os.path.dirname(os.path.abspath(__file__))


class Counter:
    """A pytest plugin counting tests: a test fails if any phase (setup, call, teardown) fails."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed += 1
        elif report.when == "call" and report.passed:
            self.passed += 1

    def pytest_collectreport(self, report):
        if report.failed:  # a module that does not import is a failure, not zero tests
            self.failed += 1


def wait_for_health(seconds=60):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if call("GET", "/health")[0] == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    return False


def main():
    counter = Counter()
    if not wait_for_health():
        print("FAIL service did not become healthy")
        counter.failed += 1
    else:
        args = ["-v", "-p", "no:cacheprovider", "--continue-on-collection-errors", "--rootdir", HERE, HERE]
        code = pytest.main(args, plugins=[counter])
        if code not in (pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED) and counter.failed == 0:
            print(f"FAIL pytest exited with {code!r}")  # usage error, no tests collected, internal error
            counter.failed += 1
    sys.stdout.flush()
    print(f"ITSMLAB-TESTS: passed={counter.passed} failed={counter.failed}", flush=True)
    return 0 if counter.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
