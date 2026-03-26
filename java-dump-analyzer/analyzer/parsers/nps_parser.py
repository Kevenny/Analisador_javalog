"""
Parser para arquivos NetBeans Profiler Snapshot (.nps) com dados de thread dump.

Estratégia:
  1. Texto com padrões jstack → thread_parser completo
  2. Binário → busca estrutural por pares (nomeThread, nomeClasse) + long timestamps,
     que é exatamente como ThreadsDataManager serializa cada thread no NPS
  3. Fallback: extração ampla de todas strings UTF plausíveis como nomes de thread
"""

import re
import struct
from typing import Any, Dict, List, Optional, Tuple

from .thread_parser import parse_thread_dump as _parse_jstack

# ── Indicadores de thread dump em texto (jstack) ────────────────────────────
_JSTACK_INDICATORS = [
    re.compile(r'^"[^"]+".*(?:prio|tid|nid)=', re.MULTILINE),
    re.compile(r'java\.lang\.Thread\.State:', re.MULTILINE),
    re.compile(r'^\s+at [a-zA-Z_$][\w$.]+\.[a-zA-Z_$][\w$]+\(', re.MULTILINE),
]

# Regex de nome de classe Java (ex: java/lang/Thread ou java.lang.Thread)
_JAVA_CLASS_RE = re.compile(
    r'^(?:[a-zA-Z_$][\w$]*/)*[a-zA-Z_$][\w$]*'
    r'|^(?:[a-zA-Z_$][\w$]*\.)*[a-zA-Z_$][\w$]*$'
)


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


def _read_utf(data: bytes, offset: int) -> Tuple[str, int]:
    """Lê string DataOutputStream.writeUTF: 2 bytes big-endian length + UTF-8."""
    if offset + 2 > len(data):
        raise ValueError('offset além do fim')
    length = struct.unpack_from('>H', data, offset)[0]
    end = offset + 2 + length
    if end > len(data):
        raise ValueError('string excede dados')
    return data[offset + 2:end].decode('utf-8', errors='replace'), end


def _is_valid_thread_name(s: str) -> bool:
    """
    Aceita qualquer string que possa ser nome de thread Java:
    - 1 a 200 caracteres
    - Sem quebra de linha
    - Pelo menos 50% dos caracteres são imprimíveis ASCII
    """
    if not s or len(s) > 200 or '\n' in s or '\r' in s:
        return False
    printable = sum(1 for c in s if 32 <= ord(c) < 127)
    return printable / len(s) >= 0.5


def _is_valid_class_name(s: str) -> bool:
    """Verifica se parece nome de classe Java (com / ou . como separador)."""
    if not s or len(s) > 300 or '\n' in s:
        return False
    return bool(_JAVA_CLASS_RE.match(s)) and ('.' in s or '/' in s or s[0].isupper())


def _find_thread_count(data: bytes, offset: int) -> Optional[int]:
    """Tenta ler um int big-endian plausível como contagem de threads."""
    if offset + 4 > len(data):
        return None
    count = struct.unpack_from('>i', data, offset)[0]
    return count if 1 <= count <= 10000 else None


def _parse_thread_section(data: bytes, start: int, count: int) -> List[Dict[str, Any]]:
    """
    Lê `count` threads a partir de `start`.
    Cada thread: writeUTF(name) + writeUTF(className) + writeLong(birth) + writeLong(death)
    seguido de dados de estado variáveis.
    """
    threads = []
    pos = start
    for _ in range(count):
        try:
            name, pos = _read_utf(data, pos)
            class_name, pos = _read_utf(data, pos)
            # pula birth_time (long 8 bytes) e death_time (long 8 bytes)
            pos += 16
            if _is_valid_thread_name(name):
                threads.append({
                    'name': name,
                    'class_name': class_name,
                    'state': 'DESCONHECIDO',
                    'priority': 5,
                    'stack_trace': [],
                    'waiting_on': None,
                    'locked': [],
                })
        except Exception:
            break
    return threads


def _structured_scan(data: bytes) -> List[Dict[str, Any]]:
    """
    Varre o arquivo procurando a estrutura do ThreadsDataManager:
    int(threadCount) + [writeUTF(name) + writeUTF(className) + long + long] × N
    """
    best: List[Dict[str, Any]] = []
    i = 0
    while i < len(data) - 6:
        count = _find_thread_count(data, i)
        if count is not None:
            threads = _parse_thread_section(data, i + 4, count)
            # Considera válido se conseguiu ler >= 60% das threads esperadas
            if len(threads) >= max(1, count * 0.6) and len(threads) > len(best):
                best = threads
                # Avança além deste bloco encontrado
                i += 4
                continue
        i += 1
    return best


def _broad_utf_scan(data: bytes) -> List[str]:
    """
    Extração ampla: coleta TODAS as strings writeUTF plausíveis como nomes de thread.
    Usado como fallback quando a varredura estrutural não encontra nada.
    """
    candidates: List[str] = []
    seen: set = set()
    i = 0
    while i < len(data) - 2:
        length = struct.unpack_from('>H', data, i)[0]
        if 1 <= length <= 200 and i + 2 + length <= len(data):
            raw = data[i + 2: i + 2 + length]
            try:
                s = raw.decode('utf-8')
                if _is_valid_thread_name(s) and s not in seen:
                    # Exclui strings que claramente são código/path/número
                    if not re.match(r'^[\d./\\:]+$', s) and len(s.split()) <= 8:
                        candidates.append(s)
                        seen.add(s)
                        i += 2 + length
                        continue
            except (UnicodeDecodeError, ZeroDivisionError):
                pass
        i += 1
    return candidates


def _parse_netbeans_binary(path: str) -> Dict[str, Any]:
    with open(path, 'rb') as f:
        data = f.read()

    # Tentativa 1: varredura estrutural (mais precisa)
    threads = _structured_scan(data)

    # Tentativa 2: extração ampla de strings
    if not threads:
        names = _broad_utf_scan(data)
        threads = [
            {
                'name': n,
                'state': 'DESCONHECIDO',
                'priority': 5,
                'stack_trace': [],
                'waiting_on': None,
                'locked': [],
            }
            for n in names
        ]

    if not threads:
        return _fallback_result(
            'Não foi possível extrair dados de threads do arquivo .nps. '
            'Para análise completa exporte o thread dump em texto via VisualVM: '
            'aba "Threads" → botão "Thread Dump".'
        )

    total = len(threads)
    note = (
        f'{total} thread(s) encontrada(s) no snapshot NetBeans Profiler (.nps). '
        'Stack traces não estão disponíveis no formato binário — '
        'exporte como texto via VisualVM para análise completa de stacks.'
    )

    # Agrupa por estado (todos DESCONHECIDO neste formato)
    states: Dict[str, int] = {}
    for t in threads:
        s = t.get('state', 'DESCONHECIDO')
        states[s] = states.get(s, 0) + 1

    return {
        'summary': {
            'total_threads': total,
            'states': states,
            'deadlocks_found': False,
            'note': note,
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
    Analisa um arquivo .nps (NetBeans Profiler Snapshot) como thread dump.

    Fluxo:
      1. Texto no estilo jstack → thread_parser completo
      2. Texto simples variante → tenta thread_parser
      3. Binário → varredura estrutural (pares nome+classe+timestamps)
         → fallback: extração ampla de strings UTF
    """
    if _is_jstack_text(path):
        return _parse_jstack(path)

    if not _is_binary(path):
        try:
            result = _parse_jstack(path)
            if result['summary']['total_threads'] > 0:
                return result
        except Exception:
            pass

    return _parse_netbeans_binary(path)
