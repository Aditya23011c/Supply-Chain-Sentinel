"""Loads KEY=VALUE pairs from <project>/.env into os.environ (no extra dependency).
Real environment variables always win; empty values are ignored."""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_env(path=None):
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


load_env()
