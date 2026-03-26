import os

import httpx

ANALYZER_URL = os.environ.get("ANALYZER_URL", "http://analyzer:5000")


def run_analysis(file_path: str, analysis_type: str) -> dict:
    response = httpx.post(
        f"{ANALYZER_URL}/analyze",
        json={"type": analysis_type, "file": file_path},
        timeout=600,
    )
    response.raise_for_status()
    return response.json()
