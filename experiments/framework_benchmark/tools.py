"""
Pure computational tools for the framework benchmark.
Operates on datasets retrieved from benchmark_env by ID string.
Contains strictly numeric calculations without qualitative judgments or interpretations.
"""
import math
import statistics
from typing import Any
from experiments.framework_benchmark.benchmark_env import get_dataset


def calculate_statistics_core(values: list[float]) -> dict[str, Any]:
    """
    Core mathematical calculation on an explicit list of numbers.

    Args:
        values: Non-empty list of float/int values.

    Returns:
        Dictionary with count, mean, median, min, max, range, std_dev.
    """
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"Invalid values type: expected list/tuple, got {type(values).__name__}")

    if len(values) == 0:
        raise ValueError("Cannot calculate statistics for an empty dataset.")

    cleaned: list[float] = []
    for idx, x in enumerate(values):
        if not isinstance(x, (int, float)) or isinstance(x, bool):
            raise TypeError(f"Element at index {idx} ('{x}') is not a number (type: {type(x).__name__}).")
        if math.isnan(x) or math.isinf(x):
            raise ValueError(f"Element at index {idx} is not finite ({x}).")
        cleaned.append(float(x))

    sorted_vals = sorted(cleaned)
    n = len(sorted_vals)
    val_mean = sum(sorted_vals) / n
    val_median = float(statistics.median(sorted_vals))
    val_min = float(sorted_vals[0])
    val_max = float(sorted_vals[-1])
    val_range = round(val_max - val_min, 4)
    val_variance = statistics.variance(sorted_vals) if n > 1 else 0.0
    val_stdev = math.sqrt(val_variance)

    return {
        "count": n,
        "mean": round(val_mean, 4),
        "median": round(val_median, 4),
        "min": round(val_min, 4),
        "max": round(val_max, 4),
        "range": val_range,
        "std_dev": round(val_stdev, 4),
    }


def calculate_statistics(dataset_id: str) -> dict[str, Any]:
    """
    Retrieves the dataset by identifier from benchmark_env and computes summary statistics.

    Args:
        dataset_id: Identifier of the dataset ('A', 'B', etc.).

    Returns:
        Dictionary containing count, mean, median, min, max, range, std_dev.
    """
    dataset = get_dataset(dataset_id)
    stats = calculate_statistics_core(dataset)
    stats["dataset_id"] = dataset_id.strip().upper()
    return stats


def compare_datasets(dataset_id_a: str, dataset_id_b: str) -> dict[str, Any]:
    """
    Compares two datasets by retrieving them and calculating individual statistics
    and arithmetic differences (delta = A - B).

    Args:
        dataset_id_a: First dataset identifier.
        dataset_id_b: Second dataset identifier.

    Returns:
        Dictionary with statistics_a, statistics_b, and exact numerical differences.
    """
    stats_a = calculate_statistics(dataset_id_a)
    stats_b = calculate_statistics(dataset_id_b)

    mean_diff = stats_a["mean"] - stats_b["mean"]
    median_diff = stats_a["median"] - stats_b["median"]
    range_diff = stats_a["range"] - stats_b["range"]
    stdev_diff = stats_a["std_dev"] - stats_b["std_dev"]

    return {
        "statistics_a": stats_a,
        "statistics_b": stats_b,
        "mean_difference": round(mean_diff, 4),
        "median_difference": round(median_diff, 4),
        "range_difference": round(range_diff, 4),
        "std_dev_difference": round(stdev_diff, 4),
    }
