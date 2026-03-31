"""
Parser para thread dumps Java (jstack e formato .tdump isCOBOL).
Versão aprimorada com categorização, detecção de contenção de lock e insights em português.
"""

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional


_THREAD_HEADER = re.compile(
    r'^"(?P<name>[^"]+)"\s*'
    r'(?:#\d+\s*)?'
    r'(?:daemon\s*)?'
    r'(?:prio=(?P<prio>\d+)\s*)?'
    r'(?:os_prio=\d+\s*)?'
    r'(?:cpu=[\d.]+ms\s*)?'
    r'(?:elapsed=[\d.]+s\s*)?'
    r'(?:tid=0x[0-9a-f]+\s*)?'
    r'(?:nid=0x[0-9a-f]+\s*)?'
    r'(?P<rest>.*)',
    re.IGNORECASE,
)

# Formato alternativo de cabeçalho usado pelo isCOBOL .tdump:
# "thread-name" - Thread t@N
_TDUMP_HEADER = re.compile(
    r'^"(?P<name>[^"]+)"\s*-\s*Thread\s+t@\d+',
    re.IGNORECASE,
)

_STATE_LINE = re.compile(r'java\.lang\.Thread\.State:\s*(\S+)', re.IGNORECASE)
_FRAME_LINE = re.compile(r'^\s+at\s+(\S+)')
_WAITING_ON = re.compile(r'waiting (?:on|to lock) <[^>]+> \(a ([^\)]+)\)')
_LOCKED = re.compile(r'locked <[^>]+> \(a ([^\)]+)\)')
_DEADLOCK_SECTION = re.compile(r'Found \d+ deadlock', re.IGNORECASE)

# Regex aprimorados para capturar ID do lock
_WAITING_ON_LOCK = re.compile(r'-\s+waiting (?:on|to lock) <([0-9a-f]+)> \(a ([^)]+)\)')
_PARKING_WAIT = re.compile(r'-\s+parking to wait for <([0-9a-f]+)> \(a ([^)]+)\)')
_LOCKED_LINE = re.compile(r'-\s+locked <([0-9a-f]+)> \(a ([^)]+)\)')

# Padrão para extrair info JVM do cabeçalho do dump
_JVM_INFO = re.compile(
    r'(Full thread dump|JRE\s+[\d._]+|OpenJDK|HotSpot|Java\s+HotSpot|JVM|java version\s+"[^"]+"|'
    r'VM\s+\(build\s+[^)]+\)|Java\(TM\)|[A-Za-z]+ VM\s+\(.*?\))',
    re.IGNORECASE,
)

_JVM_SYSTEM_NAMES = [
    "reference handler", "finalizer", "signal dispatcher",
    "common-cleaner", "notification thread", "java2d disposer",
    "attach listener", "gc task", "vm thread", "vm periodic",
    "service thread", "c1 compiler thread", "c2 compiler thread",
    "sweeper thread", "codecache sweeper thread",
]

_RMI_NAMES = ["rmi tcp accept", "rmi scheduler", "rmi renewclean", "rmi"]

_MONITORING_NAMES = [
    "check alive", "cleanup", "cleaner", "monitor", "watchdog",
    "heartbeat", "keepalive", "keep-alive",
]

_HTTP_NAMES = ["http", "tomcat", "undertow", "jetty", "nio-", "ajp"]

_SCHEDULER_NAMES = ["scheduler", "timer", "quartz", "cron", "executor"]

_DB_NAMES = ["hikari", "c3p0", "dbcp", "datasource", "jdbc", "pool"]

_RPC_NAMES = ["messageserver", "iscobol", "rpc"]


def _stack_hash(frames: List[str]) -> str:
    key = "|".join(frames[:10])
    return hashlib.md5(key.encode()).hexdigest()[:8]


