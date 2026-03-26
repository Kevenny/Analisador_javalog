"""
Parser nativo para arquivos Java Heap Dump (.hprof).
Lê o formato binário HPROF diretamente, sem dependência do Eclipse MAT.

Referência do formato: https://hg.openjdk.java.net/jdk/jdk/file/tip/src/hotspot/share/services/heapDumper.cpp
"""

import os
import struct
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional

# ── Tags de registro de alto nível ──────────────────────────────────────────
TAG_STRING           = 0x01
TAG_LOAD_CLASS       = 0x02
TAG_HEAP_SUMMARY     = 0x07
TAG_HEAP_DUMP        = 0x0A
TAG_HEAP_DUMP_SEGMENT = 0x1C
TAG_HEAP_DUMP_END    = 0x0B

# ── Sub-tags dentro do segmento HEAP_DUMP ───────────────────────────────────
SUB_ROOT_UNKNOWN      = 0xFF
SUB_ROOT_JNI_GLOBAL   = 0xFE
SUB_ROOT_JNI_LOCAL    = 0xFD
SUB_ROOT_JAVA_FRAME   = 0xFC
SUB_ROOT_NATIVE_STACK = 0xFB
SUB_ROOT_STICKY_CLASS = 0xFA
SUB_ROOT_THREAD_BLOCK = 0xF9
SUB_ROOT_MONITOR_USED = 0xF8
SUB_ROOT_THREAD_OBJ   = 0xF7
SUB_CLASS_DUMP        = 0x20
SUB_INSTANCE_DUMP     = 0x21
SUB_OBJECT_ARRAY_DUMP = 0x22
SUB_PRIMITIVE_ARRAY_DUMP = 0x23

# Tamanho em bytes de cada tipo primitivo
PRIM_SIZE = {
    2: None,  # referência de objeto (usa id_size)
    4: 1,     # boolean
    5: 2,     # char
    6: 4,     # float
    7: 8,     # double
    8: 1,     # byte
    9: 2,     # short
    10: 4,    # int
    11: 8,    # long
}

PRIM_NAMES = {
    4: 'boolean[]', 5: 'char[]', 6: 'float[]', 7: 'double[]',
    8: 'byte[]',    9: 'short[]', 10: 'int[]', 11: 'long[]',
}


def _read_id(f, id_size: int) -> int:
    data = f.read(id_size)
    return struct.unpack('>I', data)[0] if id_size == 4 else struct.unpack('>Q', data)[0]


def _decode_class_name(raw: str) -> str:
    """Converte nome interno JVM (ex: Ljava/lang/String;) para formato legível."""
    if not raw:
        return 'desconhecido'
    dims = 0
    while raw.startswith('['):
        dims += 1
        raw = raw[1:]
    type_map = {
        'B': 'byte', 'C': 'char', 'D': 'double', 'F': 'float',
        'I': 'int',  'J': 'long', 'S': 'short',  'Z': 'boolean',
    }
    if raw in type_map:
        name = type_map[raw]
    elif raw.startswith('L') and raw.endswith(';'):
        name = raw[1:-1].replace('/', '.')
    else:
        name = raw.replace('/', '.')
    return name + '[]' * dims


def _prim_value_size(prim_type: int, id_size: int) -> int:
    if prim_type == 2:
        return id_size
    return PRIM_SIZE.get(prim_type, 4)


