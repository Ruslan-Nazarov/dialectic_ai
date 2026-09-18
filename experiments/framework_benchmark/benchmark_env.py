"""
Benchmark Environment: isolated data store for the evaluation.
Datasets are kept server-side and identified only by ID strings ('A', 'B'),
preventing the LLM from inspecting the raw values directly in prompt.
"""
from typing import Mapping, Any

_DATASETS: Mapping[str, list[Any]] = {
    "A": [40.0, 45.0, 50.0, 55.0, 60.0],
    "B": [10.0, 10.0, 10.0, 20.0, 200.0],
    # Private fixtures for Stage 4 isolated tools verification (never exposed to prompts)
    "__TEST_EMPTY__": [],
    "__TEST_INVALID__": [10.0, "not-a-number", 30.0],
}


def get_dataset(dataset_id: str) -> list[Any]:
    """
    Retrieve a clean copy of the requested dataset by identifier.

    Args:
        dataset_id: Identifier of the dataset ('A', 'B', etc.). Case-insensitive.

    Returns:
        A new list copy of numbers.

    Raises:
        ValueError: If the dataset_id is not recognized.
    """
    if not isinstance(dataset_id, str):
        raise TypeError(f"dataset_id must be a string, got {type(dataset_id).__name__}")

    normalized_id = dataset_id.strip().upper()
    if normalized_id not in _DATASETS:
        available = ", ".join(sorted([k for k in _DATASETS.keys() if not k.startswith("__")]))
        raise ValueError(f"Unknown dataset '{dataset_id}'. Available datasets: {available}")

    return list(_DATASETS[normalized_id])


def list_available_dataset_ids() -> list[str]:
    """Returns the list of public dataset identifiers (excluding private fixtures)."""
    return sorted([k for k in _DATASETS.keys() if not k.startswith("__")])

