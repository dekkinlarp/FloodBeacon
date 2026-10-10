import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AttributionControl, Map as MapLibreMap, Marker, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import type { AddLayerObject } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type { Incident } from '../types';
import { markerStyle } from '../logic/severity';
import { contactBadge } from '../logic/contactBadge';
import { mainNeed } from '../logic/mainNeed';
import { isOverdueCritical } from '../logic/warnings';
import { NeedIcon, needLabel } from './NeedIcon';

/** OpenFreeMap "Dark": free, no API key. Map data © OpenStreetMap contributors. */
export const BASEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty';
const BANGKOK_CENTER: [number, number] = [100.6, 13.77]; // [lon, lat]
const BANGKOK_ZOOM = 10;
/** 2.5D view: tilted camera, slightly rotated so the river and roads read in depth. */
export const TILTED = { pitch: 50, bearing: -17 };
export const FLAT = { pitch: 0, bearing: 0 };

/**
 * Buildings extruded to their mapped height (OpenMapTiles `render_height`).
 * They grow in between zoom 13 and 14 so the city-wide view stays uncluttered.
 */
export const BUILDINGS_3D: AddLayerObject = {
  id: 'buildings-3d',
  type: 'fill-extrusion',
  source: 'openmaptiles',
  'source-layer': 'building',
  minzoom: 13,
  filter: ['!=', ['get', 'hide_3d'], true],
  paint: {
    // Muted blue buildings stay distinct from the light basemap.
    'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 6], 0, '#cbd5e1', 40, '#94a3b8', 150, '#64748b'],
    'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, ['coalesce', ['get', 'render_height'], 6]],
    'fill-extrusion-base': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, ['coalesce', ['get', 'render_min_height'], 0]],
    'fill-extrusion-opacity': 0.85,
  },
};

// MapLibre finds its worker next to its own module by default. Vite moves that
// module (dev pre-bundling) and drops the worker file (build), so hand MapLibre
// a worker that Vite bundles itself.
setWorkerUrl(maplibreWorkerUrl);

interface Props {
  incidents: readonly Incident[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  now: Date;
}

interface MarkerSlot {
  incident: Incident;
  element: HTMLElement;
}

/**
 * Map markers show only severity colour, main-need icon and hours since
 * contact. No health details here (CLAUDE.md rule 7).
 */
export function IncidentMap({ incidents, selectedId, onSelect, now }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [slots, setSlots] = useState<MarkerSlot[]>([]);
  const [tilted, setTilted] = useState(true);

  useEffect(() => {
    const m = new MapLibreMap({
      container: containerRef.current!,
      style: BASEMAP_STYLE_URL,
      center: BANGKOK_CENTER,
      zoom: BANGKOK_ZOOM,
      ...TILTED,
      attributionControl: false,
    });
    m.on('load', () => {
      // Under the first label layer, so street and place names stay on top of buildings.
      const firstLabel = m.getStyle().layers.find((l) => l.type === 'symbol')?.id;
      if (!m.getLayer(BUILDINGS_3D.id)) m.addLayer(BUILDINGS_3D, firstLabel);
    });
    // Keep the toggle in sync when the user tilts with the mouse or the compass.
    m.on('pitchend', () => setTilted(m.getPitch() > 5));
    // Some map styles refer to pattern images they do not ship (e.g. "wood-pattern").
    // Fill them with a transparent pixel instead of logging a warning per tile.
    m.setMissingStyleImageResolver((id) => {
      if (!m.hasImage(id)) m.addImage(id, new ImageData(1, 1));
    });
    m.addControl(new NavigationControl(), 'top-right');
    // Bottom-left so the incident card (right side) never hides the OSM credit.
    m.addControl(new AttributionControl({ compact: true }), 'bottom-left');
    setMap(m);
    return () => {
      m.remove();
      setMap(null);
    };
  }, []);

  // MapLibre owns each marker's DOM element; React renders into it via a portal.
  useEffect(() => {
    if (!map) return;
    const created = incidents.map((incident) => {
      const element = document.createElement('div');
      const marker = new Marker({ element, anchor: 'center' })
        .setLngLat([incident.location.lon, incident.location.lat])
        .addTo(map);
      return { incident, element, marker };
    });
    setSlots(created.map(({ incident, element }) => ({ incident, element })));
    return () => created.forEach(({ marker }) => marker.remove());
  }, [map, incidents]);

  // Re-centre only when the selection changes, not on every status update.
  const incidentsRef = useRef(incidents);
  incidentsRef.current = incidents;
  useEffect(() => {
    const selected = incidentsRef.current.find((i) => i.id === selectedId);
    if (map && selected) {
      map.easeTo({ center: [selected.location.lon, selected.location.lat] });
    }
  }, [map, selectedId]);

  return (
    <div className="incident-map-wrap">
      <button
        type="button"
        className="map-tilt"
        aria-pressed={tilted}
        title={tilted ? 'Flat 2D view' : 'Tilted 2.5D view with buildings'}
        onClick={() => {
          map?.easeTo({ ...(tilted ? FLAT : TILTED), duration: 600 });
          setTilted(!tilted);
        }}
      >
        {tilted ? '2D' : '3D'}
      </button>
      <div ref={containerRef} className="incident-map">
        {slots.map(({ incident, element }) =>
          createPortal(
            <IncidentMarker
              incident={incident}
              selected={incident.id === selectedId}
              onSelect={onSelect}
              now={now}
            />,
            element,
            incident.id,
          ),
        )}
      </div>
    </div>
  );
}

function IncidentMarker({
  incident,
  selected,
  onSelect,
  now,
}: {
  incident: Incident;
  selected: boolean;
  onSelect: (id: string) => void;
  now: Date;
}) {
  const style = markerStyle(incident.severity, incident.status);
  const need = mainNeed(incident);
  const badge = contactBadge(incident, now);
  const needText = need ? needLabel(need) : 'No need listed';
  const overdue = isOverdueCritical(incident, now);
  return (
    <button
      type="button"
      className={`marker${selected ? ' marker--selected' : ''}${overdue ? ' flash' : ''}`}
      style={{ background: style.fill, color: style.ink }}
      aria-pressed={selected}
      aria-label={`${incident.id}, ${incident.severity}, ${needText}, last contact ${badge.label} ago${overdue ? ', no team for over 30 minutes' : ''}`}
      onClick={() => onSelect(incident.id)}
    >
      <NeedIcon need={need} />
      <span className={`marker__badge${badge.overdue ? ' marker__badge--overdue' : ''}`}>
        {badge.label}
      </span>
    </button>
  );
}
