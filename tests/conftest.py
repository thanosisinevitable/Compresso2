from pathlib import Path
import sys
import threading
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from common import Cancelled


class TestJob:
    def __init__(self, directory):
        self.directory = directory
        self.cancelled = threading.Event()
        self.updates = []

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def progress(self, message, current=0, total=0):
        self.check()
        self.updates.append((message, current, total))


@pytest.fixture
def job(tmp_path):
    directory = tmp_path / 'work'
    directory.mkdir()
    return TestJob(directory)
