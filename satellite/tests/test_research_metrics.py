import numpy as np
import pytest

from floodbeacon.research_metrics import pixel_confusion, segmentation_metrics


def test_ignore_unknown_and_count_damage_confusions():
    matrix = pixel_confusion(np.array([0, 1, 2, 3, 255]), np.array([0, 2, 2, 1, 3]))
    result = segmentation_metrics(matrix)
    assert matrix.sum() == 4
    assert result["damaged_or_destroyed"]["precision"] == 0.5
    assert result["damaged_or_destroyed"]["recall"] == 0.5
    assert result["per_class"]["destroyed"]["precision"] is None
    assert result["per_class"]["destroyed"]["recall"] == 0


def test_empty_support_never_means_perfect_damage_detection():
    result = segmentation_metrics(np.zeros((4, 4), dtype=int))
    assert result["macro_iou_observed_unions"] is None
    assert result["damaged_or_destroyed"]["f1"] is None


def test_misaligned_or_unknown_classes_fail():
    with pytest.raises(ValueError, match="grids"):
        pixel_confusion(np.array([0, 1]), np.array([0]))
    with pytest.raises(ValueError, match="classes"):
        pixel_confusion(np.array([4]), np.array([0]))
