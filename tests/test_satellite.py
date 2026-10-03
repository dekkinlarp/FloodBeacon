import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import shape
from pyproj import Transformer
from shapely.ops import transform

from floodbeacon.satellite import grid_for_bbox, mask_features


def test_polygon_filter_preserves_a_missing_pixel_hole():
    mask = np.ones((5,5), dtype=bool)
    mask[2,2] = False
    grid = from_origin(350000,5500000,20,20)
    features = mask_features(mask,grid,"EPSG:32632",{"kind":"water"},minimum_pixels=4)
    metric = transform(Transformer.from_crs("EPSG:4326","EPSG:32632",always_xy=True).transform,shape(features["features"][0]["geometry"]))
    assert metric.area == pytest.approx(24*400, rel=1e-6)


def test_small_component_filter_does_not_expand_water():
    mask = np.array([[True,False],[False,False]])
    assert mask_features(mask,from_origin(350000,5500000,20,20),"EPSG:32632",{"kind":"water"},minimum_pixels=4)["features"] == []


def test_grid_limit_bounds_memory():
    with pytest.raises(ValueError,match="four million"):
        grid_for_bbox([-125,45,-115,55],"EPSG:32610")
