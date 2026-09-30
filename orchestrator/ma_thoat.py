def mo_ta_ma_thoat(code: int) -> str | None:
    if code in (3221225477, -1073741819):
        return "0xC0000005 — tiến trình bị crash trong thư viện native (thường là driver GPU NVIDIA). Hãy bấm chạy lại; nếu lặp lại, cập nhật driver NVIDIA hoặc chọn thiết bị CPU."
    elif code in (3221226505, -1073740791):
        return "0xC0000409 — thư viện native tự huỷ (stack buffer overrun)."
    elif code in (3221225725, -1073741571):
        return "0xC00000FD — tràn ngăn xếp."
    elif code in (3221226525, -1073740771):
        return "0xC000041D — lỗi trong callback native."
    return None

NATIVE_CRASH_CODES = {
    3221225477, -1073741819,
    3221226525, -1073740771,
    3221226505, -1073740791,
    3221225725, -1073741571
}
