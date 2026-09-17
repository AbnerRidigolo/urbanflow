import pytest
from urbanflow.ingest import RangeReader,ingest
from urbanflow.storage import register_source

class Response:
    def __init__(self,status=200,headers=None): self.status_code=status;self.headers=headers or {}
    def raise_for_status(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass

def test_range_budget_blocks_before_get(monkeypatch):
    monkeypatch.setattr('urbanflow.ingest.requests.head',lambda *a,**k:Response(headers={'Content-Length':'100'}))
    monkeypatch.setattr('urbanflow.ingest.requests.get',lambda *a,**k:pytest.fail('network must not start'))
    reader=RangeReader('https://example.test/file',10)
    with pytest.raises(ValueError,match='Limite'): reader.read(11)

def test_range_refuses_full_response(monkeypatch):
    monkeypatch.setattr('urbanflow.ingest.requests.head',lambda *a,**k:Response(headers={'Content-Length':'100'}))
    monkeypatch.setattr('urbanflow.ingest.requests.get',lambda *a,**k:Response())
    with pytest.raises(ValueError,match='ignorou Range'): RangeReader('https://example.test/file',100).read(5)

def test_cached_etag_requires_local_checksum(tmp_path,monkeypatch):
    path=tmp_path/'source.parquet';path.write_bytes(b'previously validated source')
    old=register_source(tmp_path,path,'2024-01','public_full',{'etag':'v1'},True)
    monkeypatch.setattr('urbanflow.ingest.requests.head',lambda *a,**k:Response(headers={'ETag':'v1'}))
    monkeypatch.setattr('urbanflow.ingest.requests.get',lambda *a,**k:pytest.fail('unchanged source must be reused'))
    assert ingest(tmp_path,'2024-01',full=True)['sha256']==old['sha256']
