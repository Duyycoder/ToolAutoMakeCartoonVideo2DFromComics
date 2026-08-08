"""Đổi tên các tệp chương về đúng quy tắc mà pipeline nhận diện.

Bước lồng tiếng và ghép video chỉ lấy tệp có " - [VI] " trong tên, nên chương
đặt tên kiểu khác (chuong_0001.md, 12.md, Chapter 12 - Title.txt, ...) sẽ bị bỏ
qua lặng lẽ. Script này đổi tên tại chỗ theo đúng quy tắc dùng chung ở
`orchestrator/chapter_naming.py`.

Tệp đã đúng quy tắc được giữ nguyên, nên chạy lại nhiều lần cũng không sao.

Dùng:
    python scripts/fix_ten_chuong.py storage/truyen/<slug>/raw --dry-run
    python scripts/fix_ten_chuong.py storage/truyen/<slug>/raw
    python scripts/fix_ten_chuong.py storage/truyen/<slug>/raw --chua-dich
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import chapter_naming  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir",
                    help="Thư mục chứa tệp chương (thường là storage/truyen/<slug>/raw)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Chỉ in ra dự định, không đổi tên")
    ap.add_argument("--chua-dich", action="store_true",
                    help="Nội dung là tiếng nước ngoài, còn phải qua bước dịch: "
                         "đặt tên KHÔNG kèm nhãn [VI] để bước dịch tự gắn")
    args = ap.parse_args()

    if not os.path.isdir(args.raw_dir):
        print(f"[LOI] Khong tim thay thu muc: {args.raw_dir}")
        sys.exit(1)

    n = chapter_naming.normalize_dir(
        args.raw_dir,
        translated=not args.chua_dich,
        log=print,
        dry_run=args.dry_run,
    )
    if n == 0:
        print("Khong co tep nao can doi ten.")
    else:
        print(f"{'Se doi ten' if args.dry_run else 'Da doi ten'} {n} tep.")


if __name__ == "__main__":
    main()
