"""Export an inspectable map using the same completed runs as the REST API."""

import html
import json
from pathlib import Path
from datetime import date

import folium

from floodbeacon import db

COLORS = {
    "reported_damage": "#dc2626", "agency_flood_reference": "#2563eb",
    "assets": "#64748b", "modeled_new_water": "#0891b2",
    "modeled_event_water": "#60a5fa", "exposure": "#f97316",
    "scenario_50m": "#a855f7", "scenario_100m": "#db2777",
    "unknown_coverage": "#737373", "valid_coverage": "#22c55e",
}


def observation_plot(observations):
    """Small SVG hydrograph; quality flags remain available in the table below."""
    groups = {}
    for row in observations:
        parameter = row.get("parameter")
        if parameter in ("discharge", "total_precipitation"):
            groups.setdefault((parameter, row.get("series_id")), []).append(row)
    charts = []
    for (parameter, _), rows in groups.items():
        known = [row for row in rows if row.get("value") is not None]
        if not known:
            continue
        rows.sort(key=lambda row: str(row["observed_at"]))
        start = date.fromisoformat(str(rows[0]["observed_at"])[:10])
        end = date.fromisoformat(str(rows[-1]["observed_at"])[:10])
        maximum = max(float(row["value"]) for row in known)
        shapes = []
        for row in known:
            day = date.fromisoformat(str(row["observed_at"])[:10])
            x = 10 + (day-start).days * 280 / max(1, (end-start).days)
            y = 100 - float(row["value"]) * 85 / (maximum or 1)
            color = "#d97706" if row.get("quality_status") == "flagged" else "#2563eb"
            shapes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>')
        label, unit = ("Daily mean discharge", "m³/s") if parameter == "discharge" else ("Daily precipitation", "mm")
        station = html.escape(str(known[0].get("station_name") or known[0].get("series_id")))
        charts.append(f'<h3>{label} · {station}</h3><svg viewBox="0 0 300 115" role="img" aria-label="{label}">{"".join(shapes)}</svg><p>{start} – {end}. Maximum measured: {maximum:.1f} {unit}. {len(rows)-len(known)} missing days. Amber: flagged/estimated values. Missing values remain gaps.</p>')
    return "".join(charts)