def _categorize_thread(name: str, frames: List[str]) -> str:
    """Classifica a thread em uma categoria com base no nome e frames da stack."""
    name_lower = name.lower()

    # Threads de sistema JVM
    if any(x in name_lower for x in _JVM_SYSTEM_NAMES):
        return "jvm_sistema"

    # RMI
    if any(x in name_lower for x in _RMI_NAMES):
        return "rmi"

    # Servidor RPC / isCOBOL
    if any(x in name_lower for x in _RPC_NAMES):
        return "servidor_rpc"

    # Monitoramento / manutenção
    if any(x in name_lower for x in _MONITORING_NAMES):
        return "monitoramento"

    # HTTP / servidores web
    if any(x in name_lower for x in _HTTP_NAMES):
        return "http_servidor"

    # Agendador / timer
    if any(x in name_lower for x in _SCHEDULER_NAMES):
        return "agendador"

    # Pool de banco de dados
    if any(x in name_lower for x in _DB_NAMES):
        return "banco_dados"

    # Verifica frames para pacotes de aplicação
    frame_str = " ".join(frames).lower()
    if any(x in frame_str for x in ["com.iscobol", "org.springframework", "com.sun", "javax"]):
        return "aplicacao"

    return "aplicacao"


def _extract_jvm_info(lines: List[str]) -> str:
    """Extrai a linha de informação da JVM do cabeçalho do dump."""
    for line in lines[:50]:
        m = _JVM_INFO.search(line)
        if m:
            stripped = line.strip()
            if stripped and len(stripped) > 5:
                return stripped
    return ""


def _build_categories(threads: List[Dict[str, Any]], total: int) -> Dict[str, Any]:
    """Agrupa threads por categoria e calcula percentuais."""
    # Garante que todas as categorias conhecidas apareçam no resultado, mesmo com 0 threads
    known_categories = [
        "jvm_sistema", "servidor_rpc", "rmi", "monitoramento",
        "aplicacao", "http_servidor", "agendador", "banco_dados",
    ]
    category_map: Dict[str, List[str]] = defaultdict(list)
    for t in threads:
        cat = t.get("category", "aplicacao")
        category_map[cat].append(t["name"])

    categories: Dict[str, Any] = {}
    # Primeiro insere as categorias conhecidas (incluindo as com 0 threads)
    for cat in known_categories:
        names = category_map.get(cat, [])
        count = len(names)
        pct = round(count / total * 100, 1) if total > 0 else 0.0
        categories[cat] = {
            "count": count,
            "percent": pct,
            "threads": names,
        }
    # Depois insere categorias desconhecidas que possam ter sido geradas
    for cat, names in category_map.items():
        if cat not in categories:
            count = len(names)
            pct = round(count / total * 100, 1) if total > 0 else 0.0
            categories[cat] = {
                "count": count,
                "percent": pct,
                "threads": names,
            }
    return categories


