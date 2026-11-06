"""Chạy spike TripoSR theo ma trận chunk_size x mc_resolution, ghi report markdown.

  .venv-ai\\Scripts\\python.exe workers\\spike_triposr_matrix.py [--image a.png] [--quick]

Report: plans/reports/spike-triposr-vram-<yymmdd-hhmm>.md — dùng để chốt cấu hình
mặc định trong configs/config.example.json (Phase 01, bước 5).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SINGLE = ROOT / "workers" / "worker_image_to_3d.py"
OUT_ROOT = ROOT / "output" / "spike"
CHUNKS = (8192, 4096, 2048)
RESOLUTIONS = (256, 192, 128)
VRAM_BUDGET_MB = 5200  # chừa ~0.8 GB cho Windows/WebView trên card 6 GB


def run_one(extra_args: list[str]) -> dict:
    proc = subprocess.run([sys.executable, str(SINGLE), *extra_args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = None
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(f"    {msg.get('msg') or msg.get('type')}", flush=True)
        last = msg
    if last is None:  # crash native: không kịp in JSON
        return {"type": "error", "code": f"EXIT_{proc.returncode}", "msg": proc.stderr[-300:]}
    return last


def to_row(chunk: int, res: int, result: dict) -> str:
    if result.get("type") != "done":
        return f"| {chunk} | {res} | - | - | - | FAIL `{result.get('code')}` |"
    s = result["stats"]
    vram = s["peak_vram_mb"]
    verdict = "PASS" if vram is None or vram <= VRAM_BUDGET_MB else "OVER"
    return f"| {chunk} | {res} | {vram if vram is not None else 'cpu'} | {s['seconds']} | {s['tris']} | {verdict} |"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--image", default=None)
    p.add_argument("--quick", action="store_true", help="chỉ chạy 1 cấu hình (4096, 192)")
    args = p.parse_args()
    base = ["--image", args.image] if args.image else []
    combos = [(4096, 192)] if args.quick else [(c, r) for c in CHUNKS for r in RESOLUTIONS]

    rows, meta = [], {}
    for chunk, res in combos:
        print(f"[spike] chunk_size={chunk} mc_resolution={res}", flush=True)
        result = run_one(base + ["--chunk-size", str(chunk), "--mc-resolution", str(res),
                                 "--out-dir", str(OUT_ROOT / f"c{chunk}_r{res}")])
        if result.get("type") == "done":
            meta = {"device": result["stats"]["device"], "mc_backend": result["stats"]["mc_backend"]}
        rows.append(to_row(chunk, res, result))

    stamp = time.strftime("%y%m%d-%H%M")
    report = ROOT / "plans" / "reports" / f"spike-triposr-vram-{stamp}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join([
        f"# Spike TripoSR VRAM — {stamp}",
        "",
        f"- Device: `{meta.get('device', '?')}` · Marching cubes: `{meta.get('mc_backend', '?')}`",
        f"- Ngân sách VRAM: {VRAM_BUDGET_MB} MB (peak `torch.cuda.max_memory_allocated`, chưa gồm CUDA context ~300-500 MB)",
        "",
        "| chunk_size | mc_resolution | peak VRAM (MB) | thời gian (s) | tam giác | kết quả |",
        "|-----------|---------------|----------------|---------------|----------|---------|",
        *rows,
        "",
    ]), encoding="utf-8")
    print(f"[spike] Report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
