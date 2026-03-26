"""
HTTP server que expõe o analyzer para o worker chamar via rede interna.
POST /analyze  {"type": "heap|thread", "file": "/tmp/..."}
"""

import sys
import os

sys.path.insert(0, "/analyzer")

from flask import Flask, jsonify, request

from parsers.heap_parser import parse_heap_dump
from parsers.thread_parser import parse_thread_dump

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
        return jsonify({"error": "Campos 'type' e 'file' são obrigatórios"}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"Arquivo não encontrado: {file_path}"}), 404

    if dump_type == "heap":
        result = parse_heap_dump(file_path)
    elif dump_type == "thread":
        result = parse_thread_dump(file_path)
    else:
        return jsonify({"error": f"Tipo inválido: {dump_type}"}), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
