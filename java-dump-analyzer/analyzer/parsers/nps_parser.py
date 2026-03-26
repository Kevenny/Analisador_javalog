"""
Parser para arquivos NetBeans Profiler Snapshot (.nps) com dados de thread dump.

Estratégia de detecção:
  1. Se o arquivo contém padrões jstack (texto) → delega ao thread_parser
  2. Se binário com strings legíveis de thread → extrai via leitura binária
  3. Fallback informativo
"""

import re
import struct
from typing import Any, Dict, List, Optional, Tuple

from .thread_parser import parse_thread_dump as _parse_jstack

# Padrões que identificam um thread dump em texto no estilo jstack
_JSTACK_INDICATORS = [
    re.compile(r'^"[^"]+".*(?:prio|tid|nid)=', re.MULTILINE),
    re.compile(r'java\.lang\.Thread\.State:', re.MULTILINE),
    re.compile(r'^\s+at [a-zA-Z_$][\w$.]+\.[a-zA-Z_$][\w$]+\(', re.MULTILINE),
]

# Estados de thread usados pelo NetBeans Profiler (ThreadState enum)
_NB_THREAD_STATE = {
    0: 'DESCONHECIDO',
    1: 'RUNNABLE',    # ALIVE
    2: 'RUNNABLE',
    3: 'TIMED_WAITING',   # sleeping
    4: 'BLOCKED',          # aguardando monitor
    5: 'WAITING',          # Object.wait()
    6: 'WAITING',          # LockSupport.park()
    7: 'TERMINATED',
}


def _is_jstack_text(path: str) -> bool:
    """Retorna True se o arquivo parece ser um thread dump em texto."""
    try:
        with open(path, 'r', errors='replace') as f:
            sample = f.read(32768)
        return sum(1 for p in _JSTACK_INDICATORS if p.search(sample)) >= 2
    except Exception:
        return False


def _is_binary(path: str) -> bool:
    """Retorna True se o arquivo contém dados binários."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
        if not chunk:
            return False
        printable = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
        return (printable / len(chunk)) < 0.75
    except Exception:
        return True


def _read_java_utf(data: bytes, offset: int) -> Tuple[str, int]:
    """
    Lê string no formato DataOutputStream.writeUTF:
    2 bytes big-endian length + bytes UTF-8.
    """
    if offset + 2 > len(data):
        raise ValueError('Offset além do fim dos dados')
    length = struct.unpack_from('>H', data, offset)[0]
    end = offset + 2 + length
    if end > len(data):
        raise ValueError(f'String de comprimento {length} excede os dados')
    s = data[offset + 2:end].decode('utf-8', errors='replace')
    return s, end


def _scan_java_utf_strings(data: bytes, min_len: int = 3, max_len: int = 256) -> List[str]:
    """
    Varre os dados buscando strings no formato writeUTF (2-byte length prefix).
    Retorna apenas strings com conteúdo imprimível.
    """
    results: List[str] = []
    i = 0
    while i < len(data) - 2:
        length = struct.unpack_from('>H', data, i)[0]
        if min_len <= length <= max_len and i + 2 + length <= len(data):
            raw = data[i + 2: i + 2 + length]
            try:
                s = raw.decode('utf-8')
                printable_ratio = sum(1 for c in s if c.isprintable() or c in '\t\n\r') / len(s)
                if printable_ratio > 0.85:
                    results.append(s)
                    i += 2 + length
                    continue
            except (UnicodeDecodeError, ZeroDivisionError):
                pass
        i += 1
    return results


# Padrão de nome de thread Java comum
_THREAD_NAME_RE = re.compile(
    r'^(?:'
    r'main|'
    r'Thread-\d+|'
    r'pool-\d+-thread-\d+|'
    r'[Ff]inalizer|'
    r'Reference\s+Handler|'
    r'Signal\s+Dispatcher|'
    r'Attach\s+Listener|'
    r'Notification\s+Thread|'
    r'GC\s+Thread.*|'
    r'VM\s+Thread|'
    r'VM\s+Periodic\s+Task\s+Thread|'
    r'DestroyJavaVM|'
    r'Monitor\s+Ctrl-Break|'
    r'.*(?:worker|Worker|executor|Executor|thread|Thread|daemon|Daemon).*|'
    r'[\w\s.\-#@]+:\s*\d+'
    r')$'
)


def _parse_netbeans_binary(path: str) -> Dict[str, Any]:
    """
    Extrai informações de threads de um arquivo .nps binário do NetBeans Profiler.
    Usa scan de strings writeUTF para localizar nomes de threads na estrutura binária.
    """
    with open(path, 'rb') as f:
        data = f.read()

    all_strings = _scan_java_utf_strings(data)

    # Filtra strings que parecem nomes de thread
    thread_names: List[str] = []
    seen: set = set()
    for s in all_strings:
        s_stripped = s.strip()
        if (
            s_stripped
            and s_stripped not in seen
            and 2 <= len(s_stripped) <= 128
            and _THREAD_NAME_RE.match(s_stripped)
            and '\n' not in s_stripped
        ):
            thread_names.append(s_stripped)
            seen.add(s_stripped)

    if not thread_names:
        return _fallback_result(
            'Não foi possível extrair nomes de threads do arquivo binário .nps. '
            'Para análise completa exporte o thread dump em texto via VisualVM ou jstack: '
            'no VisualVM → aba "Threads" → botão "Thread Dump".'
        )

    threads = [
        {
            'name': name,
            'state': 'DESCONHECIDO',
            'priority': 5,
            'stack_trace': [],
            'waiting_on': None,
            'locked': [],
        }
        for name in thread_names
    ]

    return {
        'summary': {
            'total_threads': len(threads),
            'states': {'DESCONHECIDO': len(threads)},
            'deadlocks_found': False,
            'note': (
                f'{len(threads)} thread(s) identificada(s) no snapshot NetBeans Profiler. '
                'Stack traces não estão disponíveis no formato binário .nps — '
                'exporte como texto via VisualVM para análise completa.'
            ),
        },
        'deadlocks': [],
        'threads': threads,
        'hotspots': [],
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
    Analisa um arquivo .nps como thread dump.

    Fluxo:
      1. Texto no estilo jstack → thread_parser completo (estados, stacks, deadlocks)
      2. Binário NetBeans Profiler → extração de nomes via scan writeUTF
      3. Fallback com orientação ao usuário
    """
    # Caso 1: arquivo de texto com formato jstack
    if _is_jstack_text(path):
        return _parse_jstack(path)

    # Caso 2: texto simples não-jstack (algumas ferramentas salvam assim)
    if not _is_binary(path):
        # Ainda tenta o parser de texto — pode conter variações de formato
        try:
            result = _parse_jstack(path)
            if result['summary']['total_threads'] > 0:
                return result
        except Exception:
            pass

    # Caso 3: binário NetBeans Profiler
    return _parse_netbeans_binary(path)
