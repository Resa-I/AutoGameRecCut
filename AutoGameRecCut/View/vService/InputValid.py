import os

class InputValid:
    """
    Provides additional validation for file and directory paths.
    Note:
        PySide6 already validates user inputs. For example:  setRange(1, 20)
    """
    @staticmethod
    def valid(data):
        errors = []
        inp = data.get('input_path', '')
        outp = data.get('output_path', '')

        valid, msg = InputValid.valid_path(inp, require_write=False)
        if not valid:
            errors.append(f"Video input: {msg}: {msg}")

        valid, msg = InputValid.valid_path(outp, require_write=True)
        if not valid:
            errors.append(f"Output folder: {msg}")

        return len(errors) == 0, errors

    @staticmethod
    def valid_path(path, require_write=True):
        if not path or not path.strip():
            return False, "Path cannot be empty"
        if not os.path.exists(path):
            # For output paths allow non-existing if parent is writable
            parent = os.path.dirname(path) or "."
            if require_write and os.access(parent, os.W_OK):
                return True, ""
            return False, "Path does not exist"
        if not (os.path.isfile(path) or os.path.isdir(path)):
            return False, "Path is not a file or a directory"
        if require_write:
            if not os.access(path, os.W_OK):
                return False, "No write permission for this path"
        else:
            if not os.access(path, os.R_OK):
                return False, "No read permission for this path"
        return True, ""