def _parse_heap_segment(
    f, id_size: int, end_pos: int,
    class_obj_to_serial: dict,
    serial_to_name_id: dict,
    strings: dict,
    instance_counts: dict,
    instance_bytes_map: dict,
):
    while f.tell() < end_pos:
        sub_data = f.read(1)
        if not sub_data:
            break
        sub = sub_data[0]

        if sub == SUB_ROOT_UNKNOWN:
            _read_id(f, id_size)

        elif sub == SUB_ROOT_JNI_GLOBAL:
            _read_id(f, id_size)
            _read_id(f, id_size)

        elif sub in (SUB_ROOT_JNI_LOCAL, SUB_ROOT_JAVA_FRAME):
            _read_id(f, id_size)
            f.read(8)

        elif sub in (SUB_ROOT_NATIVE_STACK, SUB_ROOT_THREAD_BLOCK):
            _read_id(f, id_size)
            f.read(4)

        elif sub in (SUB_ROOT_STICKY_CLASS, SUB_ROOT_MONITOR_USED):
            _read_id(f, id_size)

        elif sub == SUB_ROOT_THREAD_OBJ:
            _read_id(f, id_size)
            f.read(8)

        elif sub == SUB_CLASS_DUMP:
            # class_id + stack_serial + 6× id (super, loader, signers, domain, reserved×2) + instance_size
            _read_id(f, id_size)          # class_id
            f.read(4)                     # stack_serial
            f.read(id_size * 6)           # super … reserved2
            f.read(4)                     # instance_size

            # Constant pool
            cp_count = struct.unpack('>H', f.read(2))[0]
            for _ in range(cp_count):
                f.read(2)                 # cp index
                ptype = f.read(1)[0]
                f.read(_prim_value_size(ptype, id_size))

            # Static fields
            sf_count = struct.unpack('>H', f.read(2))[0]
            for _ in range(sf_count):
                _read_id(f, id_size)      # name string id
                ptype = f.read(1)[0]
                f.read(_prim_value_size(ptype, id_size))

            # Instance field descriptors (nome + tipo, sem valor)
            if_count = struct.unpack('>H', f.read(2))[0]
            for _ in range(if_count):
                _read_id(f, id_size)      # name string id
                f.read(1)                 # type

        elif sub == SUB_INSTANCE_DUMP:
            _read_id(f, id_size)          # object_id
            f.read(4)                     # stack_serial
            class_id = _read_id(f, id_size)
            data_len = struct.unpack('>I', f.read(4))[0]
            f.read(data_len)

            serial = class_obj_to_serial.get(class_id)
            if serial is not None:
                name_id = serial_to_name_id.get(serial)
                name = _decode_class_name(strings.get(name_id, f'classe_{serial}'))
                instance_counts[name] += 1
                instance_bytes_map[name] += data_len + 16  # +16 cabeçalho objeto

        elif sub == SUB_OBJECT_ARRAY_DUMP:
            _read_id(f, id_size)          # object_id
            f.read(4)                     # stack_serial
            num_elems = struct.unpack('>I', f.read(4))[0]
            elem_class_id = _read_id(f, id_size)
            f.read(num_elems * id_size)

            serial = class_obj_to_serial.get(elem_class_id)
            if serial is not None:
                name_id = serial_to_name_id.get(serial)
                name = _decode_class_name(strings.get(name_id, 'Object')) + '[]'
            else:
                name = 'Object[]'
            instance_counts[name] += 1
            instance_bytes_map[name] += num_elems * id_size + 16

        elif sub == SUB_PRIMITIVE_ARRAY_DUMP:
            _read_id(f, id_size)          # object_id
            f.read(4)                     # stack_serial
            num_elems = struct.unpack('>I', f.read(4))[0]
            elem_type = f.read(1)[0]
            elem_size = PRIM_SIZE.get(elem_type, 1)
            f.read(num_elems * elem_size)

            name = PRIM_NAMES.get(elem_type, 'primitivo[]')
            instance_counts[name] += 1
            instance_bytes_map[name] += num_elems * elem_size + 16

        else:
            # Sub-tag desconhecido — não é seguro continuar neste segmento
            break


