"""Giao thức stdout dùng chung cho mọi worker AI (backend/job_runner.py đọc từng dòng JSON):
  {"type":"progress","pct":42,"msg":"..."} · {"type":"done","stats":{...}} · {"type":"error","code":"CUDA_OOM","msg":"..."}
"""
import json
import sys


def emit(**payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def run_worker(run, args) -> int:
    """Chạy `run(args)` -> dict thống kê; mọi lỗi được báo theo giao thức để runner phân loại/thử lại."""
    sys.stdout.reconfigure(encoding="utf-8")  # JSON có tiếng Việt
    try:
        emit(type="done", stats=run(args))
        return 0
    except Exception as exc:
        code = "CUDA_OOM" if "out of memory" in str(exc).lower() else type(exc).__name__
        emit(type="error", code=code, msg=str(exc)[:500])
        return 1
