import sys
import traceback
from datetime import datetime

class Logger:
    """
    Redirects all print output to a log file.
    A simple logger that redirects stdout/stderr and logs unhandled exceptions.
    """
    def __init__(self, logfile_path):
        self.logfile = open(logfile_path, "a", buffering=1, encoding="utf-8", errors="backslashreplace")
        self._orig_stdout = sys.__stdout__
        self._orig_stderr = sys.__stderr__
        sys.stdout = self
        sys.stderr = self

         # Handle uncaught exceptions globally
        sys.excepthook = self.handle_exception

    def write(self, message):
        if message is None:
            return
        try:
            timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
            self.logfile.write(f"{timestamp} {message}")
        except Exception:
            try:
                self._orig_stderr.write("Error in Logger.write\n")
            except Exception:
                pass

    def flush(self):
        try:
            self.logfile.flush()
        except Exception:
            pass

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            self._orig_stderr.write("KeyboardInterrupt\n")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        try:
            self.write("UNHANDLED EXCEPTION:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=self.logfile)
            self.flush()
        except Exception:
            try:
                self._orig_stderr.write("Error while Logging the Exception\n")
            except Exception:
                pass

    def close(self):
        # restore original stdout/stderr
        try:
            sys.stdout = self._orig_stdout
            sys.stderr = self._orig_stderr
        except Exception:
            pass
        try:
            self.logfile.close()
        except Exception:
            pass
