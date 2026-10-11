import { useSite } from '../state/Site';
import { SITES, type SiteId } from '../data/sites';
import { useEffect, useState } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';
import type { FeatureCollection } from 'geojson';
import { labelBlockStart } from './mapLayers';
type Bounds = [number, number, number, number];
type Image = { id: string; url: string; image_coordinates: [[number, number], [number, number], [number, number], [number, number]]; attribution: string; license: string; license_url: string };
type Observation = { id: string; label: string; acquired_date: string; images: Image[]; bridges: FeatureCollection; regional_tiles?: { url: string; bounds: Bounds; minzoom: number; maxzoom: number; tile_size: number; attribution: string; license: string; license_url: string } };
type CatalogCase = { observations: Observation[]; metadata: { imagery: { name: string; case_id: string; bounds: Bounds; flood_extent?: FeatureCollection; bridges: { name: string; coordinate: [number, number]; comparison_url: string }[] } } };
export function SatelliteLayers({ map, onReturn }: { map: MapLibreMap | null; onReturn: () => void }) {
  const [cases, setCases] = useState<CatalogCase[]>([]);
  const { siteId: caseId, selectSite } = useSite();
  const [date, setDate] = useState('');
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const current = cases.find(c => c.metadata.imagery.case_id === caseId);
  const observation = current?.observations.find(o => o.id === date) ?? current?.observations[0];
  useEffect(() => {
    const controller = new AbortController();
    fetch('/static/imagery/bridge-catalog/catalog.json', { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => setCases(data.cases)).catch(e => { if (e.name !== 'AbortError') setError('Satellite catalog unavailable.'); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!map) return;
    const loaded = () => setReady(true);
    if (map.isStyleLoaded()) loaded();
    map.on('load', loaded);
    return () => { map.off('load', loaded); };
  }, [map]);
  const fit = (c: CatalogCase) => {
    const b = c.metadata.imagery.bounds;
    map?.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 65, duration: 600 });
  };
  useEffect(() => {
    if (!map || !ready || !observation || !current) return;
    const sources: string[] = [], layers: string[] = [];
    // Imagery covers the style's flat buildings and roads, and sits below the 3D buildings
    // (BUILDINGS_3D in IncidentMap) and the labels.
    const before = map.getLayer('buildings-3d') ? 'buildings-3d' : labelBlockStart(map);
    setError('');
    const failure = (event: unknown) => { if ((event as { sourceId?: string }).sourceId?.startsWith('sat-')) setError('Some satellite imagery could not load; gaps remain unknown.'); };
    map.on('error', failure);
    const regional = observation.regional_tiles;
    if (regional) {
      map.addSource('sat-region', { type: 'raster', tiles: [regional.url], bounds: regional.bounds, minzoom: regional.minzoom, maxzoom: regional.maxzoom, tileSize: regional.tile_size, attribution: regional.attribution });
      sources.push('sat-region');
      map.addLayer({ id: 'sat-region', type: 'raster', source: 'sat-region', paint: { 'raster-opacity': 0.85 } }, before); layers.push('sat-region');
    }
    observation.images.forEach((image, index) => {
      const id = `sat-image-${index}`;
      map.addSource(id, { type: 'image', url: image.url, coordinates: image.image_coordinates }); sources.push(id);
      map.addLayer({ id, type: 'raster', source: id, minzoom: regional ? 15 : 0, paint: { 'raster-opacity': 0.95 } }, before); layers.push(id);
    });
    // The agency reference is dated July 18, 2021, not the pre-flood observation.
    if (current.metadata.imagery.flood_extent && observation.acquired_date >= '2021-07-18') {
      map.addSource('sat-flood', { type: 'geojson', data: current.metadata.imagery.flood_extent }); sources.push('sat-flood');
      map.addLayer({ id: 'sat-flood', type: 'fill', source: 'sat-flood', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.3 } }, before); layers.push('sat-flood');
    }
    map.addSource('sat-bridges', { type: 'geojson', data: observation.bridges }); sources.push('sat-bridges');
    map.addLayer({ id: 'sat-bridges', type: 'line', source: 'sat-bridges', paint: { 'line-color': '#facc15', 'line-width': 3 } }); layers.push('sat-bridges');
    return () => {
      map.off('error', failure);
      for (const id of layers.reverse()) if (map.getLayer(id)) map.removeLayer(id);
      for (const id of sources) if (map.getSource(id)) map.removeSource(id);
    };
  }, [map, ready, current, observation]);
  const showsFlood = !!current?.metadata.imagery.flood_extent && !!observation && observation.acquired_date >= '2021-07-18';
  const findings = new Map(observation?.bridges.features.map(f => [String(f.properties?.name ?? ''), String(f.properties?.finding ?? '')]));
  const sources = observation ? [...observation.images, ...(observation.regional_tiles ? [observation.regional_tiles] : [])] : [];

  // Collapsed by default on phones, where the panel would cover most of the map.
  return <details className="satellite-controls" aria-label="Historical satellite imagery"
    open={!window.matchMedia('(max-width: 760px)').matches || undefined}>
    <summary>
      <span className="sat__title">Historical satellite imagery</span>
      {observation && <span className="sat__current">{observation.acquired_date} · {observation.label}</span>}
    </summary>
    <div className="sat__body">
      <div className="sat__fields">
        <label className="sat__field">
          <span>Study area</span>
          <select value={caseId} onChange={e => {
            if (e.target.value in SITES) selectSite(e.target.value as SiteId);
          }}>{Object.entries(SITES).map(([id, site]) => <option key={id} value={id}>{site.name}</option>)}</select>
        </label>
        {current && observation && <label className="sat__field">
          <span>Image date</span>
          <select value={observation.id} onChange={e => setDate(e.target.value)}>{current.observations.map(o => <option key={o.id} value={o.id}>{o.acquired_date} · {o.label}</option>)}</select>
        </label>}
      </div>
      {current && observation && <>
        <div className="sat__view" role="group" aria-label="Map view">
          <button type="button" onClick={() => fit(current)}>Whole study area</button>
          <button type="button" onClick={onReturn}>Rescue reports</button>
        </div>
        <section className="sat__section" aria-label="Bridges">
          <h3>Bridges</h3>
          <ul className="sat__bridges">
            {current.metadata.imagery.bridges.map(b => <li key={b.name}>
              <button type="button" className="sat__bridge" onClick={() => map?.easeTo({ center: b.coordinate, zoom: 17 })}>{b.name}</button>
              <a className="sat__compare" href={b.comparison_url} target="_blank" rel="noreferrer">Compare<span aria-hidden="true"> ↗</span></a>
              <p className="sat__finding">{findings.get(b.name) ?? 'Not covered by this image.'}</p>
            </li>)}
          </ul>
        </section>
        <ul className="sat__legend" aria-label="Legend">
          <li><span className="sat__swatch sat__swatch--bridge" aria-hidden="true" />Manual bridge review</li>
          {showsFlood && <li><span className="sat__swatch sat__swatch--flood" aria-hidden="true" />Copernicus EMSR517 flood / flood-trace reference (18 July 2021)</li>}
        </ul>
        <p className="sat__note">Gaps are unknown. These are historical observations, not live conditions or route safety assessments. Rescue demo pins are fictional.</p>
        <footer className="sat__sources">
          {sources.map((im, i) => <small key={i}>{im.attribution} · <a href={im.license_url} target="_blank" rel="noreferrer">{im.license}</a></small>)}
        </footer>
      </>}
      {error && <p className="sat__error" role="alert">{error}</p>}
    </div>
  </details>;
}
