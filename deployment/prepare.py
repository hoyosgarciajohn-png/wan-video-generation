"""Prepare external local staging directories and a secret token file; never print tokens."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets


def prepare(directory, owner):
    directory = Path(directory).resolve()
    repository = Path(__file__).resolve().parents[1]
    if directory == repository or repository in directory.parents:
        raise ValueError('State and secrets must be outside the repository/build context')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(directory)) or not owner.strip():
        raise ValueError('Use an absolute directory without spaces/shell characters and a nonempty owner')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = directory / 'state'
    state.mkdir(mode=0o700, exist_ok=True)
    token_file = directory / 'tokens.json'
    if token_file.exists() or (directory / 'compose.env').exists():
        raise ValueError('Existing token file retained; choose another directory or reuse compose.env')
    descriptor = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump({secrets.token_urlsafe(48): owner.strip()}, output)
    environment = directory / 'compose.env'
    environment.write_text(f'WAN_UID={os.getuid()}\nWAN_GID={os.getgid()}\nWAN_STATE_DIR={state}\nWAN_TOKEN_FILE={token_file}\nWAN_PORT=8080\n')
    environment.chmod(0o600)
    return environment


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--owner', required=True)
    args = parser.parse_args()
    print(f'Prepared staging settings: {prepare(args.directory, args.owner)}')
