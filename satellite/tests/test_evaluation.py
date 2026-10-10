import pytest
from pyproj import Transformer
from shapely.geometry import box, mapping
from shapely.ops import transform

from floodbeacon.evaluation import compare_water_reference


CRS = "EPSG:32632"
to_wgs84 = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform


def polygons(*bounds):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"fixture": "synthetic"},
         "geometry": mapping(transform(to_wgs84, box(*bound)))} for bound in bounds
    ]}


def test_metric_agreement_clips_both_sources_and_deduplicates_overlaps():
    coverage = polygons((500000, 5500000, 500100, 5500100))
    # Two duplicate 200m rectangles must not double-count modeled area.
    modeled = polygons((500000, 5500000, 500200, 5500100),
                       (500000, 5500000, 500200, 5500100))
    reference = polygons((500050, 5500000, 500150, 5500100))
    result = compare_water_reference(modeled, reference, coverage, CRS,
                                     modeled_observed_at="2021-07-15T05:50:52Z",
                                     reference_observed_at="2021-07-18")
    assert result["coverage_area_m2"] == pytest.approx(10000, abs=0.001)
    assert result["modeled_area_m2"] == pytest.approx(10000, abs=0.001)
    assert result["reference_area_m2"] == pytest.approx(5000, abs=0.001)
    assert result["intersection_area_m2"] == pytest.approx(5000, abs=0.001)
    assert result["union_area_m2"] == pytest.approx(10000, abs=0.001)
    assert result["intersection_over_union"] == pytest.approx(0.5, abs=1e-7)
    assert result["comparison_type"] == "retrospective_spatial_agreement"
    assert result["accuracy_claim_supported"] is False
    assert result["reference_observed_at"] == "2021-07-18"


def test_empty_union_does_not_invent_perfect_score():
    result = compare_water_reference(polygons(), polygons(),
                                     polygons((500000, 5500000, 500100, 5500100)), CRS)
    assert result["status"] == "empty_union"
    assert result["union_area_m2"] == 0
    assert result["intersection_over_union"] is None


def test_missing_reference_is_distinct_from_empty_reference():
    result = compare_water_reference(polygons(), None,
                                     polygons((500000, 5500000, 500100, 5500100)), CRS)
    assert result["status"] == "reference_unavailable"
    assert result["reference_area_m2"] is None


def test_missing_coverage_does_not_interpret_unexamined_region_as_dry():
    result = compare_water_reference(polygons((500000, 5500000, 500100, 5500100)),
                                     polygons(), polygons(), CRS)
    assert result["status"] == "no_valid_coverage"
    assert result["modeled_area_m2"] is None
    assert result["intersection_over_union"] is None


@pytest.mark.parametrize("crs", ["EPSG:4326", "EPSG:2263"])
def test_rejects_nonmetric_or_geographic_crs(crs):
    with pytest.raises(ValueError, match="metre"):
        compare_water_reference(polygons(), polygons(), polygons(), crs)


def test_rejects_invalid_reference_geometry_instead_of_silently_repairing():
    reference = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
            [[7, 50], [8, 51], [7, 51], [8, 50], [7, 50]]]}, "properties": {}}
    ]}
    with pytest.raises(ValueError, match="valid polygon"):
        compare_water_reference(polygons(), reference,
                                polygons((500000, 5500000, 500100, 5500100)), CRS)
