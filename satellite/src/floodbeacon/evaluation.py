"""Retrospective spatial agreement, with no claim of detector accuracy."""

from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union


def _polygon_union(collection: dict, to_metric):
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Comparison inputs must be GeoJSON FeatureCollections")
    polygons = []
    for feature in collection["features"]:
        geometry = shape(feature["geometry"])
        if geometry.geom_type not in ("Polygon", "MultiPolygon") or not geometry.is_valid:
            raise ValueError("Comparison requires valid polygon geometries")
        metric = transform(to_metric, geometry)
        if not metric.is_valid:
            raise ValueError("Geometry became invalid in the comparison CRS")
        polygons.append(metric)
    return unary_union(polygons)


def compare_water_reference(
    modeled: dict, reference: dict | None, coverage: dict, crs: str,
    *, modeled_observed_at: str | None = None, reference_observed_at: str | None = None,
) -> dict:
    """Compare polygon unions only inside supplied jointly valid coverage.

    Inputs are WGS84 GeoJSON. The caller supplies a suitable local projected
    CRS in metres and the observation dates of both evidence sources. Missing
    reference/coverage and an empty union produce an undefined score (None),
    never fabricated perfect agreement. This statistic measures spatial
    agreement of the two supplied footprints, even when their dates differ.
    """
    projected = CRS.from_user_input(crs)
    if not projected.is_projected or not projected.axis_info or any(
        axis.unit_conversion_factor != 1 for axis in projected.axis_info[:2]
    ):
        raise ValueError("Comparison CRS must be projected with metre units")
    to_metric = Transformer.from_crs("EPSG:4326", projected, always_xy=True).transform
    valid = _polygon_union(coverage, to_metric)
    result = {
        "comparison_type": "retrospective_spatial_agreement",
        "accuracy_claim_supported": False,
        "status": "reference_unavailable" if reference is None else "no_valid_coverage",
        "crs": projected.to_string(),
        "modeled_observed_at": modeled_observed_at,
        "reference_observed_at": reference_observed_at,
        "coverage_area_m2": float(valid.area),
        "modeled_area_m2": None, "reference_area_m2": None,
        "intersection_area_m2": None, "union_area_m2": None,
        "intersection_over_union": None,
        "limitations": [
            "Spatial agreement is not detector accuracy; source observations can have different dates and methods.",
            "The supplied coverage mask does not independently establish cloud, radar shadow or layover quality.",
            "Only polygon footprints inside supplied valid coverage are compared; unmapped areas remain unknown.",
            "Water agreement does not assess structural destruction, closure or route passability.",
        ],
    }
    if reference is None or valid.is_empty:
        return result
    water = _polygon_union(modeled, to_metric).intersection(valid)
    agency = _polygon_union(reference, to_metric).intersection(valid)
    intersection = water.intersection(agency).area
    union = water.union(agency).area
    result.update({
        "status": "compared" if union > 0 else "empty_union",
        "modeled_area_m2": float(water.area), "reference_area_m2": float(agency.area),
        "intersection_area_m2": float(intersection), "union_area_m2": float(union),
        "intersection_over_union": float(intersection / union) if union > 0 else None,
    })
    return result
