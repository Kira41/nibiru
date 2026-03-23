from __future__ import annotations

import pathlib
import subprocess
import sys


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'test', '-p', 'test_*.py', '-v']
    completed = subprocess.run(command, cwd=repo_root)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