def _build_lock_contention(
    lock_holders: Dict[str, str],
    lock_waiters: Dict[str, List[str]],
    lock_types: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Constrói lista de contenção de lock para locks com >= 2 aguardantes ou 1 aguardante + 1 detentor."""
    contention = []
    all_lock_ids = set(lock_holders.keys()) | set(lock_waiters.keys())
    for lock_id in all_lock_ids:
        waiters = lock_waiters.get(lock_id, [])
        holder = lock_holders.get(lock_id)
        if len(waiters) >= 2 or (len(waiters) >= 1 and holder is not None):
            contention.append({
                "lock_id": lock_id,
                "lock_type": lock_types.get(lock_id, "desconhecido"),
                "holder": holder,
                "waiters": waiters,
            })
    # Ordena por número de aguardantes (maior primeiro)
    contention.sort(key=lambda x: -len(x["waiters"]))
    return contention


def _build_insights(
    threads: List[Dict[str, Any]],
    states: Dict[str, int],
    deadlocks: List[Dict[str, Any]],
    lock_contention: List[Dict[str, Any]],
    categories: Dict[str, Any],
    jvm_info: str,
) -> List[Dict[str, Any]]:
    """Gera observações em linguagem natural (português) sobre o dump."""
    insights: List[Dict[str, Any]] = []
    total = len(threads)
    if total == 0:
        return insights

    # Insight: deadlock
    if deadlocks:
        insights.append({
            "nivel": "critico",
            "titulo": "DEADLOCK DETECTADO",
            "descricao": (
                f"Foram encontrados {len(deadlocks)} deadlock(s) no dump. "
                "Intervenção imediata é necessária — as threads envolvidas estão bloqueadas permanentemente."
            ),
        })

    timed_waiting = states.get("TIMED_WAITING", 0)
    blocked = states.get("BLOCKED", 0)
    runnable = states.get("RUNNABLE", 0)
    waiting = states.get("WAITING", 0)

    timed_pct = timed_waiting / total * 100
    blocked_pct = blocked / total * 100

    # Insight: maioria em TIMED_WAITING
    if timed_pct > 60:
        insights.append({
            "nivel": "info",
            "titulo": "Maioria das threads em espera temporizada",
            "descricao": (
                f"{timed_pct:.1f}% das threads ({timed_waiting}/{total}) estão em TIMED_WAITING. "
                "O sistema provavelmente está idle aguardando requisições ou eventos externos."
            ),
        })

    # Insight: alta contenção (BLOCKED)
    if blocked_pct > 10:
        insights.append({
            "nivel": "aviso",
            "titulo": f"Alta contenção: {blocked_pct:.1f}% das threads estão BLOCKED",
            "descricao": (
                f"{blocked} thread(s) estão BLOCKED aguardando a liberação de monitores. "
                "Isso pode indicar gargalos de sincronização ou lentidão em locks."
            ),
        })

    # Insight: contenção de lock
    if lock_contention:
        total_waiters = sum(len(lc["waiters"]) for lc in lock_contention)
        insights.append({
            "nivel": "aviso",
            "titulo": f"Contenção de lock em {len(lock_contention)} lock(s)",
            "descricao": (
                f"{total_waiters} thread(s) aguardando em {len(lock_contention)} lock(s) disputados. "
                "Revise as seções de lock_contention para identificar os recursos mais disputados."
            ),
        })

    # Insight: categoria dominante
    if categories:
        non_empty = {k: v for k, v in categories.items() if v.get("count", 0) > 0}
        if non_empty:
            dominant = max(non_empty.items(), key=lambda x: x[1]["count"])
            dom_name, dom_data = dominant
            cat_labels = {
                "jvm_sistema": "sistema JVM",
                "rmi": "RMI",
                "servidor_rpc": "servidor RPC/isCOBOL",
                "monitoramento": "monitoramento/limpeza",
                "http_servidor": "servidor HTTP",
                "agendador": "agendador/timer",
                "banco_dados": "pool de banco de dados",
                "aplicacao": "aplicação",
            }
            label = cat_labels.get(dom_name, dom_name)
            insights.append({
                "nivel": "info",
                "titulo": f"Categoria dominante: {label}",
                "descricao": (
                    f"{dom_data['count']} thread(s) ({dom_data['percent']}%) pertencem à categoria '{label}'. "
                    "Esta é a maior concentração de threads no dump."
                ),
            })

    # Insight: nenhuma thread de aplicação RUNNABLE
    app_threads = [t for t in threads if t.get("category") in ("aplicacao", "servidor_rpc")]
    app_runnable = [t for t in app_threads if t.get("state") == "RUNNABLE"]
    if app_threads and not app_runnable:
        insights.append({
            "nivel": "aviso",
            "titulo": "Nenhuma thread de aplicação RUNNABLE",
            "descricao": (
                f"Existem {len(app_threads)} thread(s) de aplicação, mas nenhuma está RUNNABLE. "
                "O sistema pode estar idle ou travado aguardando recursos externos."
            ),
        })

    # Insight: threads RMI
    rmi_threads = categories.get("rmi", {})
    if rmi_threads and rmi_threads.get("count", 0) > 0:
        insights.append({
            "nivel": "info",
            "titulo": "Serviço RMI ativo",
            "descricao": (
                f"Serviço RMI ativo com {rmi_threads['count']} thread(s) presente(s) no dump."
            ),
        })

    # Insight: threads de sistema JVM
    jvm_sys = categories.get("jvm_sistema", {})
    if jvm_sys and jvm_sys.get("count", 0) > 0:
        insights.append({
            "nivel": "info",
            "titulo": "Threads internas da JVM",
            "descricao": (
                f"{jvm_sys['count']} thread(s) são threads internas da JVM "
                "(Reference Handler, Finalizer, GC, etc.) e não representam carga da aplicação."
            ),
        })

    # Insight: informação JVM
    if jvm_info:
        insights.append({
            "nivel": "info",
            "titulo": "Versão/ambiente JVM identificado",
            "descricao": jvm_info,
        })

    return insights


def _parse_thread_block(
    lines: List[str],
    i: int,
    thread_name: str,
    priority: int,
    lock_holders: Dict[str, str],
    lock_waiters: Dict[str, List[str]],
    lock_types: Dict[str, str],
) -> tuple:
    """
    Lê as linhas de uma thread a partir da posição i até uma linha em branco.
    Retorna (thread_dict, new_i).
    """
    state = "DESCONHECIDO"
    stack_frames: List[str] = []
    waiting_on: Optional[str] = None
    locked_list: List[str] = []
    thread_lock_ids_waiting: List[str] = []
    thread_lock_ids_held: List[str] = []

    while i < len(lines):
        tline = lines[i]
        if tline.strip() == "":
            break
        sm = _STATE_LINE.search(tline)
        if sm:
            state = sm.group(1)
        fm = _FRAME_LINE.match(tline)
        if fm:
            stack_frames.append(fm.group(1))
        wm = _WAITING_ON.search(tline)
        if wm:
            waiting_on = wm.group(1)

        # Extração de lock com ID
        wlm = _WAITING_ON_LOCK.search(tline)
        if wlm:
            lid, ltype = wlm.group(1), wlm.group(2)
            thread_lock_ids_waiting.append(lid)
            lock_types[lid] = ltype

        pwm = _PARKING_WAIT.search(tline)
        if pwm:
            lid, ltype = pwm.group(1), pwm.group(2)
            thread_lock_ids_waiting.append(lid)
            lock_types[lid] = ltype

        lm_full = _LOCKED_LINE.search(tline)
        if lm_full:
            lid, ltype = lm_full.group(1), lm_full.group(2)
            thread_lock_ids_held.append(lid)
            lock_types[lid] = ltype

        lm = _LOCKED.search(tline)
        if lm:
            locked_list.append(lm.group(1))
        i += 1

    # Registra holdings e waitings nos mapas globais
    for lid in thread_lock_ids_held:
        lock_holders[lid] = thread_name
    for lid in thread_lock_ids_waiting:
        lock_waiters[lid].append(thread_name)

    category = _categorize_thread(thread_name, stack_frames)
    thread_dict = {
        "name": thread_name,
        "state": state,
        "priority": priority,
        "stack_trace": stack_frames,
        "waiting_on": waiting_on,
        "locked": locked_list,
        "category": category,
    }
    return thread_dict, i


def parse_thread_dump(path: str) -> Dict[str, Any]:
    with open(path, "r", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()
    threads: List[Dict[str, Any]] = []
    deadlocks: List[Dict[str, Any]] = []
    in_deadlock = False
    deadlock_buffer: List[str] = []

    # Extração de info JVM do cabeçalho
    jvm_info = _extract_jvm_info(lines)

    # Mapeamentos de lock para análise de contenção
    lock_holders: Dict[str, str] = {}
    lock_waiters: Dict[str, List[str]] = defaultdict(list)
    lock_types: Dict[str, str] = {}

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detecta seção de deadlock
        if _DEADLOCK_SECTION.search(line):
            in_deadlock = True
            deadlock_buffer = [line]
            i += 1
            continue

        if in_deadlock:
            if line.strip() == "" and deadlock_buffer:
                block_text = "\n".join(deadlock_buffer)
                thread_names = re.findall(r'"([^"]+)"', block_text)
                deadlocks.append({"threads": thread_names, "description": block_text})
                deadlock_buffer = []
                in_deadlock = False
            else:
                deadlock_buffer.append(line)
            i += 1
            continue

        if not line.startswith('"'):
            i += 1
            continue

        # Tenta cabeçalho no formato .tdump isCOBOL
        tdump_m = _TDUMP_HEADER.match(line)
        if tdump_m:
            thread_name = tdump_m.group("name")
            i += 1
            thread_dict, i = _parse_thread_block(
                lines, i, thread_name, 5,
                lock_holders, lock_waiters, lock_types,
            )
            threads.append(thread_dict)
            continue

        # Tenta cabeçalho no formato jstack padrão
        jstack_m = _THREAD_HEADER.match(line)
        if jstack_m:
            thread_name = jstack_m.group("name")
            priority = int(jstack_m.group("prio") or 5)
            i += 1
            thread_dict, i = _parse_thread_block(
                lines, i, thread_name, priority,
                lock_holders, lock_waiters, lock_types,
            )
            threads.append(thread_dict)
            continue

        i += 1

    # Contagem de estados
    state_counts: Dict[str, int] = Counter(
        t["state"] for t in threads if t["state"] != "DESCONHECIDO"
    )
    normalized_states: Dict[str, int] = {
        "RUNNABLE": 0,
        "BLOCKED": 0,
        "WAITING": 0,
        "TIMED_WAITING": 0,
    }
    for state, count in state_counts.items():
        key = state.upper()
        if key in normalized_states:
            normalized_states[key] = count
        else:
            normalized_states[key] = count

    # Contagem de threads de sistema JVM vs threads de aplicação
    jvm_system_count = sum(1 for t in threads if t.get("category") == "jvm_sistema")
    app_thread_count = len(threads) - jvm_system_count

    # Categorias
    categories = _build_categories(threads, len(threads))

    # Pontos quentes
    frame_counter: Counter = Counter()
    for t in threads:
        for frame in t["stack_trace"]:
            frame_counter[frame] += 1
    hotspots = [{"frame": frame, "count": cnt} for frame, cnt in frame_counter.most_common(20)]

    # Grupos de stack
    groups: Dict[str, Dict[str, Any]] = {}
    for t in threads:
        if not t["stack_trace"]:
            continue
        h = _stack_hash(t["stack_trace"])
        if h not in groups:
            groups[h] = {
                "stack_hash": h,
                "count": 0,
                "sample_thread": t["name"],
                "frames": t["stack_trace"][:10],
            }
        groups[h]["count"] += 1

    stack_groups = sorted(groups.values(), key=lambda g: -g["count"])

    # Contenção de lock
    lock_contention = _build_lock_contention(lock_holders, dict(lock_waiters), lock_types)

    # Insights
    insights = _build_insights(
        threads, normalized_states, deadlocks, lock_contention, categories, jvm_info
    )

    return {
        "summary": {
            "total_threads": len(threads),
            "states": normalized_states,
            "deadlocks_found": len(deadlocks) > 0,
            "jvm_info": jvm_info,
            "app_threads": app_thread_count,
            "jvm_system_threads": jvm_system_count,
        },
        "categories": categories,
        "lock_contention": lock_contention,
        "insights": insights,
        "deadlocks": deadlocks,
        "threads": threads,
        "hotspots": hotspots,
        "stack_groups": stack_groups,
    }
