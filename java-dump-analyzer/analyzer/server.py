"""
HTTP server que expõe o analyzer para o worker chamar via rede interna.
POST /analyze  {"type": "heap|thread|nps", "file": "/tmp/..."}
"""

import struct
import sys
import os
from pathlib import Path

sys.path.insert(0, "/analyzer")

from flask import Flask, jsonify, request

from parsers.heap_parser import parse_heap_dump
from parsers.thread_parser import parse_thread_dump
from parsers.nps_parser import parse_nps

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    dump_type = data.get("type")
    file_path = data.get("file")

    if not dump_type or not file_path:
        return jsonify({"erro": "Os campos 'type' e 'file' são obrigatórios"}), 400

    if not os.path.exists(file_path):
        return jsonify({"erro": f"Arquivo não encontrado: {file_path}"}), 404

    # Auto-detecta .nps mesmo que o tipo informado seja 'thread'
    if dump_type == "thread" and Path(file_path).suffix.lower() == ".nps":
        dump_type = "nps"

    if dump_type == "heap":
        result = parse_heap_dump(file_path)
    elif dump_type == "nps":
        result = parse_nps(file_path)
    elif dump_type == "thread":
        result = parse_thread_dump(file_path)
    else:
        return jsonify({"erro": f"Tipo inválido: {dump_type}. Use 'heap', 'thread' ou 'nps'"}), 400

    return jsonify(result)



@app.route("/inspect", methods=["POST"])
def inspect():
    """
    Endpoint de diagnóstico: retorna os primeiros bytes e strings extraídas do arquivo.
    Útil para depurar arquivos .nps com formato desconhecido.
    """
    data = request.get_json(force=True)
    file_path = data.get("file")
    if not file_path or not os.path.exists(file_path):
        return jsonify({"erro": "Arquivo não encontrado"}), 404

    with open(file_path, 'rb') as f:
        raw = f.read()

    # Primeiros 64 bytes em hex
    hex_header = raw[:64].hex()

    # Todas as strings writeUTF encontradas (sem filtro)
    strings = []
    i = 0
    while i < len(raw) - 2 and len(strings) < 200:
        length = struct.unpack_from('>H', raw, i)[0]
        if 1 <= length <= 300 and i + 2 + length <= len(raw):
            try:
                s = raw[i + 2: i + 2 + length].decode('utf-8')
                if sum(1 for c in s if c.isprintable()) / len(s) > 0.8 and '\n' not in s:
                    strings.append({'offset': i, 'length': length, 'value': s})
                    i += 2 + length
                    continue
            except Exception:
                pass
        i += 1

    return jsonify({
        'file_size': len(raw),
        'hex_header': hex_header,
        'utf_strings_found': len(strings),
        'strings': strings[:100],
    })


