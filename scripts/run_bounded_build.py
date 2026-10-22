"""Bound a CI subprocess and retain a readable tail when Xcode is interrupted.

Stdout goes straight to disk (never accumulated in RAM). Kill the process
GROUP on an overrun to prevent orphaned xcodebuild/Swift compiler children.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def tail(path: Path, limit: int = 120):
    # Efficient line-tail without loading the entire Xcode log into RAM.
    from collections import deque
    with path.open('r', errors='replace') as stream:
        return ''.join(deque(stream, maxlen=limit))


def run(command: list[str], log: Path, timeout_seconds: int) -> int:
    if not command:
        raise ValueError('Missing command')
    log.parent.mkdir(parents=True, exist_ok=True)
    print('[CI_BUILD] bounded command:', command[0], 'time_limit_seconds=', timeout_seconds, flush=True)
    start = time.monotonic()
    with log.open('w') as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = child.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            print('[CI_BUILD] deadline reached: terminating build process group', flush=True)
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            status = 124
    print('[CI_BUILD] exit=', status, 'duration_seconds=', int(time.monotonic() - start),
          'log_bytes=', log.stat().st_size, flush=True)
    if status != 0:
        print('[CI_BUILD] last 120 log lines:', flush=True)
        print(tail(log), flush=True)
    else:
        print('[CI_BUILD] completed (full log saved):', log, flush=True)
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=int, default=1100)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.timeout_seconds <= 0:
        parser.error('--timeout-seconds must be positive')
    sys.exit(run(command, args.log, args.timeout_seconds))
