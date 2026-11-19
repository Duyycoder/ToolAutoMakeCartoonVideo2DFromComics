"""Gộp clip (gop_clip.py): timeline con chỉ gồm clip được chọn, dời về 0, giữ vùng che và chuyển cảnh nội bộ."""
import pytest

from orchestrator.editor import gop_clip


def _tl():
    return {"tracks": [{"id": "V2", "loai": "video"}, {"id": "V1", "loai": "video"}, {"id": "O1", "loai": "lop_phu"},
                       {"id": "S1", "loai": "phu_de"}, {"id": "A1", "loai": "audio"}],
            "vung_vao": 1, "danh_dau": [{"id": "dd_1", "t": 3}],
            "chuyen_canh": [{"id": "x1", "truoc": "a", "sau": "b"}, {"id": "x2", "truoc": "b", "sau": "c"}],
            "clips": [
                {"id": "a", "track": "V1", "media": "m1", "bat_dau": 10, "vao": 0, "ra": 4, "toc_do": 1},
                {"id": "b", "track": "V1", "media": "m2", "bat_dau": 14, "vao": 0, "ra": 6, "toc_do": 2},
                {"id": "c", "track": "V1", "media": "m3", "bat_dau": 17, "vao": 0, "ra": 2, "toc_do": 1},
                {"id": "p", "track": "V2", "media": "m4", "bat_dau": 12, "vao": 1, "ra": 3, "toc_do": 1},
                {"id": "che", "track": "O1", "loai": "che_phu_de", "tu_media": "m1", "t_vao": 0, "t_ra": 4},
                {"id": "chu", "track": "O1", "loai": "chu", "bat_dau": 11, "ket_thuc": 13, "noi_dung": "x"},
                {"id": "pd", "track": "S1", "loai": "phu_de", "tu_media": "m1", "t_vao": 1, "t_ra": 2, "text": "y"},
                {"id": "nhac", "track": "A1", "media": "m9", "bat_dau": 0, "vao": 0, "ra": 60, "toc_do": 1}]}


def test_timeline_con():
    tl = _tl()
    con, t0, co_hinh = gop_clip.tl_con(tl, ["b", "a", "p", "chu", "khong_co"])
    assert (t0, co_hinh) == (10, True)
    assert [(c["id"], c.get("bat_dau")) for c in con["clips"]] == [("a", 0), ("b", 4), ("p", 2), ("che", None)]
    assert [cc["id"] for cc in con["chuyen_canh"]] == ["x1"]            # chuyển cảnh b→c bị bỏ vì c không được chọn
    assert "vung_vao" not in con and "danh_dau" not in con
    assert gop_clip.thoi_luong(con) == 7                                 # b: 4 + 6/2
    assert tl["clips"][0]["bat_dau"] == 10                               # không sửa timeline gốc


def test_chi_am_thanh_va_khong_chon_gi():
    con, t0, co_hinh = gop_clip.tl_con(_tl(), ["nhac"])
    assert (t0, co_hinh, len(con["clips"])) == (0, False, 2)             # clip nhạc + vùng che (vô hại khi không có video)
    with pytest.raises(ValueError):
        gop_clip.tl_con(_tl(), ["chu", "pd"])
