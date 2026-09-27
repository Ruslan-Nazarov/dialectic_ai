"""Loads the owner's prompt_N.md / prompt_N.en.md files from dialectic_world/prompts/ and fills their
{{placeholder}} tokens. The prompt files are authored and edited by the owner, outside the block code;
this module only reads and fills them, never rewrites their wording (PROMPTS_SNAPSHOT_PRE_REWRITE.md).

The path is resolved relative to this package (not the repo root) so a `pip install`ed copy of
dialectic_world -- e.g. as a git dependency of another project -- finds its own bundled prompts
wherever it ends up on disk; see pyproject.toml's [tool.setuptools.package-data]."""
import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def load_prompt(name: str, lang: str = "ru", **fields: str) -> str:
    """`name` is a block's prompt number as a string, e.g. "1".."6". `lang` selects
    prompt_<name>.md ("ru") or prompt_<name>.en.md (anything else, e.g. "en")."""
    suffix = f"prompt_{name}.md" if lang == "ru" else f"prompt_{name}.{lang}.md"
    path = PROMPTS_DIR / suffix
    text = path.read_text(encoding="utf-8")
    needed = set(_PLACEHOLDER.findall(text))
    missing = needed - set(fields)
    if missing:
        raise KeyError(f"{path.name}: no value given for placeholders {sorted(missing)}")
    for key, value in fields.items():
        text = text.replace("{{" + key + "}}", str(value))
    leftover = _PLACEHOLDER.findall(text)
    if leftover:
        raise KeyError(f"{path.name}: placeholders left unfilled: {sorted(set(leftover))}")
    return text
