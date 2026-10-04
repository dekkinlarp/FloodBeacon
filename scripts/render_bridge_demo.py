"""Render retrieved manual bridge comparisons without processing new imagery.

Run the three prepare_bridge_demo_* research scripts first, then
``uv run python scripts/render_bridge_demo.py``. No model is run here.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/bridge-demo"


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text())


def collect() -> list[dict]:
    records = []
    for folder, country in [("bridge-demo-other", "Libya"), ("bridge-demo-nepal", "Nepal")]:
        path = f"data/research/{folder}/manifest.json"
        manifest = read(path)
        for target in manifest["targets"]:
            before, after = [target["images"][phase] for phase in ("before", "after")]
            records.append({
                "id": target["id"], "name": target["name"], "country": country,
                "coordinate": target.get("coordinate", [target.get("lon"), target.get("lat")]),
                "finding": target["finding"], "modality": "Satellite RGB",
                "before_date": before.get("acquired_at", before.get("acquisition_time_utc")),
                "after_date": after.get("acquired_at", after.get("acquisition_time_utc")),
                "before": before.get("png", before.get("png_path")),
                "after": after.get("png", after.get("png_path")),
                "comparison": target.get("comparison_png", target.get("comparison_png_path")),
                "manifest": path, "license": manifest["license"],
                "attribution": manifest["attribution"],
                "caveat": manifest.get("interpretation", manifest.get("reference_caveat", "")),
                "source": manifest.get("collection_url", manifest.get("license_source")),
                "recent_reference": target.get("recent_pre_event_reference"),
            })
    for path in sorted((ROOT / "data/research/bridge-demo-existing").glob("*-manifest.json")):
        if path.name.startswith("discarded-"):
            continue
        target = json.loads(path.read_text())
        before, after = target["imagery"]
        records.append({
            "id": target["target_id"], "name": f'{target["target"]} · {target["place"]}',
            "country": "Germany", "coordinate": [target["lon"], target["lat"]],
            "finding": target["manual_finding"], "modality": target["modality"],
            "before_date": before["acquisition_date"],
            "after_date": "Collection flights: " + ", ".join(after["collection_acquisition_dates"]),
            "before": before["png_path"], "after": after["png_path"],
            "comparison": target["annotated_image"], "manifest": str(path.relative_to(ROOT)),
            "license": before["license"], "attribution": before["attribution"],
            "caveat": target["historical_note"] + " " + target["manual_confidence"],
            "source": target["source_url"],
        })
    return records


def render() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = collect()
    buttons, sections, features, files = [], [], [], []
    for i, record in enumerate(records):
        short = record["id"]
        for key in ("before", "after", "comparison", "manifest"):
            source = Path(record[key])
            if not source.is_absolute():
                source = ROOT / source
            dest = OUTPUT / f"{short}-{key}{source.suffix}"
            shutil.copyfile(source, dest)
            record[key] = dest.name
            files.append({"path": dest.name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
        recent = record.get("recent_reference")
        supplemental = ""
        if recent:
            dest = OUTPUT / f"{short}-recent-before.png"
            shutil.copyfile(recent["png_path"], dest)
            files.append({"path": dest.name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
            supplemental = (f'<p class="caveat"><a href="{dest.name}">Recent reference: Planet, 27 May 2026, 3 m</a><br>'
                + html.escape(recent["manual_finding"]) + '<br>' + html.escape(recent["attribution"])
                + ' · ' + html.escape(recent["license"]) + '</p>')
        def e(key: str) -> str:
            return html.escape(str(record[key]), quote=True)
        buttons.append(f'<option value="{e("id")}">{e("country")} · {e("name")}</option>')
        lon, lat = record["coordinate"]
        hidden = " hidden" if i else ""
        sections.append(f'''<section id="{e("id")}"{hidden}>
<div class="heading"><div><p class="tag">{e("country")} · {e("modality")}</p><h2>{e("name")}</h2></div>
<a href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=17/{lat}/{lon}" target="_blank" rel="noreferrer">Locate crossing ↗</a></div>
<p class="finding">{e("finding")}</p>
<a href="{e("comparison")}"><img class="comparison" src="{e("comparison")}" alt="Annotated manual before/after comparison of {e("name")}"></a>
<p class="dates"><strong>Before:</strong> {e("before_date")}<br><strong>After:</strong> {e("after_date")}</p>
<p class="caveat">{e("caveat")}</p>
{supplemental}
<details><summary>Raw images, coordinates and source records</summary>
<p><a href="{e("before")}">Unannotated before</a> · <a href="{e("after")}">Unannotated after</a> · <a href="{e("manifest")}">Full provenance JSON</a> · <a href="{e("source")}">Source collection / agency</a></p>
<p>WGS84 longitude {lon:.6f}, latitude {lat:.6f}. Coordinates locate the reviewed crossing; they are not surveyed engineering points.</p>
<p>{e("attribution")} · {e("license")}</p></details></section>''')
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"id": short, "name": record["name"], "assessment_method": "manual image interpretation",
                "observation": record["finding"], "before_acquisition": record["before_date"],
                "after_acquisition": record["after_date"], "time_caveat": record["caveat"],
                "model_output": False, "source": record["source"], "license": record["license"]}})
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FloodBeacon · bridge image review</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf1f3;color:#192933;font:16px/1.55 system-ui,sans-serif}main{max-width:1450px;margin:auto;padding:32px}
h1{font-size:36px;line-height:1.15;margin:8px 0 14px}h2{margin:0;font-size:25px}.intro{max-width:960px;color:#435964}.tag{font-size:12px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#387267;margin:0 0 5px}
nav{margin:18px 0}select{padding:10px;font:inherit;border:1px solid #bdcbd0;border-radius:8px;background:white;color:#244651;max-width:100%;width:100%}label{font-size:14px}
section{background:white;padding:24px;border-radius:14px;border:1px solid #d3dde1}section[hidden]{display:none}.heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.finding{max-width:1050px}.comparison{display:block;width:100%;height:auto;border-radius:6px}.dates{font-size:14px;color:#3a535f}.caveat{padding:12px 16px;background:#f4f5f3;border-left:3px solid #8a9e93;font-size:14px}a{color:#126f72}details{font-size:14px}summary{cursor:pointer;font-weight:600}footer{margin-top:20px;font-size:14px;color:#4c606c}
@media(max-width:700px){main{padding:18px}h1{font-size:28px}.heading{display:block}section{padding:15px}}
</style><main><p class="tag">FloodBeacon · hackathon research</p><h1>Destroyed crossings, visible from above.</h1>
<p class="intro">Real before/after images, manually marked at reported flood-damage locations. Start with Derna for a satellite demo, or Rech for our existing Germany case.</p>
<nav><label for="bridge">Choose a crossing</label><select id="bridge">BUTTONS</select></nav>SECTIONS
<footer><a href="targets.geojson">Reviewed bridge locations · GeoJSON</a> · <a href="manifest.json">Viewer checksums</a><p>Selected retrospective examples. An unmarked crossing is unassessed. Imagery does not establish safe passage, verified detours, or a precise failure time.</p></footer></main>
<script>document.getElementById('bridge').addEventListener('change',event=>{document.querySelectorAll('section').forEach(section=>section.hidden=section.id!==event.target.value);});</script></html>'''
    (OUTPUT / "index.html").write_text(page.replace("BUTTONS", "\n".join(buttons)).replace("SECTIONS", "\n".join(sections)))
    (OUTPUT / "targets.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2) + "\n")
    (OUTPUT / "manifest.json").write_text(json.dumps({"assessment_method": "manual image review", "targets": records, "files": files}, indent=2) + "\n")
    print(f"Rendered {len(records)} manually reviewed crossings: {OUTPUT / 'index.html'}")


if __name__ == "__main__":
    render()
