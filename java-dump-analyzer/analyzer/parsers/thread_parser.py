"""
Parser for jstack / Java thread dumps.
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

_STATE_LINE = re.compile(r'java\.lang\.Thread\.State:\s*(\S+)', re.IGNORECASE)
_FRAME_LINE = re.compile(r'^\s+at\s+(\S+)')
_WAITING_ON = re.compile(r'waiting (?:on|to lock) <[^>]+> \(a ([^\)]+)\)')
_LOCKED = re.compile(r'locked <[^>]+> \(a ([^\)]+)\)')
_DEADLOCK_SECTION = re.compile(r'Found \d+ deadlock', re.IGNORECASE)


def _stack_hash(frames: List[str]) -> str:
    key = "|".join(frames[:10])
    return hashlib.md5(key.encode()).hexdigest()[:8]


def parse_thread_dump(path: str) -> Dict[str, Any]:
    with open(path, "r", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()
    threads: List[Dict[str, Any]] = []
    deadlocks: List[Dict[str, Any]] = []
    in_deadlock = False
    deadlock_buffer: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect deadlock section
        if _DEADLOCK_SECTION.search(line):
            in_deadlock = True
            deadlock_buffer = [line]
            i += 1
            continue

        if in_deadlock:
            if line.strip() == "" and deadlock_buffer:
                # End of deadlock block — parse it
                block_text = "\n".join(deadlock_buffer)
                thread_names = re.findall(r'"([^"]+)"', block_text)
                deadlocks.append({"threads": thread_names, "description": block_text})
                deadlock_buffer = []
                in_deadlock = False
            else:
                deadlock_buffer.append(line)
            i += 1
            continue

        # Try thread header
        m = _THREAD_HEADER.match(line)
        if m and line.startswith('"'):
            thread_name = m.group("name")
            priority = int(m.group("prio") or 5)
            state = "UNKNOWN"
            stack_frames: List[str] = []
            waiting_on: Optional[str] = None
            locked: List[str] = []

            i += 1
            while i < len(lines):
                tline = lines[i]
                if tline.strip() == "":
                    break
                sm = _STATE_LINE.search(tline)
                if sm:
                    state = sm.group(1).split("_")[0] if "_" not in sm.group(1) else sm.group(1)
                    # Normalize to standard states
                    state = sm.group(1)
                fm = _FRAME_LINE.match(tline)
                if fm:
                    stack_frames.append(fm.group(1))
                wm = _WAITING_ON.search(tline)
                if wm:
                    waiting_on = wm.group(1)
                lm = _LOCKED.search(tline)
                if lm:
                    locked.append(lm.group(1))
                i += 1

            threads.append({
                "name": thread_name,
                "state": state,
                "priority": priority,
                "stack_trace": stack_frames,
                "waiting_on": waiting_on,
                "locked": locked,
            })
        else:
            i += 1

    # State counts
    state_counts: Dict[str, int] = Counter(
        t["state"] for t in threads if t["state"] != "UNKNOWN"
    )
    normalized_states = {
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

    # Hotspots: most frequent stack frames
    frame_counter: Counter = Counter()
    for t in threads:
        for frame in t["stack_trace"]:
            frame_counter[frame] += 1
    hotspots = [{"frame": frame, "count": cnt} for frame, cnt in frame_counter.most_common(20)]

    # Stack groups: group threads by similar stack
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

    return {
        "summary": {
            "total_threads": len(threads),
            "states": normalized_states,
            "deadlocks_found": len(deadlocks) > 0,
        },
        "deadlocks": deadlocks,
        "threads": threads,
        "hotspots": hotspots,
        "stack_groups": stack_groups,
    }
