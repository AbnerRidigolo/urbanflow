import numpy as np
import pandas as pd
import pytest
from urbanflow.ml import features, metrics, train, FEATURES
from urbanflow.storage import atomic_json, read_json, run_lock, checksum

def hours(n=600):
    return pd.DataFrame({"zone_id":161,"hour_at":pd.date_range('2024-01-01', periods=n, freq='h'),
                         "complete":True,"borough":"Manhattan","trips":np.arange(n,dtype=float)})

def test_no_future_leakage():
    a=hours(); b=a.copy(); b.loc[400:,"trips"] = 999999
    fa,fb=features(a),features(b)
    pd.testing.assert_frame_equal(fa.loc[:400,FEATURES],fb.loc[:400,FEATURES])
    assert fa.loc[400,"lag_1"]==399
    assert fa.loc[400,"lag_168"]==232

def test_missing_hour_is_not_zero_or_adjacent_row():
    a=hours().drop(index=300)
    f=features(a)
    assert np.isnan(f.loc[300,'trips'])
    assert np.isnan(f.loc[301,'lag_1'])
    assert np.isnan(f.loc[400,'mean_168'])

def test_incomplete_partition_is_unknown():
    a=hours(); a['complete']=False
    assert features(a).trips.isna().all()

def test_dst_hour_excluded():
    a=hours(4); a['hour_at']=pd.date_range('2024-03-10 00:00',periods=4,freq='h')
    assert np.isnan(features(a).loc[2,'trips'])

def test_metrics_zero_denominator():
    assert metrics([0,0],[1,2]) == {'mae':1.5,'wape':None,'n':2,'actual_sum':0.0}
    assert metrics([2,2],[1,3])['wape']==.5

def test_memory_and_sample_guard(tmp_path):
    with pytest.raises(MemoryError): features(hours(), max_rows=5)
    with pytest.raises(ValueError,match='parcial'): train(hours(),tmp_path,'public_sample')

def test_atomic_and_lock(tmp_path):
    atomic_json(tmp_path/'manifest.json',{'ok':1})
    assert read_json(tmp_path/'manifest.json')['ok']==1
    with run_lock(tmp_path):
        with pytest.raises(FileExistsError):
            with run_lock(tmp_path): pass
    assert not (tmp_path/'pipeline.lock').exists()

@pytest.mark.integration
def test_spark_idempotency_quarantine_and_failed_promotion(tmp_path):
    from urbanflow.fixture import create_fixture
    from urbanflow.etl import spark_session,transform
    from urbanflow.storage import register_source
    s=spark_session()
    try:
        source=create_fixture(tmp_path,['2024-01'])[0]
        first=transform(tmp_path,source,s)
        assert first['input']==first['accepted']+first['rejected']
        assert first['rejected']==1
        accepted=pd.read_parquet(first['path'])
        assert accepted.duplicated().sum()>=1
        assert transform(tmp_path,source,s)['path']==first['path']
        bad=pd.read_parquet(source['path']); bad['PULocationID']=999
        path=tmp_path/'bad.parquet'; bad.to_parquet(path,coerce_timestamps='us')
        changed=register_source(tmp_path,path,'2024-01','synthetic',{},True)
        with pytest.raises(ValueError,match='qualidade'): transform(tmp_path,changed,s)
        pointer=read_json(tmp_path/'silver/synthetic/2024-01/current.json')
        assert pointer['sha256']==first['sha256']
        good=pd.read_parquet(source['path'])
        good=pd.concat([good,good.iloc[[0]]],ignore_index=True)
        path=tmp_path/'corrected.parquet'; good.to_parquet(path,coerce_timestamps='us')
        changed=register_source(tmp_path,path,'2024-01','synthetic',{},True)
        corrected=transform(tmp_path,changed,s)
        assert corrected['accepted']==first['accepted']+1
        assert corrected['path']!=first['path']
        assert read_json(tmp_path/'silver/synthetic/2024-01/current.json')['sha256']==corrected['sha256']
    finally: s.stop()

@pytest.mark.integration
def test_postgres_rebuild_is_idempotent_and_failed_dbt_keeps_views(tmp_path, monkeypatch):
    import os
    if os.getenv('UF_TEST_POSTGRES')!='1': pytest.skip('Set UF_TEST_POSTGRES=1 with a disposable local PostgreSQL database')
    from urbanflow.warehouse import build,connect
    from urbanflow.storage import register_source
    from pathlib import Path
    project=Path(__file__).resolve().parents[1]
    df=pd.DataFrame({'pickup_at':[pd.Timestamp('2024-01-01')]*2,'dropoff_at':[pd.Timestamp('2024-01-01 00:10')]*2,
      'pickup_zone_id':[161]*2,'dropoff_zone_id':[161]*2,'distance_miles':[1.]*2,'total_usd':[10.]*2,
      'passengers':[1]*2,'payment_type':[1]*2,'duration_minutes':[10.]*2,'source_month':['2024-01']*2})
    path=tmp_path/'silver.parquet';df.to_parquet(path,index=False)
    m={'kind':'synthetic','partition':'2024-01','complete':True,'passed':True,'sha256':checksum(path),'path':str(path),'accepted':2}
    zones=tmp_path/'zones.csv';zones.write_text('LocationID,Borough,Zone,service_zone\n161,Manhattan,Midtown Center,Yellow Zone\n')
    build(project,[m],zones); second=build(project,[m],zones)
    with connect() as c: assert c.execute('select count(*) from analytics.fct_trips').fetchone()[0]==2
    zones.write_text('LocationID,Borough,Zone,service_zone\n132,Queens,JFK,Yellow Zone\n')
    with pytest.raises(RuntimeError,match='dbt build'): build(project,[m],zones)
    with connect() as c:
        assert c.execute('select count(*) from analytics.fct_trips').fetchone()[0]==2
        assert c.execute("select table_schema from information_schema.view_table_usage where view_schema='analytics' and view_name='fct_trips'").fetchone()[0]==second['gold_schema']
