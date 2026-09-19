import os

def is_file_readable(file_path: str) -> bool:
    """Check if the file exists and is readable."""
    return os.path.isfile(file_path) and os.access(file_path, os.R_OK)
