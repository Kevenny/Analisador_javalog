"""
Parser para arquivos NetBeans Profiler Snapshot (.nps).

Formato detectado por engenharia reversa do arquivo real:
  Magic:   b'nBpRoFiLeR' (10 bytes)
  Header:  14 bytes de metadados
  Offset 24: bloco zlib comprimido

Após descompressão:
  int (4 bytes):  snap_type
  long (8 bytes): time_start (ms epoch)
  long (8 bytes): time_end   (ms epoch)
  byte (1 byte):  flag
  int (4 bytes):  n_items   = número de entradas no call tree
  n_items × 3 writeUTF:
      field1 + field2 + field3
      Se field2 == '' → field1 é nome de thread (marcador de contexto)
      Se field2 != '' → field1=classe, field2=método (frame do call tree)

Suporta também thread dumps em texto (jstack) salvos com extensão .nps.
"""

import re
import struct
import zlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .thread_parser import parse_thread_dump as _parse_jstack

NPS_MAGIC = b'nBpRoFiLeR'
ZLIB_OFFSET = 24  # offset fixo do bloco zlib no arquivo

_JSTACK_INDICATORS = [
    re.compile(r'^"[^"]+".*(?:prio|tid|nid)=', re.MULTILINE),
    re.compile(r'java\.lang\.Thread\.State:', re.MULTILINE),
    re.compile(r'^\s+at [a-zA-Z_$][\w$.]+\.[a-zA-Z_$][\w$]+\(', re.MULTILINE),
]


def _is_jstack_text(path: str) -> bool:
    try:
        with open(path, 'r', errors='replace') as f:
            sample = f.read(32768)
        return sum(1 for p in _JSTACK_INDICATORS if p.search(sample)) >= 2
    except Exception:
        return False


