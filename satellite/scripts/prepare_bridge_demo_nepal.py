"""Anonymous Vantor COG window retrieval; uses this checkout's locked environment."""
import datetime, hashlib, json, pathlib
import httpx, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from PIL import Image, ImageDraw, ImageFont
ROOT=pathlib.Path(__file__).resolve().parents[1] / 'data/research/bridge-demo-nepal'
ROOT.mkdir(parents=True, exist_ok=True)
COLLECTION='https://vantor-opendata.s3.amazonaws.com/events/Nepal-Flooding-Aug-2026/collection.json'
IDS={'before':'10500100364E8400','after':'B040001100881410'}
for name, url in [('vantor-collection', COLLECTION)] + [(id, COLLECTION.replace('collection.json', id+'.json')) for id in IDS.values()]:
    response=httpx.get(url, timeout=30); response.raise_for_status(); (ROOT/(name+'.json')).write_text(json.dumps(response.json(), indent=2)+'\n')
TARGETS=[{'id':'syabrubesi-trishuli-footbridge','name':'Syaphru Besi I / Trishuli footbridge','lon':85.342728,'lat':28.165879,'type':'suspension footbridge','coordinate_source':'https://www.bridgemeister.com/bridge.php?bid=9351','finding':'Continuous narrow span is visible in the 2023 image. No continuous span is visible at the same crossing in the 2026 image; approach paths and riverside buildings are also absent or buried. Human visual assessment corroborates reported bridge destruction, not an automated detector result.'}, {'id':'syabrubesi-langtang-road-crossing','name':'Syabrubesi road crossing near Langtang confluence (name unverified)','lon':85.33999,'lat':28.16422,'type':'road bridge, inferred from connecting road geometry','coordinate_source':'Manually localized from retrieved georeferenced pre-event imagery; approximate center, not a surveyed inventory point.','finding':'Road-linked bridge deck is visible in the 2023 image. Deck and approaches are no longer visible across the widened debris channel in the 2026 image. Human image interpretation; precise official bridge identity and time of destruction unverified.'}]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(n): return ImageFont.truetype(FONT,n)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
retrieved=datetime.datetime.now(datetime.UTC).isoformat()
manifest={'event':'Bhote Koshi / Trishuli debris-laden flood','event_date':'2026-08-26','retrieval_time_utc':retrieved,'collection_url':COLLECTION,'license':'CC-BY-NC-4.0','attribution':'Vantor Open Data Program; imagery WorldView/GeoEye','interpretation':'Retrospective, manually inspected demonstration examples. Baseline is three years earlier and does not alone date the loss to the 2026 event. The July 2025 Rasuwa flood is an intervening event; its impact on these exact crossings is unverified. No model accuracy claim. Pixel windows are georeferenced, but no precision image coregistration was performed.','targets':[]}
for target in TARGETS:
    t=dict(target); bounds=[t['lon']-.002,t['lat']-.002,t['lon']+.002,t['lat']+.002];t['requested_bounds_wgs84']=bounds;t['images']={}; panels=[]
    for phase,id in IDS.items():
        meta_path=ROOT/(id+'.json');j=json.loads(meta_path.read_text());url=j['assets']['visual']['href']
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='30'):
            with rasterio.open(url) as ds:
                win=from_bounds(*bounds,ds.transform).round_offsets().round_lengths();arr=ds.read(window=win);xf=ds.window_transform(win)
                tif=ROOT/(t['id']+'-'+phase+'.tif'); profile=ds.profile.copy(); profile.update(height=arr.shape[1],width=arr.shape[2],transform=xf,driver='GTiff',compress='deflate',photometric='RGB');
                with rasterio.open(tif,'w',**profile) as out:out.write(arr)
                img=Image.fromarray(arr.transpose(1,2,0)); png=ROOT/(t['id']+'-'+phase+'.png');img.save(png)
                t['images'][phase]={'item_id':id,'acquisition_time_utc':j['properties']['datetime'],'publication_time':j['properties'].get('published'),'source_url':url,'pan_gsd_m':j['properties']['pan_gsd'],'multispectral_gsd_m':j['properties']['multispectral_gsd'],'crs':str(ds.crs),'transform':list(xf),'pixel_dimensions':[arr.shape[2],arr.shape[1]],'scene_cloud_cover_percent':j['properties']['eo:cloud_cover'],'local_observation':'Bridge crossing locally clear; no obstructing cloud seen in selected window.','png_path':str(png),'geotiff_path':str(tif),'png_sha256':sha(png),'geotiff_sha256':sha(tif),'stac_path':str(meta_path),'stac_sha256':sha(meta_path)}
        panel=Image.new('RGB',(700,855),(16,26,39));d=ImageDraw.Draw(panel);d.text((18,14),phase.upper()+': '+j['properties']['datetime'][:10],font=font(24),fill='white');view=img.resize((700,790));panel.paste(view,(0,50));d=ImageDraw.Draw(panel)
        # Circle is a visual attention guide around approximate former crossing, not a measured footprint.
        x=(t['lon']-xf.c)/xf.a/arr.shape[2]*700;y=(t['lat']-xf.f)/xf.e/arr.shape[1]*790+50
        d.ellipse((x-95,y-60,x+95,y+60),outline=(76,235,134) if phase=='before' else (255,104,91),width=4)
        text='Span visible' if phase=='before' else 'Span no longer visible';d.rounded_rectangle((x-105,y+69,x+193,y+110),8,fill=(16,26,39));d.text((x-96,y+74),text,font=font(20),fill='white');panels.append(panel)
    combined=Image.new('RGB',(1412,945),(16,26,39));d=ImageDraw.Draw(combined);d.text((18,12),t['name'],font=font(23),fill='white');combined.paste(panels[0],(0,45));combined.paste(panels[1],(712,45));d=ImageDraw.Draw(combined);d.text((18,908),'Manual image interpretation | Vantor / CC BY-NC 4.0 | Circle: approximate crossing',font=font(18),fill=(201,211,224));out=ROOT/(t['id']+'-comparison.png');combined.save(out);t['comparison_png_path']=str(out);t['comparison_sha256']=sha(out);manifest['targets'].append(t)
