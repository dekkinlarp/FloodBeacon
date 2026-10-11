import type { Map as MapLibreMap } from 'maplibre-gl';

/**
 * Id of the layer that starts the style's label block: the first symbol layer after its last
 * non-symbol layer. Inserting before it puts a layer above every fill and line in the style
 * (some styles, like OpenFreeMap "dark", draw flat buildings and roads after an early water
 * label) while keeping street and place names on top.
 */
export function labelBlockStart(map: MapLibreMap): string | undefined {
  const layers = map.getStyle().layers;
  let lastShape = -1;
  layers.forEach((layer, index) => {
    if (layer.type !== 'symbol') lastShape = index;
  });
  return layers.slice(lastShape + 1).find((layer) => layer.type === 'symbol')?.id;
}
