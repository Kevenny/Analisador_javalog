import json
import subprocess


def run_analysis(file_path: str, analysis_type: str) -> dict:
    """
    Invokes the analyzer container's run_analysis.py script.
    The analyzer service mounts /tmp/analyzer as /tmp, so files placed there
    are accessible to the analyzer container.
    """
    result = subprocess.run(
        ["python3", "/analyzer/run_analysis.py", "--type", analysis_type, "--file", file_path],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Analyzer failed: {result.stderr}")
    return json.loads(result.stdout)
