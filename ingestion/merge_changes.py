"""CLI for applying phase 1 document changes."""

from __future__ import annotations

import argparse
import json
import sys
import traceback

from config.settings import load_config, load_settings
from ingestion.pipeline import run_ingestion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge phase 1 UPSERT and DELETE changes into Iceberg")
    parser.add_argument("--source", default=None, help="Local or HDFS changes.json or changes.jsonl path")
    parser.add_argument("--upload", action="store_true", help="Upload a local source to the configured HDFS path")
    parser.add_argument("--hdfs-path", default=None, help="Override the HDFS upload destination")
    parser.add_argument("--config", default=None, help="Cluster configuration YAML")
    parser.add_argument("--settings", default=None, help="Spark and ingestion settings YAML")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = run_ingestion(
            phase=1,
            source=args.source,
            upload=args.upload,
            hdfs_path=args.hdfs_path,
            config=load_config(args.config),
            settings=load_settings(args.settings),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        traceback.print_exc()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
