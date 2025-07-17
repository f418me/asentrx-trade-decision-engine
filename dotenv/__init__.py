import os
from pathlib import Path

def load_dotenv(dotenv_path=None, override=False):
    """Minimal replacement for python-dotenv's load_dotenv."""
    if dotenv_path is None:
        dotenv_path = '.env'
    path = Path(dotenv_path)
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if override or key not in os.environ:
            os.environ[key] = value
    return True
