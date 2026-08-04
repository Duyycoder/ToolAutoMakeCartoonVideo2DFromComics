"""CLI dọn dẹp file sinh ra cũ + đồng bộ lại CSDL SQLite.

Cách dùng (chạy từ thư mục gốc dự án):
  python -m orchestrator.cleanup --rebuild-db          # dựng lại app.db từ các story.json
  python -m orchestrator.cleanup --tasks --dry-run     # xem trước file tạm sẽ xóa (không xóa)
  python -m orchestrator.cleanup --tasks               # xóa toàn bộ thư mục làm việc tạm trong tasks/
  python -m orchestrator.cleanup --tasks --days 7      # chỉ xóa file tạm cũ hơn 7 ngày
  python -m orchestrator.cleanup --stats               # in thống kê CSDL
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from orchestrator.config import load_global_config
from orchestrator.storage import StorageManager
from orchestrator import db


def main():
    ap = argparse.ArgumentParser(description="Dọn dẹp & đồng bộ dữ liệu")
    ap.add_argument("--tasks", action="store_true", help="Dọn thư mục làm việc tạm trong tasks/")
    ap.add_argument("--days", type=float, default=0,
                    help="Chỉ xóa file tạm cũ hơn N ngày (mặc định 0 = tất cả)")
    ap.add_argument("--dry-run", action="store_true", help="Xem trước, không xóa thật")
    ap.add_argument("--rebuild-db", action="store_true", help="Dựng lại app.db từ các story.json")
    ap.add_argument("--stats", action="store_true", help="In thống kê CSDL")
    args = ap.parse_args()

    cfg = load_global_config()
    sm = StorageManager(base_storage_dir=(cfg.get("storage_dir") or "storage"))
    print(f"[storage] {sm.base_dir}")
    print(f"[db]      {sm.db_path}")

    if args.rebuild_db:
        n = sm.rebuild_db()
        print(f"[rebuild-db] Đã đồng bộ {n} truyện vào SQLite.")

    if args.tasks:
        res = sm.cleanup_tasks(keep_days=args.days, dry_run=args.dry_run)
        verb = "Sẽ xóa" if args.dry_run else "Đã xóa"
        print(f"[cleanup-tasks] {verb} {res['count']} thư mục tạm, giải phóng ~{res['freed_mb']} MB.")
        for name in res["removed"][:20]:
            print("   -", name)

    if args.stats or not (args.tasks or args.rebuild_db):
        print("[stats]", db.stats(sm.db_path))


if __name__ == "__main__":
    main()
