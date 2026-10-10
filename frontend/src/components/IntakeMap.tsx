import { SatelliteLayers } from './SatelliteLayers';
import { useEffect, useRef, useState } from 'react';
import { AttributionControl, Map as MapLibreMap, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { hasMapLocation, type IntakeIncident } from '../data/intake';
import { BASEMAP_STYLE_URL, BUILDINGS_3D, TILTED, FLAT } from './IncidentMap';
setWorkerUrl(maplibreWorkerUrl);

export function IntakeMap({ incidents, selectedId, onSelect }: {
  incidents: IntakeIncident[]; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [error, setError] = useState(false);
  const [tilted, setTilted] = useState(true);
  const fitted = useRef(false);
  useEffect(() => {
    let instance: MapLibreMap;
    try {
      instance = new MapLibreMap({ container: container.current!, style: BASEMAP_STYLE_URL,
        center: [7.0362, 50.5141], zoom: 10, ...TILTED, attributionControl: false });
      instance.on('load', () => {
        const firstLabel = instance.getStyle().layers.find(layer => layer.type === 'symbol')?.id;
        if (!instance.getLayer(BUILDINGS_3D.id)) instance.addLayer(BUILDINGS_3D, firstLabel);
      });
      instance.on('pitchend', () => setTilted(instance.getPitch() > 5));
      instance.setMissingStyleImageResolver(id => {
        if (!instance.hasImage(id)) instance.addImage(id, new ImageData(1, 1));
      });
      instance.addControl(new AttributionControl({ compact: true }), 'bottom-left');
      instance.addControl(new NavigationControl());
      instance.on('error', () => setError(true));
      setMap(instance);
    } catch { setError(true); return; }
    return () => instance.remove();
  }, []);
  useEffect(() => {
    if (!map) return;
    const located = incidents.filter(hasMapLocation);
    const markers = located.map(i => {
      const el = document.createElement('button');
      el.type = 'button'; el.className = 'intake-pin';
      el.style.background = i.id === selectedId ? '#b45309' : '#0369a1';
      el.setAttribute('aria-label', `Select report ${i.id.slice(0, 8)}`);
      el.onclick = () => onSelect(i.id);
      return new Marker({ element: el }).setLngLat([i.longitude!, i.latitude!]).addTo(map);
    });
    if (located.length && !fitted.current) {
      const lngs = located.map(i => i.longitude!), lats = located.map(i => i.latitude!);
      map.fitBounds([[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
        { padding: 70, maxZoom: 14, duration: 0, pitch: map.getPitch(), bearing: map.getBearing() });
      fitted.current = true;
    }
    return () => markers.forEach(m => m.remove());
  }, [map, incidents, selectedId, onSelect]);
  useEffect(() => {
    const i = incidents.find(row => row.id === selectedId);
    if (map && i && hasMapLocation(i)) map.easeTo({ center: [i.longitude!, i.latitude!], duration: 500 });
  }, [map, selectedId, incidents]);
  return <><SatelliteLayers map={map} onReturn={() => {
      const points = incidents.filter(hasMapLocation);
      if (points.length && map) map.fitBounds([
        [Math.min(...points.map(i => i.longitude!)), Math.min(...points.map(i => i.latitude!))],
        [Math.max(...points.map(i => i.longitude!)), Math.max(...points.map(i => i.latitude!))],
      ], { padding: 70, maxZoom: 14 });
    }} /><button type="button" className="map-tilt" aria-pressed={tilted}
      title={tilted ? 'Flat 2D view' : 'Tilted 2.5D view with buildings'}
      onClick={() => map?.easeTo({ ...(tilted ? FLAT : TILTED), duration: 500 })}>
      {tilted ? '2.5D' : '2D'}
    </button><div ref={container} className="intake-map" aria-label="Reported incident locations" />
    <div className="intake-map-note">{error ? 'Basemap unavailable. Reports remain accessible in the feed.' :
      `${incidents.filter(hasMapLocation).length} located cases · ${incidents.filter(i => !hasMapLocation(i)).length} awaiting location review`}
      <br />Pins use operator-supplied coordinates; no positions are inferred from SMS.</div></>;
}
