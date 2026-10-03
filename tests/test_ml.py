import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from floodbeacon.ml import _features, _read_chip, _select, load_model, predict_water


def _model():
    model = RandomForestClassifier(n_estimators=8, random_state=42)
    model.fit(_features(np.array([-2., -3., -22., -24.]), np.array([-7., -8., -29., -32.])), [0, 0, 1, 1])
    return model


def test_inference_preserves_unknown_and_does_not_fill_invalid_pixels():
    vv = np.array([[-2., -22.], [np.nan, -24.]])
    vh = np.array([[-7., -29.], [-8., -32.]])
    output = predict_water(_model(), vv, vh, np.array([[True, True], [True, False]]))
    assert output.dtype == np.float32
    assert output[0, 0] < output[0, 1]
    assert np.isnan(output[1]).all()


def test_empty_observation_never_calls_classifier():
    output = predict_water(None, np.zeros((2, 3)), np.zeros((2, 3)), np.zeros((2, 3), dtype=bool))
    assert np.isnan(output).all()


def test_predict_rejects_unaligned_shapes():
    with pytest.raises(ValueError, match="same shape"):
        predict_water(_model(), np.zeros(2), np.zeros(3), np.ones(2))


def test_event_selection_is_reproducible_and_never_crosses_country():
    rows = [[f"{event}_{i}_S1Hand.tif", f"{event}_{i}_LabelHand.tif"] for event in ("Spain", "Bolivia") for i in range(10)]
    chosen = _select(rows, "Spain", 3)
    assert chosen == _select(list(reversed(rows)), "Spain", 3)
    assert len(chosen) == 3
    assert all(row[0].startswith("Spain_") for row in chosen)
    with pytest.raises(ValueError, match="Only"):
        _select(rows, "Ghana", 3)


def test_locally_trained_model_round_trip(tmp_path):
    import pickle

    path = tmp_path / "local.pkl"
    with path.open("wb") as stream:
        pickle.dump(_model(), stream)
    before = predict_water(_model(), np.array([-22.]), np.array([-29.]), np.array([True]))
    after = predict_water(load_model(path), np.array([-22.]), np.array([-29.]), np.array([True]))
    np.testing.assert_array_equal(before, after)


def test_grid_check_accepts_serialization_roundoff_but_rejects_real_offset(tmp_path):
    import rasterio
    from affine import Affine

    sar_path, label_path = tmp_path / "sar.tif", tmp_path / "labels.tif"
    transform = Affine(8.983152841195215e-5, 0, 5, 0, -8.983152841195215e-5, 30)
    profile = {"driver": "GTiff", "width": 2, "height": 2, "crs": "EPSG:4326", "transform": transform}
    with rasterio.open(sar_path, "w", count=2, dtype="float32", **profile) as ds:
        ds.write(np.full((2, 2, 2), -10, dtype="float32"))
    for origin_shift, should_fail in ((0, False), (transform.a / 2, True)):
        label_transform = Affine(transform.a + 6.42e-18, 0, transform.c + origin_shift, 0, transform.e, transform.f)
        with rasterio.open(label_path, "w", count=1, dtype="int16", **{**profile, "transform": label_transform}) as ds:
            ds.write(np.array([[0, 1], [-1, 0]], dtype="int16"), 1)
        if should_fail:
            with pytest.raises(ValueError, match="do not align"):
                _read_chip(sar_path, label_path)
        else:
            _, _, valid, _ = _read_chip(sar_path, label_path)
            assert valid.sum() == 3
