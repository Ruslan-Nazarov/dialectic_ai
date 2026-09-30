"""Read-only renderer for the pre-f905f30 world schema.

Preserves 14d9114's brief ordering and soft core limit for historical experiments.
It does not migrate the world or permit current-engine revision of legacy data.
"""
import json
from pathlib import Path


def load_world(path):
    world = json.loads(Path(path).read_text(encoding="utf-8"))
    if "bundles" not in world:
        raise ValueError("Expected a historical bundle-world; use current WorldAdapter for schema 2")
    return world


def process_line(world, pid):
    p = world["processes"][pid]
    return f"[{pid}] {p['source']} → {p['target']}: {p['statement']}"


def brief(world, max_chars=8000):
    core = [f"Область: {world['domain']} (мир, версия {world['version']})"]
    if world.get("p0"):
        core.append(f"Простейший процесс P0: {process_line(world, world['p0']['process_id'])}")
    if world.get("opposite"):
        o = world["opposite"]
        core.append(f"Противоположный процесс: {process_line(world, o['process_id'])}\n"
                    f"  для его развития P0 не требуется: {o['why_not_required']}")
    if world.get("contradiction"):
        c = world["contradiction"]
        core.append(f"Противоречие: {process_line(world, c['process_id'])}\n  единство: {c['unity']}")
    if world.get("resolution"):
        r = world["resolution"]
        core.append(f"Разрешение ({r['kind']}): {process_line(world, r['process_id'])}\n"
                    f"  {r['explanation']}")
    developing, internal = [], []
    for name, title in (("p0", "Развитие P0"), ("opposite", "Развитие противоположного"),
                        ("contradiction", "Развитие противоречия")):
        its = world["bundles"].get(name, {}).get("iterations", [])
        if not its:
            continue
        it = its[-1]
        developing.append(f"{title}:")
        developing += [f"  {process_line(world, pid)}" for pid in it['developing']]
        for pid in it['developing']:
            internal += [f"  · (внутри {pid}) {process_line(world, i)}"
                         for i in it.get('internal', {}).get(pid, [])]
    text = "\n".join(core)
    for block in (developing, internal):
        for line in block:
            if len(text) + len(line) + 1 > max_chars:
                return text
            text += "\n" + line
    return text


class LegacyWorldAdapter:
    def __init__(self, world, max_chars=8000):
        self.world, self.max_chars = world, max_chars

    def brief(self):
        return brief(self.world, self.max_chars)

    def system_prompt(self, role=""):
        # Historical wording, including its limitations, must remain unchanged.
        rule = ('В каждом ответе отметь, укладывается ли то, с чем ты столкнулся (данные задачи, результаты инструментов),\n'
                'в картину мира выше: поле "world_fit": {"fits": true|false, "process_ids": ["id процессов мира, с которыми это связано"],\n'
                '"note": "что именно не укладывается"}. Если ответ не в JSON — последней строкой: WORLD_FIT: {...}.')
        return (f"{role}\n\n" if role else "") + (
            "Ты действуешь в мире, картина которого построена заранее. Опирайся на неё, а не на догадки: "
            "что в этой области простейшее, как оно развивается, какое в нём противоречие и чем оно разрешается.\n\n"
            f"КАРТИНА МИРА\n{self.brief()}\n\n{rule}")
