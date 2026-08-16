from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

FILES = ("proverbs.json", "facts.json", "quiz_questions.json")


def refresh(data_dir: Path, cache_dir: Path, timeout: int) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now(timezone.utc).date().isoformat()
    for filename in FILES:
        path = data_dir / filename
        entries = json.loads(path.read_text(encoding="utf-8"))
        for entry in entries:
            url = entry.get("source_url", "")
            if not url.startswith("https://"):
                entry["verified"] = False
                continue
            request = Request(url, headers={"User-Agent": "OzgeLeaderboardContentVerifier/1.0"})
            try:
                with urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                    if response.status != 200 or not payload:
                        raise RuntimeError(f"HTTP {response.status}")
                name = hashlib.sha256(url.encode()).hexdigest() + ".source"
                (cache_dir / name).write_bytes(payload)
                entry["retrieved_at"] = checked_at
                entry["source_sha256"] = hashlib.sha256(payload).hexdigest()
            except Exception as exc:
                entry["verified"] = False
                entry["verification_error"] = type(exc).__name__
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and cache cited source material. Semantic verification remains manual.")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "source_cache")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    refresh(args.data_dir, args.cache_dir, args.timeout)


if __name__ == "__main__":
    main()
