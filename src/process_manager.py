import os
import queue
import signal
import subprocess
import threading
import time
 
 
class StreamingProcess:
    """Runs a shell command and streams its output via a thread-safe queue."""
 
    def __init__(self, command, cwd=None, shell=True, env=None):
        self.command = command
        self.cwd = cwd
        self.shell = shell
        self.env = env or os.environ.copy()
        self.process = None
        self.output_queue = queue.Queue()
        self._reader_thread = None
        self._finished = False
        self.return_code = None
 
    def start(self):
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            shell=self.shell,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid if os.name != "nt" else None,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()
        return self
 
    def _read_output(self):
        try:
            for line in iter(self.process.stdout.readline, ""):
                if line:
                    self.output_queue.put(line.rstrip("\n"))
                if line == "" and self.process.poll() is not None:
                    break
        except Exception as e:  # pragma: no cover - defensive
            self.output_queue.put(f"[reader-error] {e}")
        finally:
            try:
                self.process.stdout.close()
            except Exception:
                pass
            self.return_code = self.process.wait()
            self._finished = True
 
    def poll_lines(self):
        """Return all currently available lines without blocking."""
        lines = []
        while True:
            try:
                lines.append(self.output_queue.get_nowait())
            except queue.Empty:
                break
        return lines
 
    def is_running(self):
        return self.process is not None and self.process.poll() is None
 
    def wait(self, timeout=None):
        """
        Block, collecting output, until the process finishes or timeout (in
        seconds) elapses. Returns (lines, finished, return_code).
        """
        collected = []
        start = time.time()
        while True:
            collected.extend(self.poll_lines())
            if self._finished:
                collected.extend(self.poll_lines())
                return collected, True, self.return_code
            if timeout is not None and (time.time() - start) > timeout:
                return collected, False, None
            time.sleep(0.1)
 
    def stop(self):
        """Terminate the process (and its child tree, so e.g. `npm start` -> node also dies)."""
        if self.process and self.process.poll() is None:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                else:
                    # terminate() alone only kills the shell, leaving spawned
                    # children (e.g. node under `npm start`) running. taskkill
                    # /T walks the whole process tree.
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                    )
            except Exception:
                pass