def _is_binary(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
        if not chunk:
            return False
        printable = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
        return (printable / len(chunk)) < 0.75
    except Exception:
        return True


def _read_utf(buf: bytes, pos: int) -> Tuple[str, int]:
    if pos + 2 > len(buf):
        raise EOFError('fim dos dados')
    length = struct.unpack_from('>H', buf, pos)[0]
    end = pos + 2 + length
    if end > len(buf):
        raise EOFError(f'string de tamanho {length} excede dados')
    return buf[pos + 2:end].decode('utf-8', errors='replace'), end


def _parse_netbeans_nps(path: str) -> Dict[str, Any]:
    with open(path, 'rb') as f:
        raw = f.read()

    if not raw.startswith(NPS_MAGIC):
        return _fallback_result(
            f'Arquivo não reconhecido como NetBeans Profiler Snapshot '
            f'(magic esperado: {NPS_MAGIC!r}, encontrado: {raw[:10]!r})'
        )

    # Descomprime o bloco zlib
    try:
        dec = zlib.decompress(raw[ZLIB_OFFSET:])
    except zlib.error as e:
        return _fallback_result(f'Erro ao descomprimir dados do snapshot: {e}')

    # Lê cabeçalho do snapshot descomprimido
    try:
        pos = 0
        snap_type  = struct.unpack_from('>I', dec, pos)[0]; pos += 4
        time_start = struct.unpack_from('>Q', dec, pos)[0]; pos += 8
        time_end   = struct.unpack_from('>Q', dec, pos)[0]; pos += 8
        _flag      = dec[pos]; pos += 1
        n_items    = struct.unpack_from('>I', dec, pos)[0]; pos += 4
    except struct.error as e:
        return _fallback_result(f'Cabeçalho do snapshot inválido: {e}')

    # Lê as n_items triplas writeUTF
    entries: List[Tuple[str, str, str]] = []
    for _ in range(n_items):
        try:
            f1, pos = _read_utf(dec, pos)
            f2, pos = _read_utf(dec, pos)
            f3, pos = _read_utf(dec, pos)
            entries.append((f1, f2, f3))
        except EOFError:
            break

    # Reconstrói threads e seus call trees
    # Regra: field2=='' → marcador de thread; field2!='' → (class, method)
    threads_data: Dict[str, List[str]] = {}
    cur_thread: Optional[str] = None
    cur_frames: List[str] = []

    for f1, f2, f3 in entries:
        if f2 == '':
            if cur_thread is not None:
                if cur_thread not in threads_data:
                    threads_data[cur_thread] = []
                threads_data[cur_thread].extend(cur_frames)
            cur_thread = f1
            cur_frames = []
        else:
            cur_frames.append(f'{f1}.{f2}')

    if cur_thread is not None:
        if cur_thread not in threads_data:
            threads_data[cur_thread] = []
        threads_data[cur_thread].extend(cur_frames)

    if not threads_data:
        return _fallback_result(
            'Nenhuma thread encontrada no snapshot. '
            'O arquivo pode ser de um tipo de snapshot não suportado (ex: memory snapshot).'
        )

    # Converte timestamps epoch ms para ISO string
    def ms_to_iso(ms: int) -> str:
        try:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
        except Exception:
            return str(ms)

    analysis_date = ms_to_iso(time_start)

    # Monta a lista de threads no formato padrão
    threads_out: List[Dict[str, Any]] = []
    for tname, frames in threads_data.items():
        # Remove duplicatas mantendo a ordem do call tree
        seen: set = set()
        unique_frames: List[str] = []
        for f in frames:
            if f not in seen:
                seen.add(f)
                unique_frames.append(f)
        threads_out.append({
            'name': tname,
            'state': 'RUNNABLE',
            'priority': 5,
            'stack_trace': unique_frames,
            'waiting_on': None,
            'locked': [],
        })

    # Hotspots: frames mais frequentes no call tree
    frame_counter: Counter = Counter()
    for frames in threads_data.values():
        frame_counter.update(frames)
    hotspots = [
        {'frame': frame, 'count': cnt}
        for frame, cnt in frame_counter.most_common(30)
    ]

    # Contagem de estados
    state_counts: Dict[str, int] = {}
    for t in threads_out:
        s = t['state']
        state_counts[s] = state_counts.get(s, 0) + 1

    total = len(threads_out)
    total_frames = sum(len(t['stack_trace']) for t in threads_out)

    note = (
        f'Snapshot de CPU do NetBeans Profiler — {total} thread(s) capturada(s), '
        f'{total_frames} frames únicos no call tree. '
        f'Capturado em: {analysis_date}. '
        'Os stack traces representam todos os métodos observados durante o profiling, '
        'não o estado pontual de cada thread.'
    )

    return {
        'summary': {
            'total_threads': total,
            'states': state_counts,
            'deadlocks_found': False,
            'note': note,
        },
        'deadlocks': [],
        'threads': threads_out,
        'hotspots': hotspots,
        'stack_groups': [],
    }


def _fallback_result(mensagem: str) -> Dict[str, Any]:
    return {
        'summary': {
            'total_threads': 0,
            'states': {},
            'deadlocks_found': False,
            'note': mensagem,
        },
        'deadlocks': [],
        'threads': [],
        'hotspots': [],
        'stack_groups': [],
    }


def parse_nps(path: str) -> Dict[str, Any]:
    """
    Analisa um arquivo .nps (NetBeans Profiler Snapshot).

    Fluxo:
      1. Texto no estilo jstack → thread_parser completo
      2. Magic 'nBpRoFiLeR' → parser nativo do formato binário NPS
      3. Texto simples (variante) → tenta thread_parser
      4. Fallback informativo
    """
    # Caso 1: thread dump em texto (jstack)
    if _is_jstack_text(path):
        return _parse_jstack(path)

    # Caso 2: arquivo binário NPS
    if _is_binary(path):
        try:
            with open(path, 'rb') as f:
                magic = f.read(10)
            if magic == NPS_MAGIC:
                return _parse_netbeans_nps(path)
        except Exception:
            pass
        return _fallback_result(
            'Arquivo binário não reconhecido como NetBeans Profiler Snapshot. '
            'Tente exportar o thread dump em texto via VisualVM: aba "Threads" → "Thread Dump".'
        )

    # Caso 3: texto não-jstack
    try:
        result = _parse_jstack(path)
        if result['summary']['total_threads'] > 0:
            return result
    except Exception:
        pass

    return _fallback_result(
        'Não foi possível interpretar o arquivo .nps. '
        'Verifique se é um snapshot válido do NetBeans Profiler ou um thread dump em texto.'
    )
