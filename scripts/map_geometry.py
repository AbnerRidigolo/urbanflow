"""Official TLC shape -> simplified WGS84 GeoJSON, bounded download."""
import io,json,zipfile,hashlib
from pathlib import Path
import requests
import shapefile
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer

root=Path(__file__).resolve().parents[1]
url='https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip'
with requests.get(url,stream=True,timeout=60) as r:
    r.raise_for_status(); payload=bytearray()
    for chunk in r.iter_content(262144):
        payload.extend(chunk)
        if len(payload)>16*1024*1024: raise ValueError('Geometry download exceeds 16 MB')
z=zipfile.ZipFile(io.BytesIO(payload))
def part(ext): return io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(ext))))
reader=shapefile.Reader(shp=part('.shp'),shx=part('.shx'),dbf=part('.dbf'))
crs=z.read(next(n for n in z.namelist() if n.endswith('.prj'))).decode()
project=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform
features=[]
for record in reader.iterShapeRecords():
    geom=transform(project,shape(record.shape.__geo_interface__)).simplify(.00015,preserve_topology=True)
    features.append({'type':'Feature','properties':{'LocationID':int(record.record.as_dict()['LocationID'])},'geometry':mapping(geom)})
(root/'dashboard/zones.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
(root/'dashboard/zones-source.json').write_text(json.dumps({'url':url,'sha256':hashlib.sha256(payload).hexdigest(),'simplification_degrees':.00015,'crs':'EPSG:4326'}),encoding='utf-8')
print(f'{len(features)} official zone shapes')
