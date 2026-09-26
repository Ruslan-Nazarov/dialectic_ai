"""Download ContractNLI from its official source (Stanford NLP group) and unpack test.json.

The dataset is CC BY 4.0 (Koreeda & Manning, EMNLP Findings 2021) and is not committed to this repo --
this script fetches it on demand into data/contract-nli/ (gitignored).
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

OFFICIAL_URL = "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip"
DEFAULT_DEST = Path(__file__).resolve().parent / "data" / "contract-nli"


def download(dest: Path = DEFAULT_DEST, url: str = OFFICIAL_URL) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    test_json = dest / "test.json"
    if test_json.exists():
        print(f"already present: {test_json}")
        return test_json

    print(f"downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(dest)

    if not test_json.exists():
        # some releases nest one level, e.g. contract-nli/test.json inside the zip root
        candidates = list(dest.rglob("test.json"))
        if not candidates:
            raise FileNotFoundError(f"test.json not found anywhere under {dest} after extraction")
        candidates[0].replace(test_json)

    print(f"done: {test_json}")
    return test_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--url", type=str, default=OFFICIAL_URL)
    args = parser.parse_args()
    download(args.dest, args.url)


if __name__ == "__main__":
    main()
