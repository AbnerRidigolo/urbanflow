import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@contextmanager
def run_lock(root):
    """Um escritor por data root; lock persistente após crash requer inspeção humana."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "pipeline.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, f"pid={os.getpid()} created={now()}".encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def register_source(root, path, month, kind, provenance, complete=False):
    root, path = Path(root), Path(path)
    digest = checksum(path)
    record = {"partition": month, "kind": kind, "sha256": digest,
              "path": str(path.resolve()), "bytes": path.stat().st_size,
              "complete": complete, "retrieved_at": now(), "provenance": provenance}
    atomic_json(root / "bronze" / kind / month / f"{digest}.json", record)
    atomic_json(root / "bronze" / kind / month / "current.json", record)
    return record
