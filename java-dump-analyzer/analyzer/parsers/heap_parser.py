"""
Parser for Java Heap Dumps (.hprof).
Tries Eclipse MAT headless first; falls back to basic hprof parsing.
"""

import glob
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


MAT_PATHS = [
    "/opt/mat/MemoryAnalyzer",
    "/opt/MemoryAnalyzer",
]


def _find_mat() -> Optional[str]:
    for path in MAT_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    # Also try glob for any MemoryAnalyzer binary under /opt
    for match in glob.glob("/opt/**/MemoryAnalyzer", recursive=True):
        if os.access(match, os.X_OK):
            return match
    return None


def _run_mat(hprof_path: str, mat_bin: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as work_dir:
        cmd = [
            mat_bin,
            "-consolelog",
            "-application", "org.eclipse.mat.api.parse",
            hprof_path,
            "org.eclipse.mat.api.leak",
            "org.eclipse.mat.api.top_consumers",
            "-vmargs", "-Xmx4g",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=work_dir)

        # Look for generated HTML reports next to the hprof
        base = Path(hprof_path).stem
        report_dir = Path(hprof_path).parent / f"{base}_Leak_Suspects"
        return _parse_mat_html(report_dir, hprof_path)


def _parse_mat_html(report_dir: Path, hprof_path: str) -> Dict[str, Any]:
    leak_suspects: List[Dict[str, Any]] = []
    top_consumers: List[Dict[str, Any]] = []
    dominator_tree: List[Dict[str, Any]] = []

    if report_dir.exists():
        try:
            from bs4 import BeautifulSoup
            for html_file in report_dir.glob("*.html"):
                content = html_file.read_text(errors="replace")
                soup = BeautifulSoup(content, "lxml")
                for table in soup.find_all("table"):
                    rows = table.find_all("tr")
                    for row in rows[1:]:
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if len(cols) >= 3:
                            try:
                                retained = int(re.sub(r"[^\d]", "", cols[1]) or "0")
                                pct = float(re.sub(r"[^\d.]", "", cols[2]) or "0")
                                leak_suspects.append({
                                    "description": cols[0],
                                    "retained_bytes": retained,
                                    "percentage": pct,
                                })
                            except ValueError:
                                pass
        except Exception:
            pass

    heap_size = os.path.getsize(hprof_path)
    return {
        "summary": {
            "heap_size_bytes": heap_size,
            "total_objects": 0,
            "analysis_date": datetime.utcnow().isoformat(),
        },
        "leak_suspects": leak_suspects[:10],
        "top_consumers": top_consumers[:10],
        "dominator_tree": dominator_tree[:10],
    }


def _basic_hprof_parse(hprof_path: str) -> Dict[str, Any]:
    """
    Minimal fallback: read HPROF header and report file size.
    """
    heap_size = os.path.getsize(hprof_path)
    total_objects = 0

    try:
        with open(hprof_path, "rb") as f:
            header = f.read(32)
            # HPROF files start with "JAVA PROFILE"
            if not header.startswith(b"JAVA PROFILE"):
                return {
                    "summary": {
                        "heap_size_bytes": heap_size,
                        "total_objects": 0,
                        "analysis_date": datetime.utcnow().isoformat(),
                        "note": "File does not appear to be a valid HPROF file",
                    },
                    "leak_suspects": [],
                    "top_consumers": [],
                    "dominator_tree": [],
                }
    except Exception:
        pass

    return {
        "summary": {
            "heap_size_bytes": heap_size,
            "total_objects": total_objects,
            "analysis_date": datetime.utcnow().isoformat(),
            "note": "Basic analysis (Eclipse MAT not available). Upload a smaller heap dump or install MAT for full analysis.",
        },
        "leak_suspects": [],
        "top_consumers": [
            {
                "class_name": "Unknown (MAT required for full analysis)",
                "instances": 0,
                "retained_bytes": heap_size,
                "percentage": 100.0,
            }
        ],
        "dominator_tree": [],
    }


def parse_heap_dump(hprof_path: str) -> Dict[str, Any]:
    mat_bin = _find_mat()
    if mat_bin:
        try:
            return _run_mat(hprof_path, mat_bin)
        except Exception as e:
            # Fall through to basic parse
            pass
    return _basic_hprof_parse(hprof_path)