def parse_heap_dump(hprof_path: str) -> dict:
    """
    Faz a análise completa de um arquivo .hprof sem dependências externas.
    Retorna dicionário com resumo, consumidores, suspeitos de vazamento e árvore dominadora.
    """
    file_size = os.path.getsize(hprof_path)

    strings: Dict[int, str] = {}
    serial_to_name_id: Dict[int, int] = {}
    class_obj_to_serial: Dict[int, int] = {}
    instance_counts: Dict[str, int] = defaultdict(int)
    instance_bytes_map: Dict[str, int] = defaultdict(int)
    heap_summary: Optional[dict] = None
    parse_note: Optional[str] = None

    try:
        with open(hprof_path, 'rb') as f:
            # Cabeçalho: string terminada em \0
            header = bytearray()
            while True:
                b = f.read(1)
                if not b or b == b'\x00':
                    break
                header += b

            header_str = header.decode('ascii', errors='replace')
            if not header_str.startswith('JAVA PROFILE'):
                raise ValueError(
                    'O arquivo não parece ser um heap dump HPROF válido '
                    f'(cabeçalho: "{header_str[:30]}")'
                )

            raw_id_size = f.read(4)
            if len(raw_id_size) < 4:
                raise ValueError('Arquivo HPROF truncado no cabeçalho')
            id_size = struct.unpack('>I', raw_id_size)[0]
            if id_size not in (4, 8):
                raise ValueError(f'Tamanho de ID inválido no cabeçalho: {id_size}')

            f.read(8)  # timestamp de criação

            while True:
                tag_data = f.read(1)
                if not tag_data:
                    break
                tag = tag_data[0]

                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                length = struct.unpack('>I', hdr[4:])[0]

                if tag == TAG_STRING:
                    if length < id_size:
                        f.read(length)
                        continue
                    str_id = _read_id(f, id_size)
                    str_bytes = f.read(length - id_size)
                    strings[str_id] = str_bytes.decode('utf-8', errors='replace')

                elif tag == TAG_LOAD_CLASS:
                    serial = struct.unpack('>I', f.read(4))[0]
                    obj_id = _read_id(f, id_size)
                    f.read(4)                    # stack trace serial
                    name_id = _read_id(f, id_size)
                    serial_to_name_id[serial] = name_id
                    class_obj_to_serial[obj_id] = serial

                elif tag == TAG_HEAP_SUMMARY:
                    live_bytes     = struct.unpack('>I', f.read(4))[0]
                    live_instances = struct.unpack('>I', f.read(4))[0]
                    f.read(16)   # total alloc bytes + instances (históricas)
                    heap_summary = {
                        'live_bytes': live_bytes,
                        'live_instances': live_instances,
                    }

                elif tag in (TAG_HEAP_DUMP, TAG_HEAP_DUMP_SEGMENT):
                    end_pos = f.tell() + length
                    try:
                        _parse_heap_segment(
                            f, id_size, end_pos,
                            class_obj_to_serial, serial_to_name_id, strings,
                            instance_counts, instance_bytes_map,
                        )
                    except Exception as seg_err:
                        parse_note = f'Segmento do heap parcialmente lido: {seg_err}'
                    f.seek(end_pos)

                else:
                    f.seek(length, 1)

    except Exception as e:
        parse_note = f'Erro durante a leitura do arquivo: {e}'

    return _build_result(
        file_size, instance_counts, instance_bytes_map, heap_summary, parse_note
    )


def _build_result(
    file_size: int,
    instance_counts: dict,
    instance_bytes_map: dict,
    heap_summary: Optional[dict],
    note: Optional[str],
) -> dict:
    total_objects = sum(instance_counts.values())
    total_retained = sum(instance_bytes_map.values())
    heap_bytes = (
        heap_summary['live_bytes']
        if heap_summary and heap_summary['live_bytes'] > 0
        else total_retained or file_size
    )

    # Top consumidores por bytes retidos
    sorted_classes = sorted(instance_bytes_map.items(), key=lambda x: -x[1])

    top_consumers = []
    for class_name, retained in sorted_classes[:20]:
        pct = round(retained / heap_bytes * 100, 2) if heap_bytes else 0
        top_consumers.append({
            'class_name': class_name,
            'instances': instance_counts[class_name],
            'retained_bytes': retained,
            'percentage': pct,
        })

    # Suspeitos de vazamento: classes com alta concentração de instâncias
    threshold = max(500, total_objects * 0.03)
    leak_suspects = []
    for class_name, count in sorted(instance_counts.items(), key=lambda x: -x[1]):
        if count < threshold:
            break
        retained = instance_bytes_map[class_name]
        pct = round(retained / heap_bytes * 100, 2) if heap_bytes else 0
        leak_suspects.append({
            'description': (
                f'{class_name} — {count:,} instâncias acumuladas '
                f'({pct:.1f}% do heap)'
            ),
            'retained_bytes': retained,
            'percentage': pct,
        })
        if len(leak_suspects) >= 10:
            break

    # Árvore de dominadores (aproximação: top classes por bytes retidos)
    dominator_tree = [
        {
            'object': entry['class_name'],
            'retained_bytes': entry['retained_bytes'],
            'percentage': entry['percentage'],
        }
        for entry in top_consumers[:10]
    ]

    summary: dict = {
        'heap_size_bytes': heap_bytes,
        'total_objects': total_objects,
        'analysis_date': datetime.utcnow().isoformat(),
    }
    if note:
        summary['note'] = note

    return {
        'summary': summary,
        'leak_suspects': leak_suspects,
        'top_consumers': top_consumers,
        'dominator_tree': dominator_tree,
    }
