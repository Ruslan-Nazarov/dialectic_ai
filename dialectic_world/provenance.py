"""Non-secret provenance for new runs; old artifacts are never retroactively relabeled."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess


def run_metadata(ctx) -> dict:
    package = Path(__file__).resolve().parent
    commit, dirty = None, None
    try:
        # A wheel installed into a venv inside a checkout must not inherit that
        # checkout's identity: its installed sources are not tracked Git files.
        subprocess.check_output(["git", "ls-files", "--error-unmatch", "provenance.py"], cwd=package,
                                stderr=subprocess.DEVNULL)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=package,
                                         stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "diff", "HEAD", "--", "."], cwd=package,
                                             stderr=subprocess.DEVNULL))
    except (OSError, subprocess.CalledProcessError):
        pass  # Installed wheels may have no Git checkout.
    return {"schema_version": 2, "code_commit": commit, "tracked_package_dirty": dirty,
            "model": ctx.llm.model, "settings": asdict(ctx.settings),
            "prompt_sha256": {p.name: sha256(p.read_bytes()).hexdigest()
                              for p in sorted((package / "prompts").glob("*.md"))}}
