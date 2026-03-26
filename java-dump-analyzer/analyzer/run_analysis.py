#!/usr/bin/env python3
"""
Entry point do analisador de dumps Java.
Uso: python3 run_analysis.py --type heap|thread|nps --file <caminho>
Saída: JSON no stdout.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Analisador de Dumps Java")
    parser.add_argument(
        "--type",
        required=True,
        choices=["heap", "thread", "nps"],
        help="Tipo do dump: heap (.hprof), thread (jstack .txt) ou nps (NetBeans Profiler .nps)",
    )
    parser.add_argument("--file", required=True, help="Caminho para o arquivo de dump")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(
            json.dumps({"erro": f"Arquivo não encontrado: {args.file}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    dump_type = args.type

    # Auto-detecta pelo sufixo se o tipo informado for genérico
    if dump_type == "thread" and file_path.suffix.lower() == ".nps":
        dump_type = "nps"

    if dump_type == "heap":
        from parsers.heap_parser import parse_heap_dump
        result = parse_heap_dump(str(file_path))
    elif dump_type == "nps":
        from parsers.nps_parser import parse_nps
        result = parse_nps(str(file_path))
    else:
        from parsers.thread_parser import parse_thread_dump
        result = parse_thread_dump(str(file_path))

    print(json.dumps(result))


if __name__ == "__main__":
    main()