def export_preview(output_dir=Path("artifacts")):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    options = []
    for case in db.list_cases():
        run = db.get_run(case["id"])
        if run is None:
            continue
        bbox = case["bbox"]
        map_ = folium.Map(location=[(bbox[1]+bbox[3])/2, (bbox[0]+bbox[2])/2], tiles="OpenStreetMap")
        map_.fit_bounds([[bbox[1],bbox[0]],[bbox[3],bbox[2]]])
        names = run["metadata"].get("layer_names", [])
        counts = {}
        for name in names:
            layer = db.get_layer(case["id"], name, run["id"])
            counts[name] = len(layer["features"])
            if not layer["features"]:
                continue
            color = COLORS.get(name, "#64748b")
            label = "candidate exposure" if name == "exposure" else name.replace("_", " ")
            group = folium.FeatureGroup(name=label, show=name in ("reported_damage", "modeled_new_water", "exposure") or (name == "assets" and case["id"] == "bc-2021"))
            features = []
            for feature in layer["features"]:
                if name == "exposure" and feature["properties"].get("flood_exposure") != "candidate":
                    continue
                feature = dict(feature)
                feature["properties"] = dict(feature.get("properties", {}))
                feature["properties"]["details"] = html.escape(json.dumps(feature["properties"], indent=2, ensure_ascii=False))
                features.append(feature)
            if not features:
                continue
            def style(feature, color=color, name=name):
                state = feature["properties"].get("flood_exposure")
                selected = color if name != "exposure" or state == "candidate" else "#64748b"
                return {"color": selected, "fillColor": selected, "weight": 3 if state == "candidate" else 2,
                        "fillOpacity": 0.3, "dashArray": "5 5" if state == "unknown" else None}
            folium.GeoJson(
                {"type": "FeatureCollection", "features": features},
                style_function=style,
                marker=folium.CircleMarker(radius=4, color=color, fill=True, fill_opacity=0.75),
                popup=folium.GeoJsonPopup(fields=["details"], labels=False, max_width=450),
            ).add_to(group)
            group.add_to(map_)
        folium.LayerControl(collapsed=False).add_to(map_)
        map_path = output_dir / f"{case['id']}-map.html"
        map_.save(str(map_path))
        observations = db.get_observations(case["id"], run["id"]) or []
        details = html.escape(json.dumps(run["metadata"], indent=2, ensure_ascii=False))
        comparison = run["metadata"].get("agency_comparison", {})
        score = comparison.get("intersection_over_union")
        comparison_note = (
            f"Ahr footprint overlap: {score:.1%}. SAR {comparison.get('modeled_observed_at')} versus agency {comparison.get('reference_observed_at')}. Different dates: this is not an accuracy score."
            if score is not None else "No geospatial agency flood reference is available for this case; detector accuracy is unverified."
        )
        page = f'''<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(case['name'])}</title>
<style>body{{margin:0;font:15px system-ui;color:#0f172a}}main{{display:grid;grid-template-columns:minmax(260px,340px) 1fr;height:100vh}}aside{{padding:20px;overflow:auto;background:#f8fafc}}iframe{{width:100%;height:100%;border:0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}svg{{width:100%}}h1{{font-size:24px}}@media(max-width:700px){{main{{grid-template-columns:1fr}}aside{{height:35vh}}iframe{{height:65vh}}}}</style></head><body><main><aside>
<h1>{html.escape(case['name'])}</h1><p>Historical research POC · run {html.escape(run['id'])}</p>
<p>{html.escape(case['description'])}</p><p>Red: agency damage evidence. Blue/cyan: modeled water. Orange: candidate asset exposure. Purple/pink: hypothetical expansion sensitivity. Grey: inventory or unknown observations.</p>
<p>Flood exposure does not establish destruction or route passability. Scenarios have no predicted time or likelihood. Click a feature to inspect evidence.</p>
<p>The candidate exposure overlay displays only flagged intersections. The API exposure layer contains every asset, including unknown and not-detected states.</p>
<p><strong>Experimental water detector.</strong> {html.escape(comparison_note)} Terrain shadow/layover is not screened. Numeric coverage does not prove reliable observation.</p>
{observation_plot(observations)}<details><summary>Layer counts</summary><pre>{html.escape(json.dumps(counts,indent=2))}</pre></details>
<details><summary>Run provenance and limitations</summary><pre>{details}</pre></details>
<details><summary>Observations and quality flags</summary><pre>{html.escape(json.dumps(observations,indent=2))}</pre></details>
<p>Basemap/CDN assets require internet. The underlying run is also available through FastAPI.</p>
</aside><iframe title="Historical flood map" src="{map_path.name}"></iframe></main></body></html>'''
        (output_dir / f"{case['id']}.html").write_text(page)
        options.append((case["id"],case["name"]))
    if not options:
        raise ValueError("No completed runs; run the batch command first")
    selector = "".join(f'<option value="{html.escape(identifier)}.html">{html.escape(name)}</option>' for identifier,name in options)
    (output_dir / "index.html").write_text(f'''<!doctype html><html><head><meta charset="utf-8"><title>FloodBeacon historical POC</title><style>body{{margin:0;font:16px system-ui;background:#0f172a;color:white}}header{{padding:12px 20px}}select{{padding:8px;margin-left:15px}}iframe{{width:100%;height:calc(100vh - 70px);border:0;background:white}}</style></head><body><header>FloodBeacon · historical research POC <select aria-label="Historical case" onchange="document.querySelector('iframe').src=this.value">{selector}</select></header><iframe title="Selected case" src="{options[0][0]}.html"></iframe></body></html>''')
    return output_dir / "index.html"
