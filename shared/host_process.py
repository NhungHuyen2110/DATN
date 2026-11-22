"""Bound a host CLI including Windows Docker plugin children holding its pipes."""
import os
import signal
import subprocess


def run_bounded(command, *, cwd=None, input=None, timeout=30):
    process = subprocess.Popen(command, cwd=cwd,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as original:
        # subprocess.run kills the launcher then waits for inherited pipes. On
        # Windows docker-compose/buildx can survive that kill indefinitely.
        if os.name == 'nt':
            try:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            # Do not wait again on a surviving descendant's pipe.
            stdout, stderr = original.output or b'', original.stderr or b''
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from None
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
