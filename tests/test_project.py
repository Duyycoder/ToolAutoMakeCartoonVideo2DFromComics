"""Du an = mot thu muc co .duan.json.

Doi ten file la thao tac KHONG hoan tac duoc bang Ctrl+Z, lai lam tren du lieu
that cua nguoi dung, nen phan danh so va phan hoan tac duoc kiem ky nhat.
"""
import json
import os

import pytest
from fastapi import HTTPException

import orchestrator.main as main
from orchestrator import project


def tao_file(folder, *ten_files):
    """Moi file mang noi dung rieng de biet sau khi doi ten co lan khong."""
    for name in ten_files:
        with open(os.path.join(str(folder), name), "wb") as fh:
            fh.write(name.encode("utf-8"))


def ten_tren_dia(folder):
    return sorted(n for n in os.listdir(str(folder)) if not n.startswith("."))


def noi_dung(folder, name):
    with open(os.path.join(str(folder), name), "rb") as fh:
        return fh.read().decode("utf-8")


# ----------------------------------------------------------------- Danh so
def test_tap2_dung_truoc_tap10():
    # Sap theo chu thi "tap 10" chen len truoc "tap 2" -> ghep ra video lon tap.
    ke_hoach = project.ke_hoach_doi_ten(["tap 1.mp4", "tap 10.mp4", "tap 2.mp4"])
    assert [item["moi"] for item in ke_hoach] == [
        "001_tap_1.mp4", "002_tap_2.mp4", "003_tap_10.mp4"]


def test_khong_danh_so_chong_len_so_cu():
    # Init lan hai khong duoc bien "001_tap_1.mp4" thanh "001_001_tap_1.mp4".
    ke_hoach = project.ke_hoach_doi_ten(["001_tap_1.mp4", "002_tap_2.mp4"])
    assert [item["moi"] for item in ke_hoach] == ["001_tap_1.mp4", "002_tap_2.mp4"]
    assert all(item["doi"] is False for item in ke_hoach)


def test_giu_nguyen_duoi_file_khong_ep_ve_mp4():
    ke_hoach = project.ke_hoach_doi_ten(["phim.MKV"])
    assert ke_hoach[0]["moi"] == "001_phim.mkv"


# -------------------------------------------------------------- Xem xet
def test_thu_muc_khong_co_video(tmp_path):
    tao_file(tmp_path, "anh.jpg", "ghi_chu.txt")
    xem = project.xem_xet(str(tmp_path))

    assert xem["co_video"] is False
    assert xem["so_video"] == 0
    assert xem["da_init"] is False


def test_xem_xet_khong_dung_gi_toi_file(tmp_path):
    tao_file(tmp_path, "tap 2.mp4", "tap 1.mp4")
    truoc = ten_tren_dia(tmp_path)

    xem = project.xem_xet(str(tmp_path))

    # Chi xem truoc, chua duoc doi ten hay tao .duan.json.
    assert ten_tren_dia(tmp_path) == truoc
    assert not project.da_init(str(tmp_path))
    assert xem["so_phai_doi"] == 2


def test_xem_xet_thu_muc_khong_ton_tai():
    with pytest.raises(ValueError):
        project.xem_xet("Z:/khong/co/thu/muc")


