from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a larger synthetic benchmark corpus")
    parser.add_argument("--documents", type=int, default=10000)
    parser.add_argument("--output", default="data/benchmarks/corpus.jsonl")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    topics = ["history", "science", "geography", "technology", "culture", "biology", "mathematics"]
    with output.open("w", encoding="utf-8") as stream:
        for index in range(args.documents):
            topic = topics[index % len(topics)]
            record = {
                "doc_id": str(index),
                "url": f"https://benchmark.invalid/{index}",
                "title": f"{topic} benchmark document {index}",
                "text": f"This {topic} document discusses {topic} benchmark concepts. " * (index % 8 + 1),
                "links": [],
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
