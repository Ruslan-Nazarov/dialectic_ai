"""Settings (architecture section 6). Every limit lives here, not in the code."""
from dataclasses import dataclass


@dataclass
class Settings:
    developing_min: int = 1          # developing processes per iteration; the model picks within the range
    developing_max: int = 6
    iterations_max: int = 3          # of P0's own development, before giving up on finding an opposite
    p0_attempts: int = 3
    form_retries: int = 2            # re-asks of a block whose answer has the wrong form
    tool_calls_max: int = 3          # tool calls inside one block call
    brief_max_chars: int = 4000
    revisions_per_session: int = 3
    builder_model: str = "openai:gpt-5"
    prompt_language: str = "ru"     # "ru" loads prompts/prompt_N.md; anything else loads prompt_N.<lang>.md
    output_language: str = ""       # e.g. "en"; appended as an explicit answer-language directive when set
