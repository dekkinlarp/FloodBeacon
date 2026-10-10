"""Pixel metrics for research benchmarks; no infrastructure-risk probabilities."""

import numpy as np

CLASSES = ("background", "intact", "damaged", "destroyed")


def pixel_confusion(truth, prediction):
    truth, prediction = np.asarray(truth), np.asarray(prediction)
    if truth.shape != prediction.shape:
        raise ValueError("Truth and prediction grids must match")
    if not np.isin(truth, [0, 1, 2, 3, 255]).all() or not np.isin(prediction, range(4)).all():
        raise ValueError("Unexpected building damage classes")
    valid = truth != 255
    return np.bincount((4 * truth[valid].astype(int) + prediction[valid]).ravel(), minlength=16).reshape(4, 4)


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def segmentation_metrics(matrix):
    matrix = np.asarray(matrix)
    result = {"confusion_matrix_truth_rows_prediction_columns": matrix.tolist(), "per_class": {}}
    for index, name in enumerate(CLASSES):
        tp = int(matrix[index, index])
        actual, predicted = int(matrix[index].sum()), int(matrix[:, index].sum())
        result["per_class"][name] = {
            "truth_pixels": actual, "predicted_pixels": predicted,
            "precision": _ratio(tp, predicted), "recall": _ratio(tp, actual),
            "f1": _ratio(2 * tp, actual + predicted), "iou": _ratio(tp, actual + predicted - tp),
        }
    ious = [row["iou"] for row in result["per_class"].values() if row["iou"] is not None]
    result["macro_iou_observed_unions"] = float(np.mean(ious)) if ious else None
    result["pixel_accuracy"] = _ratio(int(np.trace(matrix)), int(matrix.sum()))
    tp, fp, fn = int(matrix[2:, 2:].sum()), int(matrix[:2, 2:].sum()), int(matrix[2:, :2].sum())
    result["damaged_or_destroyed"] = {
        "true_positive_pixels": tp, "false_positive_pixels": fp, "false_negative_pixels": fn,
        "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn), "iou": _ratio(tp, tp + fp + fn),
    }
    return result
