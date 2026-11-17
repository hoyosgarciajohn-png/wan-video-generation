"""Known immutable model profiles; caller-supplied model identifiers are not paths."""
import json
from pathlib import Path

from .common import LOCK, require


def model_lock(profile):
    if profile == LOCK['profile']:
        return LOCK
    path = Path(__file__).with_name('singing-model.lock.json')
    require(path.is_file(), 'Singing checkpoint has not been pinned')
    lock = json.loads(path.read_text())
    require(profile == lock['profile'], 'Unsupported model revision')
    return lock


def singing_profile():
    return json.loads(Path(__file__).with_name('singing-model.lock.json').read_text())['profile']
