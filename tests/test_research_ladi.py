import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_ladi.py"
SPEC = importlib.util.spec_from_file_location("benchmark_ladi", SCRIPT)
assert SPEC and SPEC.loader
benchmark_ladi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark_ladi)


def test_confusion_metrics_distinguish_zero_from_undefined_f1() -> None:
    zero_f1 = benchmark_ladi.confusion_metrics(
        [True, False], [False, True]
    )
    assert zero_f1["tp"] == 0
    assert zero_f1["fp"] == 1
    assert zero_f1["fn"] == 1
    assert zero_f1["precision"] == 0
    assert zero_f1["recall"] == 0
    assert zero_f1["f1"] == 0

    undefined_f1 = benchmark_ladi.confusion_metrics([False], [False])
    assert undefined_f1["support_positive"] == 0
    assert undefined_f1["precision"] is None
    assert undefined_f1["recall"] is None
    assert undefined_f1["f1"] is None
