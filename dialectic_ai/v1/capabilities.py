from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from dialectic_ai.v1.models import CapabilityRequirement, ExecutionBinding

@dataclass
class CapabilityRecord:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    executor_fn: Callable[[Dict[str, Any]], Dict[str, Any]]

class CapabilityRegistry:
    def __init__(self):
        self._records: Dict[str, CapabilityRecord] = {}

    def register(self, record: CapabilityRecord):
        self._records[record.name] = record

    def lookup(self, requirement: CapabilityRequirement) -> Optional[ExecutionBinding]:
        record = self._records.get(requirement.name)
        if not record:
            return None
        
        # In a real implementation, structural match of schemas would occur here.
        # For V1, we assume the name matches exactly for simplicity.
        return ExecutionBinding(
            id=f"bind_{requirement.id}",
            capability_id=record.name,
            executor_type="function",
            executor_ref=record.name
        )

    def execute(self, binding: ExecutionBinding, input_data: Dict[str, Any]) -> Dict[str, Any]:
        record = self._records.get(binding.executor_ref)
        if not record:
            raise ValueError(f"Capability {binding.executor_ref} not found for execution")
        return record.executor_fn(input_data)
