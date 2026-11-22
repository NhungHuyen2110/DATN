import subprocess
import sys
import time
import unittest
from shared.host_process import run_bounded


class HostProcessTests(unittest.TestCase):
    def test_timeout_terminates_child_holding_inherited_output_pipe(self):
        program = (
            'import subprocess,sys,time;'
            'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(40)"]);'
            'print("child:"+str(child.pid),flush=True);'
            'child.wait()'
        )
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            run_bounded([sys.executable, '-c', program], timeout=3)
        self.assertIn(b'child:', caught.exception.output)
        self.assertLess(time.monotonic() - started, 15)
