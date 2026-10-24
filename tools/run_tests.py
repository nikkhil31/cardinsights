"""Run the project's pytest suite inside E2B (SQLite backend)."""
import sys

sys.path.insert(0, "/home/user/src")

import pytest

pdf = sys.argv[1]
sys.exit(pytest.main(["-q", "/home/user/tests", f"--pdf={pdf}"]))