# Recent lower-resolution baseline helps constrain the road-crossing loss interval.
planet_id='20260527_053221_96_254a'
planet_base='https://data.source.coop/planet/disasterdata/nepal-flash-flood-2026-08-26/pre-event/planetscope-2026-05-27/items/'+planet_id+'/'
response=httpx.get(planet_base+planet_id+'.json', timeout=30); response.raise_for_status(); planet=response.json(); planet_metadata=ROOT/(planet_id+'.json');planet_metadata.write_text(json.dumps(planet,indent=2)+'\n')
road=manifest['targets'][1];bbox=road['requested_bounds_wgs84'];planet_url=planet_base+planet_id+'_visual.tif'
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='30'):
    with rasterio.open(planet_url) as ds:
        projected=transform_bounds('EPSG:4326',ds.crs,*bbox);win=from_bounds(*projected,ds.transform).round_offsets().round_lengths();arr=ds.read(window=win);xf=ds.window_transform(win)
        tif=ROOT/'syabrubesi-langtang-road-crossing-recent-before.tif';profile=ds.profile.copy();profile.update(height=arr.shape[1],width=arr.shape[2],transform=xf,compress='deflate',photometric='RGB')
        with rasterio.open(tif,'w',**profile) as out:out.write(arr)
        png=ROOT/'syabrubesi-langtang-road-crossing-recent-before.png';Image.fromarray(arr[:3].transpose(1,2,0)).resize((700,790)).save(png)
        road['recent_pre_event_reference']={'item_id':planet_id,'acquisition_time_utc':planet['properties']['datetime'],'source_url':planet_url,'resolution_m':3,'crs':str(ds.crs),'transform':list(xf),'png_path':str(png),'geotiff_path':str(tif),'png_sha256':sha(png),'geotiff_sha256':sha(tif),'stac_sha256':sha(planet_metadata),'license':'CC-BY-NC-4.0','attribution':'Planet Labs PBC / Planet Crisis Response Program','manual_finding':'Intact-looking diagonal road-crossing span is visible in this locally clear 3m image on May27 2026. Supports disappearance between May27 and Aug27 2026; does not independently establish exact loss time or structural condition. Narrow footbridge is too small for confident continuity assessment at3m.'}
manifest['collection_metadata_sha256']=sha(ROOT/'vantor-collection.json');(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'manifest':str(ROOT/'manifest.json'),'comparisons':[t['comparison_png_path'] for t in manifest['targets']]},indent=2))
