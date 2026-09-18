"""
Tools for the OpenAI Agents SDK experiment.
Provides statistical calculation and dataset comparison capabilities.
"""
from typing import Any
import math
import statistics
from agents import function_tool


def calculate_statistics_fn(values: list[float]) -> dict[str, Any]:
    """
    Calculate summary statistics (mean, median, min, max, count) for a list of numbers.

    Args:
        values: Non-empty list of numeric values (ints or floats).

    Returns:
        Dictionary with count, mean, median, min, max.
    """
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"Invalid input type: expected list of numbers, got {type(values).__name__}")

    if len(values) == 0:
        raise ValueError("Cannot calculate statistics for an empty dataset.")

    cleaned_values: list[float] = []
    for idx, item in enumerate(values):
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise TypeError(f"Element at index {idx} ('{item}') is not a number (type: {type(item).__name__}).")
        if math.isnan(item) or math.isinf(item):
            raise ValueError(f"Element at index {idx} is not finite ({item}).")
        cleaned_values.append(float(item))

    sorted_vals = sorted(cleaned_values)
    n = len(sorted_vals)
    val_mean = sum(sorted_vals) / n
    val_median = statistics.median(sorted_vals)
    val_min = sorted_vals[0]
    val_max = sorted_vals[-1]
    val_variance = statistics.variance(sorted_vals) if n > 1 else 0.0

    return {
        "count": n,
        "mean": round(val_mean, 4),
        "median": round(val_median, 4),
        "min": round(val_min, 4),
        "max": round(val_max, 4),
        "std_dev": round(math.sqrt(val_variance), 4),
    }


def compare_datasets_fn(
    dataset_a: list[float],
    dataset_b: list[float],
    label_a: str = "Group A",
    label_b: str = "Group B",
) -> dict[str, Any]:
    """
    Compare two numeric datasets by calculating their individual summary statistics
    and differential metrics (difference in means, difference in medians, range discrepancy).

    Args:
        dataset_a: First dataset of numbers.
        dataset_b: Second dataset of numbers.
        label_a: Descriptive label for first group.
        label_b: Descriptive label for second group.

    Returns:
        Comprehensive comparison dictionary.
    """
    try:
        stats_a = calculate_statistics_fn(dataset_a)
    except Exception as e:
        raise ValueError(f"Error in {label_a}: {e}") from e

    try:
        stats_b = calculate_statistics_fn(dataset_b)
    except Exception as e:
        raise ValueError(f"Error in {label_b}: {e}") from e

    mean_diff = stats_a["mean"] - stats_b["mean"]
    median_diff = stats_a["median"] - stats_b["median"]

    # Analysis of dispersion divergence
    range_a = stats_a["max"] - stats_a["min"]
    range_b = stats_b["max"] - stats_b["min"]

    is_mean_similar_but_median_different = abs(mean_diff) < 0.05 * max(abs(stats_a["mean"]), 1e-6) and abs(median_diff) > 0.2 * max(abs(stats_a["median"]), 1e-6)

    return {
        label_a: stats_a,
        label_b: stats_b,
        "comparison": {
            "mean_difference": round(mean_diff, 4),
            "median_difference": round(median_diff, 4),
            "range_a": round(range_a, 4),
            "range_b": round(range_b, 4),
            "similar_means": abs(mean_diff) < 1e-4,
            "divergent_medians": abs(median_diff) > 1.0,
            "key_takeaway": (
                "Both groups share nearly identical means, but their distributions and medians differ drastically."
                if is_mean_similar_but_median_different
                else "Comparison metrics computed."
            ),
        }
    }


# Exported OpenAI Agents SDK FunctionTools
calculate_statistics = function_tool(
    calculate_statistics_fn,
    name_override="calculate_statistics",
    description_override="Calculate statistical metrics (count, mean, median, min, max, std_dev) for a list of numbers.",
)

compare_datasets = function_tool(
    compare_datasets_fn,
    name_override="compare_datasets",
    description_override="Compare two datasets to evaluate whether equal/similar means hide major differences in distribution, median, or range.",
)
