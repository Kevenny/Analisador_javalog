#!/usr/bin/env python3
"""
Entry point for the Java dump analyzer.
Usage: python3 run_analysis.py --type heap|thread --file <path>
Outputs JSON to stdout.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Java Dump Analyzer")
    parser.add_argument("--type", required=True, choices=["heap", "thread"], help="Dump type")
    parser.add_argument("--file", required=True, help="Path to dump file")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"error": f"File not found: {args.file}"}), file=sys.stderr)
        sys.exit(1)

    if args.type == "thread":
        from parsers.thread_parser import parse_thread_dump
        result = parse_thread_dump(str(file_path))
    else:
        from parsers.heap_parser import parse_heap_dump
        result = parse_heap_dump(str(file_path))

    print(json.dumps(result))


if __name__ == "__main__":
    main()