# ------------------------------------------------------------------ Init
def test_init_doi_ten_that_va_tao_marker(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 10.mp4", "tap 2.mp4")

    data = project.init(str(tmp_path), name="Phim ABC")

    assert ten_tren_dia(tmp_path) == ["001_tap_1.mp4", "002_tap_2.mp4", "003_tap_10.mp4",
                                      "ban_ghep", "da_sub", "phu_de"]
    assert project.da_init(str(tmp_path))
    assert data["name"] == "Phim ABC"
    # Noi dung phai di theo dung file, khong bi trao nham.
    assert noi_dung(tmp_path, "002_tap_2.mp4") == "tap 2.mp4"


def test_init_giu_ten_goc_de_con_duong_lui(tmp_path):
    tao_file(tmp_path, "tap 2.mp4")
    data = project.init(str(tmp_path))
    assert data["videos"][0]["ten_goc"] == "tap 2.mp4"
    assert data["videos"][0]["file"] == "001_tap_2.mp4"


def test_init_khong_doi_ten_khi_nguoi_dung_doi_y(tmp_path):
    tao_file(tmp_path, "tap 2.mp4")
    project.init(str(tmp_path), doi_ten=False)

    assert "tap 2.mp4" in ten_tren_dia(tmp_path)
    assert project.da_init(str(tmp_path))


def test_init_thu_muc_khong_co_video_thi_bao_loi(tmp_path):
    tao_file(tmp_path, "doc.pdf")
    with pytest.raises(ValueError):
        project.init(str(tmp_path))
    # Khong duoc de lai marker khi da bao loi.
    assert not project.da_init(str(tmp_path))


def test_doi_ten_hoan_vi_khong_lam_mat_file(tmp_path):
    # "tap_2.mp4" se lay dung cai ten ma "002_tap_2.mp4" dang giu -> doi thang
    # mot pha la de mat file. Doi hai pha phai giu du ca hai.
    tao_file(tmp_path, "002_tap_2.mp4", "tap_2.mp4")

    project.init(str(tmp_path))

    assert ten_tren_dia(tmp_path) == ["001_tap_2.mp4", "002_tap_2.mp4",
                                      "ban_ghep", "da_sub", "phu_de"]
    assert noi_dung(tmp_path, "001_tap_2.mp4") == "002_tap_2.mp4"
    assert noi_dung(tmp_path, "002_tap_2.mp4") == "tap_2.mp4"


def test_mo_lai_du_an_cu_khong_hoi_doi_ten_lan_nua(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 2.mp4")
    project.init(str(tmp_path), name="Phim ABC")

    xem = project.xem_xet(str(tmp_path))

    assert xem["da_init"] is True
    assert xem["ten"] == "Phim ABC"
    assert xem["so_phai_doi"] == 0


def test_init_lan_hai_giu_nguyen_ngay_tao(tmp_path):
    tao_file(tmp_path, "tap 1.mp4")
    dau = project.init(str(tmp_path), name="Ban dau")

    lai = project.init(str(tmp_path))

    assert lai["created_at"] == dau["created_at"]
    assert lai["name"] == "Ban dau"      # khong truyen ten moi thi giu ten cu


# -------------------------------------------------------------- Hoan tac
def test_hoan_tac_tra_ten_ve_y_nhu_cu(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 10.mp4", "tap 2.mp4")
    truoc = ten_tren_dia(tmp_path)
    project.init(str(tmp_path))

    ket_qua = project.hoan_tac(str(tmp_path))

    # Tra thu muc ve DUNG nhu truoc khi init, khong bo lai thu muc rong nao.
    assert ten_tren_dia(tmp_path) == truoc
    assert not project.da_init(str(tmp_path))
    assert ket_qua["so_da_tra_lai"] == 3
    assert noi_dung(tmp_path, "tap 2.mp4") == "tap 2.mp4"


def test_hoan_tac_khong_xoa_thu_muc_dang_co_du_lieu(tmp_path):
    tao_file(tmp_path, "tap 1.mp4")
    project.init(str(tmp_path))
    # Phu de nguoi dung da tao ra thi khong duoc don theo.
    with open(os.path.join(str(tmp_path), "phu_de", "001_tap_1.vi.srt"), "w") as fh:
        fh.write("1\n")

    project.hoan_tac(str(tmp_path))

    assert os.path.isdir(os.path.join(str(tmp_path), "phu_de"))
    assert not os.path.exists(os.path.join(str(tmp_path), "ban_ghep"))


def test_hoan_tac_thu_muc_chua_phai_du_an(tmp_path):
    with pytest.raises(ValueError):
        project.hoan_tac(str(tmp_path))


def test_hoan_tac_bo_qua_file_da_bi_xoa(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 2.mp4")
    project.init(str(tmp_path))
    os.remove(os.path.join(str(tmp_path), "002_tap_2.mp4"))

    ket_qua = project.hoan_tac(str(tmp_path))

    assert ket_qua["so_da_tra_lai"] == 1
    assert "tap 1.mp4" in ten_tren_dia(tmp_path)


# --------------------------------------------------------------- Tao moi
def test_tao_du_an_rong_de_tai_video_ve(tmp_path):
    data = project.tao_moi(str(tmp_path), "Phim Hay Lam")

    folder = os.path.join(str(tmp_path), "phim_hay_lam")
    assert os.path.isdir(folder) and project.da_init(folder)
    assert data["name"] == "Phim Hay Lam"
    assert data["videos"] == []
    for sub in ("phu_de", "da_sub", "ban_ghep"):
        assert os.path.isdir(os.path.join(folder, sub))


def test_tao_du_an_bat_buoc_dat_ten(tmp_path):
    with pytest.raises(ValueError):
        project.tao_moi(str(tmp_path), "   ")


def test_tao_du_an_trung_ten_thi_bao_loi(tmp_path):
    project.tao_moi(str(tmp_path), "Phim A")
    with pytest.raises(ValueError):
        project.tao_moi(str(tmp_path), "Phim A")


# ---------------------------------------------------- Danh sach & da ghep
def test_danh_sach_video_theo_dung_so_thu_tu(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 10.mp4", "tap 2.mp4")
    project.init(str(tmp_path))

    ds = project.danh_sach_video(str(tmp_path))

    assert [v["file"] for v in ds] == ["001_tap_1.mp4", "002_tap_2.mp4", "003_tap_10.mp4"]
    assert all(v["exists"] and v["size"] > 0 for v in ds)


def test_video_da_ghep_bien_khoi_danh_sach(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 2.mp4")
    project.init(str(tmp_path))

    project.danh_dau_da_ghep(str(tmp_path),
                             [os.path.join(str(tmp_path), "001_tap_1.mp4")],
                             "tong_hop.mp4")

    con_lai = project.danh_sach_video(str(tmp_path))
    assert [v["file"] for v in con_lai] == ["002_tap_2.mp4"]

    tat_ca = project.danh_sach_video(str(tmp_path), ke_ca_da_ghep=True)
    assert len(tat_ca) == 2
    assert tat_ca[0]["merged_into"] == "tong_hop.mp4"


def test_ghi_nhan_lan_ghep_vao_lich_su(tmp_path):
    tao_file(tmp_path, "tap 1.mp4", "tap 2.mp4")
    project.init(str(tmp_path))

    project.danh_dau_da_ghep(
        str(tmp_path),
        [os.path.join(str(tmp_path), "001_tap_1.mp4"),
         os.path.join(str(tmp_path), "002_tap_2.mp4")],
        "tong_hop.mp4")

    data = project.doc(str(tmp_path))
    assert len(data["merges"]) == 1
    assert data["merges"][0]["videos"] == ["001_tap_1.mp4", "002_tap_2.mp4"]


def test_danh_sach_video_thu_muc_thuong_tra_ve_rong(tmp_path):
    assert project.danh_sach_video(str(tmp_path)) == []


def test_marker_hong_thi_coi_nhu_chua_phai_du_an(tmp_path):
    tao_file(tmp_path, "tap 1.mp4")
    with open(project.duong_dan_marker(str(tmp_path)), "w", encoding="utf-8") as fh:
        fh.write("{ day khong phai json")

    assert project.doc(str(tmp_path)) is None
    assert project.danh_sach_video(str(tmp_path)) == []


# ------------------------------------------------------------- Endpoint
@pytest.fixture
def cfg_gia(monkeypatch):
    """Cau hinh trong bo nho.

    Endpoint du an co ghi vao global_config (danh sach du an gan day) — test ma
    dung ham that la ghi de len cau hinh THAT cua nguoi dung.
    """
    kho = {}
    monkeypatch.setattr(main, "load_global_config", lambda: json.loads(json.dumps(kho)))
    monkeypatch.setattr(main, "save_global_config", lambda cfg: kho.update(cfg))
    return kho


def test_endpoint_xem_xet_thu_muc_la_bao_400(cfg_gia):
    with pytest.raises(HTTPException) as e:
        main.project_inspect(main.ProjectFolderSchema(folder="Z:/khong/co"))
    assert e.value.status_code == 400


def test_endpoint_init_doi_ten_va_nho_vao_gan_day(tmp_path, cfg_gia):
    tao_file(tmp_path, "tap 2.mp4", "tap 1.mp4")

    data = main.project_init(main.ProjectInitSchema(folder=str(tmp_path), name="Phim A"))

    assert data["name"] == "Phim A"
    assert "001_tap_1.mp4" in ten_tren_dia(tmp_path)
    assert cfg_gia["du_an"]["hien_tai"] == os.path.abspath(str(tmp_path))
    assert cfg_gia["du_an"]["gan_day"][0]["name"] == "Phim A"


def test_endpoint_init_thu_muc_khong_co_video_bao_400(tmp_path, cfg_gia):
    tao_file(tmp_path, "doc.pdf")
    with pytest.raises(HTTPException) as e:
        main.project_init(main.ProjectInitSchema(folder=str(tmp_path)))
    assert e.value.status_code == 400


def test_endpoint_tao_du_an_moi(tmp_path, cfg_gia):
    data = main.project_create(main.ProjectCreateSchema(thu_muc_cha=str(tmp_path), ten="Phim B"))

    assert data["videos"] == []
    assert os.path.isdir(os.path.join(str(tmp_path), "phim_b"))

    with pytest.raises(HTTPException) as e:   # trung ten
        main.project_create(main.ProjectCreateSchema(thu_muc_cha=str(tmp_path), ten="Phim B"))
    assert e.value.status_code == 400


def test_endpoint_mo_thu_muc_chua_phai_du_an_bao_404(tmp_path, cfg_gia):
    with pytest.raises(HTTPException) as e:
        main.project_open(main.ProjectFolderSchema(folder=str(tmp_path)))
    assert e.value.status_code == 404


def test_endpoint_hoan_tac_va_quen_khoi_gan_day(tmp_path, cfg_gia):
    tao_file(tmp_path, "tap 1.mp4")
    main.project_init(main.ProjectInitSchema(folder=str(tmp_path)))

    res = main.project_undo_rename(main.ProjectFolderSchema(folder=str(tmp_path)))

    assert res["so_da_tra_lai"] == 1
    assert "tap 1.mp4" in ten_tren_dia(tmp_path)
    assert cfg_gia["du_an"]["gan_day"] == []
    assert cfg_gia["du_an"]["hien_tai"] == ""


def test_endpoint_danh_sach_video(tmp_path, cfg_gia):
    tao_file(tmp_path, "tap 1.mp4", "tap 2.mp4")
    main.project_init(main.ProjectInitSchema(folder=str(tmp_path)))

    ds = main.project_videos(folder=str(tmp_path))
    assert [v["file"] for v in ds] == ["001_tap_1.mp4", "002_tap_2.mp4"]

    with pytest.raises(HTTPException) as e:
        main.project_videos(folder=str(tmp_path / "khong_co"))
    assert e.value.status_code == 404


def test_endpoint_gan_day_bo_du_an_da_bien_mat(tmp_path, cfg_gia, monkeypatch):
    tao_file(tmp_path, "tap 1.mp4")
    main.project_init(main.ProjectInitSchema(folder=str(tmp_path)))
    assert len(main.project_recent()["gan_day"]) == 1

    # Nguoi dung xoa/di chuyen thu muc di cho khac.
    os.remove(project.duong_dan_marker(str(tmp_path)))

    res = main.project_recent()
    assert res["gan_day"] == []
    assert res["hien_tai"] == ""


def test_marker_khong_luu_truong_folder(tmp_path):
    # `folder` la thong tin suy ra luc doc, ghi xuong dia la sai khi chuyen o.
    tao_file(tmp_path, "tap 1.mp4")
    project.init(str(tmp_path))

    with open(project.duong_dan_marker(str(tmp_path)), encoding="utf-8") as fh:
        raw = json.load(fh)
    assert "folder" not in raw
    assert project.doc(str(tmp_path))["folder"] == os.path.abspath(str(tmp_path))
