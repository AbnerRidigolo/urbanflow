"""Download limitado por bytes. Amostra por row group NÃO é mês completo."""
import io
import re
from pathlib import Path
import requests
import pyarrow.parquet as pq
from .storage import atomic_json, checksum, now, register_source, read_json

BASE = "https://d37ci6vzurychx.cloudfront.net"
ZONE_URL = BASE + "/misc/taxi_zone_lookup.csv"


class RangeReader(io.RawIOBase):
    def __init__(self, url, limit):
        self.url, self.limit, self.pos, self.used = url, limit, 0, 0
        r = requests.head(url, headers={"Accept-Encoding": "identity"}, timeout=30)
        r.raise_for_status()
        self.size = int(r.headers["Content-Length"])
        self.etag = r.headers.get("ETag")
        self.last_modified = r.headers.get("Last-Modified")

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else (self.pos if whence == 1 else self.size) + offset
        if self.pos < 0: raise ValueError("negative seek")
        return self.pos

    def read(self, n=-1):
        n = min(n if n >= 0 else self.size - self.pos, self.size - self.pos)
        if n <= 0: return b""
        if self.used + n > self.limit: raise ValueError("Limite de download excedido; nenhum mês inteiro baixado")
        headers = {"Range": f"bytes={self.pos}-{self.pos+n-1}", "Accept-Encoding": "identity"}
        if self.etag: headers["If-Match"] = self.etag
        with requests.get(self.url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            if r.status_code != 206:
                raise ValueError("Servidor ignorou Range; download integral bloqueado")
            if r.headers.get("Content-Range") != f"bytes {self.pos}-{self.pos+n-1}/{self.size}":
                raise ValueError("Content-Range inconsistente")
            data = r.raw.read(n + 1)
        if len(data) != n: raise ValueError("Resposta parcial inconsistente")
        self.used += n
        self.pos += n
        return data


def ingest(root, month, limit=16 * 1024 * 1024, full=False):
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month): raise ValueError("Mês inválido")
    root = Path(root)
    url = f"{BASE}/trip-data/yellow_tripdata_{month}.parquet"
    dest = root / "bronze" / ("public_full" if full else "public_sample") / month
    dest.mkdir(parents=True, exist_ok=True)
    current = dest / "current.json"
    if current.exists():
        old = read_json(current)
        head = requests.head(url, headers={"Accept-Encoding": "identity"}, timeout=30)
        head.raise_for_status()
        if (head.headers.get("ETag") and head.headers.get("ETag") == old["provenance"].get("etag")
                and Path(old["path"]).exists() and checksum(old["path"]) == old["sha256"]):
            return old
    tmp = dest / "download.tmp"
    if full:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            if int(r.headers.get("Content-Length", 0)) > limit: raise ValueError("Arquivo excede orçamento explícito")
            used = 0
            with tmp.open("wb") as f:
                for block in r.iter_content(1024 * 256):
                    used += len(block)
                    if used > limit: raise ValueError("Limite excedido")
                    f.write(block)
            provenance = {"url": url, "etag": r.headers.get("ETag"), "download_bytes": used, "selection": "original completo"}
        pq.ParquetFile(tmp)  # Validate footer before registration.
    else:
        reader = RangeReader(url, limit)
        parquet = pq.ParquetFile(reader)
        table = parquet.read_row_group(0)
        pq.write_table(table, tmp)
        provenance = {"url": url, "etag": reader.etag, "last_modified": reader.last_modified,
                      "original_bytes": reader.size, "download_bytes": reader.used,
                      "original_rows": parquet.metadata.num_rows, "sample_rows": table.num_rows,
                      "selection": "row_group=0; derivado reserializado; NÃO Bronze original completo"}
    final = dest / f"{checksum(tmp)}.parquet"
    tmp.replace(final)
    return register_source(root, final, month, "public_full" if full else "public_sample", provenance, full)


def zones(root):
    path = Path(root) / "reference" / "taxi_zone_lookup.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(ZONE_URL, stream=True, timeout=30) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        content = r.raw.read(128 * 1024 + 1)
        if len(content) > 128 * 1024: raise ValueError("Lookup excede orçamento")
    import csv
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    if len(rows) != 265 or len({int(x["LocationID"]) for x in rows}) != 265:
        raise ValueError("Lookup inválido")
    path.write_bytes(content)
    atomic_json(path.with_suffix(".json"), {"url": ZONE_URL, "sha256": checksum(path), "retrieved_at": now()})
    return path
