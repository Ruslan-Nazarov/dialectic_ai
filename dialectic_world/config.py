"""Settings (architecture section 6). Every limit lives here, not in the code."""
from dataclasses import dataclass


@dataclass
class Settings:
    developing_min: int = 3          # developing processes per iteration; the model picks within the range
    developing_max: int = 5
    internals_min: int = 2           # internal processes per developing process (A 4.5)
    internals_max: int = 3
    iterations_max: int = 3          # per bundle
    p0_attempts: int = 3
    form_retries: int = 2            # re-asks of a block whose answer has the wrong form
    tool_calls_max: int = 3          # tool calls inside one block call
    brief_max_chars: int = 4000
    revisions_per_session: int = 3
    builder_model: str = "openai:gpt-5"
