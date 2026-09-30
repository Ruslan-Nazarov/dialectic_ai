"""Worlds are saved one JSON file per version; old versions are never overwritten."""
import re
from pathlib import Path

from dialectic_world.world.model import World


def slug(domain: str) -> str:
    s = re.sub(r"[^\w]+", "_", domain.lower(), flags=re.UNICODE).strip("_")
    return s[:60] or "domain"


class WorldStore:
    def __init__(self, root: str | Path = "worlds"):
        self.root = Path(root)

    def path(self, world: World) -> Path:
        return self.root / slug(world.domain) / f"v{world.version}.json"

    def save(self, world: World) -> Path:
        path = self.path(world)
        if path.exists():
            raise FileExistsError(f"{path} exists: a saved version is never overwritten")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(world.model_dump_json(indent=1))
        return path

    def versions(self, domain: str) -> list[int]:
        folder = self.root / slug(domain)
        return sorted(int(p.stem[1:]) for p in folder.glob("v*.json")) if folder.exists() else []

    def load(self, domain: str, version: int | None = None) -> World:
        versions = self.versions(domain)
        if not versions:
            raise FileNotFoundError(f"no saved world for {domain!r}")
        v = version or versions[-1]
        return World.model_validate_json((self.root / slug(domain) / f"v{v}.json").read_text(encoding="utf-8"))
