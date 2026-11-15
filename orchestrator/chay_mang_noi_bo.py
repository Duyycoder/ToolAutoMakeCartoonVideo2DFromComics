"""Chạy editor trên laptop/PC (GPU NVIDIA, đủ AI) và mở từ điện thoại cùng mạng Wi-Fi.

Khác run.bat (cửa sổ app chỉ dùng trên chính máy đó): server nghe trên mọi card mạng, cổng 8200,
có mật khẩu (HTTP Basic, cùng cơ chế với bản server công khai). Xuất video dùng NVENC, proxy dùng
NVDEC/NVENC, các tính năng AI chạy trên GPU của máy.

Mật khẩu sinh ngẫu nhiên lần đầu, lưu ở configs/mat_khau_mang_noi_bo.txt (không commit) — xoá file để đổi.
Chạy: run-lan.bat   (hoặc: python -m orchestrator.chay_mang_noi_bo)
"""
import os
import secrets
import socket
import sys

GOC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONG = int(os.environ.get("EDITOR_LAN_PORT", "8200"))
USER = "game"
FILE_MAT_KHAU = os.path.join(GOC, "configs", "mat_khau_mang_noi_bo.txt")


def mat_khau() -> str:
    try:
        with open(FILE_MAT_KHAU, encoding="utf-8") as f:
            mk = f.read().strip()
        if mk:
            return mk
    except OSError:
        pass
    mk = secrets.token_urlsafe(9)
    os.makedirs(os.path.dirname(FILE_MAT_KHAU), exist_ok=True)
    with open(FILE_MAT_KHAU, "w", encoding="utf-8") as f:
        f.write(mk)
    return mk


def dia_chi_lan() -> list:
    """IP của máy trong mạng nội bộ (bỏ loopback). Không gửi gói tin nào ra ngoài."""
    ds = set()
    try:
        for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ds.add(x[4][0])
    except OSError:
        pass
    try:
        # UDP connect chỉ chọn card mạng đi ra, không gửi dữ liệu.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ds.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in ds if not ip.startswith(("127.", "169.254.")))


def main() -> int:
    mk = mat_khau()
    os.environ["EDITOR_PUBLIC_USER"] = USER
    os.environ["EDITOR_PUBLIC_PASSWORD"] = mk
    os.environ.setdefault("EDITOR_ENABLE_AI", "1")
    os.chdir(GOC)
    print("=" * 62)
    print(" Editor dang chay tren may nay - mo tu dien thoai CUNG Wi-Fi:")
    for ip in dia_chi_lan() or ["<IP may tinh>"]:
        print(f"     http://{ip}:{CONG}/")
    print(f"     Tai khoan: {USER}   Mat khau: {mk}")
    print(" Lan dau Windows hoi tuong lua: chon cho phep mang Rieng tu (Private).")
    print(" Dong cua so nay de tat.")
    print("=" * 62, flush=True)
    import uvicorn
    uvicorn.run("orchestrator.main:app", host="0.0.0.0", port=CONG, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
