"""Spatial exposure and explicit footprint-expansion sensitivity scenarios."""

from copy import deepcopy

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union


def exposure_layers(assets, flood, coverage, crs, *, exposure_observed_at=None):
    """Keep reported damage independent from hypothetical exposure attributes."""
    to_metric = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    wet = unary_union([transform(to_metric, shape(f["geometry"])) for f in flood["features"]])
    valid = unary_union([transform(to_metric, shape(f["geometry"])) for f in coverage["features"]])
    scenarios = {distance: wet.buffer(distance) for distance in (50, 100)}
    if exposure_observed_at is None and flood["features"]:
        exposure_observed_at = flood["features"][0]["properties"].get("observed_at")
    outcomes = {"exposure": [], "scenario_50m": [], "scenario_100m": []}
    for feature in assets["features"]:
        geometry = transform(to_metric, shape(feature["geometry"]))
        covered = valid.covers(geometry)
        exposed = wet.intersects(geometry)
        current = deepcopy(feature)
        current["properties"].update({
            "evidence_type": "modeled_exposure",
            "flood_exposure": "candidate" if exposed else "not_detected" if covered else "unknown",
            "coverage_complete": covered, "route_passability": "unknown",
            "exposure_observed_at": exposure_observed_at,
            "exposure_method": "Intersection with modeled new water on the satellite grid",
            "exposure_note": "Bridge deck/approach elevation and actual damage require separate evidence.",
        })
        outcomes["exposure"].append(current)
        for distance in (50, 100):
            # Sensitivity scenario, not a rainfall-to-inundation or hydraulic model.
            if not exposed and covered and scenarios[distance].intersects(geometry):
                projected = deepcopy(feature)
                projected["properties"].update({
                    "evidence_type": "scenario_risk", "scenario_id": f"expansion_{distance}m",
                    "assumed_expansion_m": distance, "forecast_horizon_hours": None,
                    "scenario_basis_observed_at": exposure_observed_at,
                    "scenario_note": "Hypothetical horizontal flood footprint expansion; no likelihood or timing inferred.",
                })
                outcomes[f"scenario_{distance}m"].append(projected)
    return {name: {"type": "FeatureCollection", "features": rows} for name, rows in outcomes.items()}
