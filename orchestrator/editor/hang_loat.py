import re
import os
import json
import uuid
import time
import threading
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrator.editor import luu_tru, workspace, hang_doi, media
from orchestrator.config import load_global_config

class VungOcrSchema(BaseModel):
    x: float
    y: float
    w: float
    h: float

class BuocSchema(BaseModel):
    phu_de: str | None = None
    vung_ocr: VungOcrSchema | None = None
    dich: Dict[str, Any] | None = None
    che_phu_de: bool = False
    long_tieng: Dict[str, Any] | None = None
    xuat: Dict[str, Any] | None = None

class HangLoatSchema(BaseModel):
    files: List[str] = []
    urls: List[str] = []
    thu_muc: str | None = None
    che_do: str
    ten: str
    thong_so: Dict[str, Any] | None = None
    buoc: BuocSchema


def ap_dung(loai: str, tl: Dict[str, Any], kq: Dict[str, Any], mid: str, tham_so: Dict[str, Any], cac_media: List[Dict[str, Any]]):
    def xoa_cau_cu(nhap, b_mid):
        tr = next((t for t in nhap["tracks"] if t["loai"] == "phu_de"), None)
        if not tr: return
        cu = [c["id"] for c in nhap["clips"] if c.get("track") == tr["id"] and c.get("tu_media") == b_mid]
        nhap["clips"] = [c for c in nhap["clips"] if c["id"] not in cu]
        
    def them_cau_moi(nhap, b_mid, cau_moi):
        tr = next((t for t in nhap["tracks"] if t["loai"] == "phu_de"), None)
        if not tr: return
        for c in cau_moi:
            cid = luu_tru.id_moi([x["id"] for x in nhap.get("clips", [])], "c")
            nhap["clips"].append({
                "id": cid, "track": tr["id"], "loai": "phu_de", "tu_media": b_mid,
                "t_vao": c.get("t_vao"), "t_ra": c.get("t_ra"), 
                "text": c.get("text"), "text_goc": c.get("text_goc", ""),
                "kieu": "k_mac_dinh"
            })

    if loai in ("phu-de", "ocr") or (loai == "dich" and kq.get("lech_so_cau")):
        xoa_cau_cu(tl, mid)
        cau_moi = []
        for x in kq.get("cau", []):
            cau_moi.append({
                "t_vao": x.get("t_vao"), "t_ra": x.get("t_ra"),
                "text": x.get("text"), "text_goc": "" if loai == "dich" else x.get("text")
            })
        them_cau_moi(tl, mid, cau_moi)
        
        if loai == "ocr" and tham_so.get("tao_che") is not False and kq.get("vung"):
            m = next((x for x in cac_media if x["id"] == mid), {})
            trO = next((t for t in tl["tracks"] if t["loai"] == "lop_phu"), None)
            if trO:
                cid = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
                cau = kq.get("cau", [])
                t_ra_cuoi = cau[-1]["t_ra"] if cau else 0
                dai = float(m.get("thoi_luong") or 0) or t_ra_cuoi
                tl["clips"].append({
                    "id": cid, "track": trO["id"], "loai": "che_phu_de",
                    "tu_media": mid, "t_vao": 0, "t_ra": dai,
                    "vung": kq["vung"], "kieu": "blur", "do_manh": 20, "mau": "#000000"
                })
                
    elif loai == "dich":
        theo_id = {id: cau for id, cau in zip(kq.get("ids", []), kq.get("cau", []))}
        for c in tl["clips"]:
            if c["id"] in theo_id:
                x = theo_id[c["id"]]
                if not c.get("text_goc"):
                    c["text_goc"] = c.get("text", "")
                c["text"] = x.get("text", "")
                
    elif loai == "long-tieng":
        midGiong = kq.get("media_moi")
        tr = next((t for t in tl["tracks"] if t.get("vai") == "long_tieng"), None)
        if not tr:
            tr = {"id": "A2", "loai": "audio", "ten": "A2", "vai": "long_tieng", "an": False, "khoa": False, "tat_tieng": False}
            tl["tracks"].append(tr)
            
        tl["clips"] = [c for c in tl["clips"] if not (c.get("track") == tr["id"] and c.get("long_tieng_cho") == mid)]
        
        giong = next((x for x in cac_media if x["id"] == midGiong), {})
        dai = float(giong.get("thoi_luong") or 0) or float('inf')
        nguon = [c for c in tl["clips"] if c.get("media") == mid and next((t for t in tl["tracks"] if t["id"] == c["track"] and t["loai"] == "video"), None)]
        
        for c in nguon:
            if float(c.get("vao", 0)) >= dai:
                continue
            cid = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
            tl["clips"].append({
                "id": cid, "track": tr["id"], "media": midGiong, "long_tieng_cho": mid,
                "bat_dau": c.get("bat_dau"), "vao": c.get("vao"), 
                "ra": min(float(c.get("ra", 0)), dai),
                "toc_do": c.get("toc_do", 1), "am_luong": 1
            })

    elif loai == "tach-giong":
        midGiong = kq.get("media_giong")
        midNhac = kq.get("media_nhac")
        
        trGiong = next((t for t in tl["tracks"] if t.get("vai") == "giong"), None)
        if not trGiong:
            trGiong = {"id": _id_track_moi(tl, "A"), "loai": "audio", "ten": "Giọng (Demucs)", "vai": "giong", "an": False, "khoa": False, "tat_tieng": False}
            tl["tracks"].append(trGiong)
            
        trNhac = None
        if midNhac:
            trNhac = next((t for t in tl["tracks"] if t.get("vai") == "nhac"), None)
            if not trNhac:
                trNhac = {"id": _id_track_moi(tl, "A"), "loai": "audio", "ten": "Nhạc (Demucs)", "vai": "nhac", "an": False, "khoa": False, "tat_tieng": False}
                tl["tracks"].append(trNhac)
        
        # Xoá clip tách giọng cũ cho media này
        tl["clips"] = [c for c in tl["clips"] if not (c.get("tach_giong_cho") == mid)]
        
        giong = next((x for x in cac_media if x["id"] == midGiong), {})
        daiG = float(giong.get("thoi_luong") or 0) or float('inf')
        
        nhac = next((x for x in cac_media if x["id"] == midNhac), {}) if midNhac else {}
        daiN = float(nhac.get("thoi_luong") or 0) or float('inf')

        nguon = [c for c in tl["clips"] if c.get("media") == mid and next((t for t in tl["tracks"] if t["id"] == c["track"] and t["loai"] == "video"), None)]
        
        for c in nguon:
            c["tat_am"] = True
            
            if float(c.get("vao", 0)) < daiG:
                cidG = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
                tl["clips"].append({
                    "id": cidG, "track": trGiong["id"], "media": midGiong, "tach_giong_cho": mid,
                    "bat_dau": c.get("bat_dau"), "vao": c.get("vao"), 
                    "ra": min(float(c.get("ra", 0)), daiG),
                    "toc_do": c.get("toc_do", 1), "am_luong": 1
                })
            
            if midNhac and float(c.get("vao", 0)) < daiN:
                cidN = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
                tl["clips"].append({
                    "id": cidN, "track": trNhac["id"], "media": midNhac, "tach_giong_cho": mid,
                    "bat_dau": c.get("bat_dau"), "vao": c.get("vao"), 
                    "ra": min(float(c.get("ra", 0)), daiN),
                    "toc_do": c.get("toc_do", 1), "am_luong": 1
                })

    elif loai == "lam-net":
        midMoi = kq.get("media_moi")
        for c in tl.get("clips", []):
            if c.get("media") == mid:
                c["media"] = midMoi

    elif loai == "minh-hoa":
        if tham_so.get("minh_hoa_hanh_dong") != "kho":
            v_id = _id_track_moi(tl, "V")
            tr = {"id": v_id, "loai": "video", "ten": v_id, "an": False, "khoa": False, "tat_tieng": False}
            # Put after the first video track
            ds = tl.get("tracks", [])
            vi_tri = next((i for i, t in enumerate(ds) if t.get("loai") == "video"), -1)
            if vi_tri >= 0:
                ds.insert(vi_tri, tr)
            else:
                ds.insert(0, tr)
                
            doan = kq.get("doan", [])
            clips_nguon = [c for c in tl.get("clips", []) if c.get("media") == mid]
            
            for d in doan:
                found = False
                t_vao, t_ra = float(d.get("t_vao", 0)), float(d.get("t_ra", 0))
                for c in clips_nguon:
                    vao, ra = float(c.get("vao", 0)), float(c.get("ra", 0))
                    toc_do = float(c.get("toc_do", 1))
                    if t_vao >= vao and t_vao < ra:
                        offset = (t_vao - vao) / toc_do
                        bat_dau = float(c.get("bat_dau", 0)) + offset
                        thoi_gian_ra_clip = (ra - vao) / toc_do
                        thoi_gian_ra_video = (t_ra - t_vao) / toc_do
                        bd_clip = float(c.get("bat_dau", 0))
                        ra_moi = thoi_gian_ra_clip - (bat_dau - bd_clip) if bat_dau + thoi_gian_ra_video > bd_clip + thoi_gian_ra_clip else thoi_gian_ra_video
                        
                        media_len = float(next((m.get("thoi_luong") for m in cac_media if m["id"] == d["media"]), ra_moi) or ra_moi)
                        
                        cid = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
                        tl["clips"].append({
                            "id": cid, "track": v_id, "media": d["media"],
                            "bat_dau": bat_dau, "vao": 0.0, "ra": min(ra_moi, media_len),
                            "am_luong": 0
                        })
                        found = True
                        break
                        
                if not found and clips_nguon:
                    c = clips_nguon[0]
                    vao = float(c.get("vao", 0))
                    toc_do = float(c.get("toc_do", 1))
                    offset = (t_vao - vao) / toc_do
                    
                    cid = luu_tru.id_moi([x["id"] for x in tl.get("clips", [])], "c")
                    tl["clips"].append({
                        "id": cid, "track": v_id, "media": d["media"],
                        "bat_dau": float(c.get("bat_dau", 0)) + offset, "vao": 0.0, "ra": (t_ra - t_vao) / toc_do,
                        "am_luong": 0
                    })

def _id_track_moi(tl: Dict[str, Any], tien_to: str) -> str:
    """Giống `idTrackMoi` bên store.js: A1, A2… → số lớn nhất + 1 (id track không có dấu `_` như id clip)."""
    so = [int(m.group(1)) for t in tl.get("tracks", []) if (m := re.match(rf"^{tien_to}(\d+)$", str(t.get("id", ""))))]
    return f"{tien_to}{(max(so) if so else 0) + 1}"


class QuanLyHangLoat:
    def __init__(self, r: APIRouter):
        self.r = r
        self.luong: Dict[str, threading.Thread] = {}
        self.huy_flag: set[str] = set()

    def path_dir(self, ws: str) -> str:
        d = os.path.join(ws, ".hang_loat")
        os.makedirs(d, exist_ok=True)
        return d

    def path_lo(self, ws: str, lid: str) -> str:
        return os.path.join(self.path_dir(ws), f"{lid}.json")
        
    def doc_lo(self, ws: str, lid: str) -> Dict[str, Any] | None:
        p = self.path_lo(ws, lid)
        for _ in range(3):
            if not os.path.exists(p):
                return None
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                import time
                time.sleep(0.1)
        return None

    def ghi_lo(self, ws: str, lid: str, data: Dict[str, Any]):
        luu_tru.ghi_nguyen_tu(self.path_lo(ws, lid), data)
        
    def kiem_tra_bi_ngat(self, ws: str):
        d = self.path_dir(ws)
        for f in os.listdir(d):
            if f.endswith(".json"):
                lid = f[:-5]
                data = self.doc_lo(ws, lid)
                song = lid in self.luong and self.luong[lid].is_alive()
                if not song and data and any(m.get("trang_thai") == "dang_chay" for m in data.get("muc", [])):
                    for m in data.get("muc", []):
                        if m.get("trang_thai") == "dang_chay":
                            m["trang_thai"] = "bi_ngat"
                            m["loi"] = "Bị ngắt do tắt app"
                    self.ghi_lo(ws, lid, data)
                    
    def chay_lo(self, ws: str, lid: str):
        t = threading.Thread(target=self._tien_trinh_lo, args=(ws, lid), daemon=True)
        self.luong[lid] = t
        t.start()
        
    def _tien_trinh_lo(self, ws: str, lid: str):
        try:
            while True:
                if lid in self.huy_flag:
                    break
                data = self.doc_lo(ws, lid)
                if not data: break
                
                muc_idx = next((i for i, m in enumerate(data.get("muc", [])) if m.get("trang_thai") in ("cho", "bi_ngat")), None)
                if muc_idx is None:
                    break
                    
                m = data["muc"][muc_idx]
                m["trang_thai"] = "dang_chay"
                m["buoc_hien_tai"] = "Bắt đầu"
                self.ghi_lo(ws, lid, data)
                
                try:
                    self._chay_muc(ws, lid, m, data)
                    m["trang_thai"] = "xong"
                    m["loi"] = ""
                except Exception as e:
                    m["trang_thai"] = "loi"
                    m["loi"] = str(e)
                    self.ghi_lo(ws, lid, data)
                    break
                self.ghi_lo(ws, lid, data)
        finally:
            self.luong.pop(lid, None)
            self.huy_flag.discard(lid)
            
    def _chay_muc(self, ws: str, lid: str, m: Dict[str, Any], lo_data: Dict[str, Any]):
        da_xong = m.setdefault("da_xong", [])
        pid = m.get("du_an_id")
        folder_da = ""
        if not pid:
            if lo_data.get("che_do") == "gom_mot_du_an" and lo_data.get("du_an_id"):
                pid = lo_data["du_an_id"]
                folder_da = self._thu_muc_da(ws, pid)
                m["du_an_id"] = pid
                self.ghi_lo(ws, lid, lo_data)
            else:
                ts = lo_data.get("thong_so")
                ten = lo_data.get("ten") or "Lô video"
                if lo_data.get("che_do") == "moi_video_mot_du_an":
                    ten = f"{ten} - {os.path.basename(m['nguon'])}"
                da = workspace.tao(ws, ten, ts, "Tạo từ Hàng loạt")
                pid = da["id"]
                folder_da = da["folder"]
                m["du_an_id"] = pid
                if lo_data.get("che_do") == "gom_mot_du_an":
                    lo_data["du_an_id"] = pid
                self.ghi_lo(ws, lid, lo_data)
        else:
            folder_da = self._thu_muc_da(ws, pid)
            
        if luu_tru.dang_bi_giu(folder_da):
            raise RuntimeError("Dự án đang mở ở một cửa sổ khác.")
            
        qlm = getattr(self.r, "qlm")
        mid = m.get("media_id", "")
        
        if "nhap" not in da_xong:
            m["buoc_hien_tai"] = "Nhập media"
            self.ghi_lo(ws, lid, lo_data)
            nguon = m["nguon"]
            if nguon.startswith("http"):
                from orchestrator.pipeline import DOWNLOAD_ADAPTER, PYTHON_EXE
                g = load_global_config()
                cookies = ((g.get("download") or {}).get("cookies_file") or "").strip()
                def lenh(tam: str) -> list:
                    cmd = [PYTHON_EXE, DOWNLOAD_ADAPTER, "--output-dir", tam, "--platform", "generic", "--url", nguon]
                    return cmd + (["--cookies-file", cookies] if cookies else [])
                viec = qlm.tai_url(folder_da, pid, [nguon], lenh, ws)
                self._cho_viec(qlm.hang_chep, viec.id, lid)
                da_cu = luu_tru.doc_duan(folder_da)
                media_moi = [md for md in da_cu["media"] if md.get("url") == nguon]
                if not media_moi:
                    raise RuntimeError("Không nhập được url")
                mid = media_moi[-1]["id"]
                self._cho_viec_media(qlm, mid, lid)
            else:
                tra_ve = qlm.nhap(folder_da, pid, [nguon])
                mid = tra_ve[0]["id"]
                self._cho_viec_media(qlm, mid, lid)
            m["media_id"] = mid
            m["da_xong"].append("nhap")
            self.ghi_lo(ws, lid, lo_data)
            
        if "timeline" not in da_xong:
            m["buoc_hien_tai"] = "Tạo timeline"
            self.ghi_lo(ws, lid, lo_data)
            
            da_hien = luu_tru.doc_duan(folder_da)
            m_obj = next((x for x in da_hien["media"] if x["id"] == mid), None)
            if not m_obj:
                raise RuntimeError("Lỗi tìm media sau khi nhập")
                
            tl, _ = luu_tru.doc_timeline(folder_da)
            t_cuoi = max([float(c.get("bat_dau", 0)) + (float(c.get("ra", 0)) - float(c.get("vao", 0))) / float(c.get("toc_do", 1)) for c in tl["clips"] if c.get("track") == "V1"] + [0.0])
            dai = float(m_obj.get("thoi_luong") or 0)
            cid = luu_tru.id_moi([c["id"] for c in tl["clips"]], "c")
            clip = luu_tru.clip_video(cid, "V1", mid, t_cuoi, dai)
            tl["clips"].append(clip)
            tl["thoi_luong"] = round(t_cuoi + dai, 3)
            
            if "theo_video_dau" in (lo_data.get("thong_so") or {}):
                da_hien["thong_so"] = {
                    "rong": m_obj.get("rong", 1920),
                    "cao": m_obj.get("cao", 1080),
                    "fps": m_obj.get("fps", 30),
                    "ti_le": f"{m_obj.get('rong', 1920)}:{m_obj.get('cao', 1080)}",
                    "mau_nen": "#000000"
                }
                luu_tru.ghi_duan(folder_da, da_hien)
                
            luu_tru.ghi_timeline(folder_da, tl, tl.get("phien_ban", 0))
            m["da_xong"].append("timeline")
            self.ghi_lo(ws, lid, lo_data)
            
        buoc = lo_data.get("buoc", {})
        
        if buoc.get("phu_de") and "phu_de" not in da_xong:
            m["buoc_hien_tai"] = "Tạo phụ đề / OCR"
            self.ghi_lo(ws, lid, lo_data)
            da_hien = luu_tru.doc_duan(folder_da)
            m_obj = next((x for x in da_hien["media"] if x["id"] == mid), {})
            loai_sub = buoc["phu_de"]
            tham_so_sub = {}
            if loai_sub == "ocr":
                vung = buoc.get("vung_ocr", {})
                tham_so_sub = {
                    "vung": vung, "tao_che": buoc.get("che_phu_de", False),
                    "vung_px": {
                        "x": int(vung.get("x", 0) * m_obj.get("rong", 1920)),
                        "y": int(vung.get("y", 0) * m_obj.get("cao", 1080)),
                        "w": int(vung.get("w", 0) * m_obj.get("rong", 1920)),
                        "h": int(vung.get("h", 0) * m_obj.get("cao", 1080))
                    }
                }
            else:
                loai_sub = "phu-de"
            xep_ai = getattr(self.r, "xep_ai")
            hang_gpu = getattr(self.r, "hang_gpu")
            viec_ai = xep_ai(folder_da, pid, loai_sub, mid, tham_so_sub)
            kq = self._cho_viec(hang_gpu, viec_ai.id, lid)
            tl, _ = luu_tru.doc_timeline(folder_da)
            da_hien = luu_tru.doc_duan(folder_da)
            ap_dung(loai_sub, tl, kq, mid, tham_so_sub, da_hien["media"])
            luu_tru.ghi_timeline(folder_da, tl, tl.get("phien_ban", 0))
            m["da_xong"].append("phu_de")
            self.ghi_lo(ws, lid, lo_data)
            
        if "dich" in buoc and buoc["dich"] is not None and "dich" not in da_xong:
            m["buoc_hien_tai"] = "Dịch"
            self.ghi_lo(ws, lid, lo_data)
            tl, _ = luu_tru.doc_timeline(folder_da)
            tr_pd = next((t for t in tl["tracks"] if t["loai"] == "phu_de"), None)
            if tr_pd:
                cau = [c for c in tl["clips"] if c.get("track") == tr_pd["id"] and c.get("tu_media") == mid and str(c.get("text", "")).strip()]
                if cau:
                    tham_so_dich = dict(buoc["dich"])
                    tham_so_dich["cau"] = [{"t_vao": c.get("t_vao"), "t_ra": c.get("t_ra"), "text": c.get("text")} for c in cau]
                    tham_so_dich["ids"] = [c.get("id") for c in cau]
                    xep_ai = getattr(self.r, "xep_ai")
                    hang_gpu = getattr(self.r, "hang_gpu")
                    viec_ai = xep_ai(folder_da, pid, "dich", mid, tham_so_dich)
                    kq = self._cho_viec(hang_gpu, viec_ai.id, lid)
                    tl, _ = luu_tru.doc_timeline(folder_da)
                    da_hien = luu_tru.doc_duan(folder_da)
                    ap_dung("dich", tl, kq, mid, tham_so_dich, da_hien["media"])
                    luu_tru.ghi_timeline(folder_da, tl, tl.get("phien_ban", 0))
            m["da_xong"].append("dich")
            self.ghi_lo(ws, lid, lo_data)
                
        if "long_tieng" in buoc and buoc["long_tieng"] is not None and "long_tieng" not in da_xong:
            m["buoc_hien_tai"] = "Lồng tiếng"
            self.ghi_lo(ws, lid, lo_data)
            tl, _ = luu_tru.doc_timeline(folder_da)
            tr_pd = next((t for t in tl["tracks"] if t["loai"] == "phu_de"), None)
            if tr_pd:
                cau = [c for c in tl["clips"] if c.get("track") == tr_pd["id"] and c.get("tu_media") == mid and str(c.get("text", "")).strip()]
                if cau:
                    tham_so_lt = dict(buoc["long_tieng"])
                    tham_so_lt["cau"] = [{"t_vao": c.get("t_vao"), "t_ra": c.get("t_ra"), "text": c.get("text")} for c in cau]
                    tham_so_lt["ids"] = [c.get("id") for c in cau]
                    xep_ai = getattr(self.r, "xep_ai")
                    hang_gpu = getattr(self.r, "hang_gpu")
                    viec_ai = xep_ai(folder_da, pid, "long-tieng", mid, tham_so_lt)
                    kq = self._cho_viec(hang_gpu, viec_ai.id, lid)
                    tl, _ = luu_tru.doc_timeline(folder_da)
                    da_hien = luu_tru.doc_duan(folder_da)
                    ap_dung("long-tieng", tl, kq, mid, tham_so_lt, da_hien["media"])
                    luu_tru.ghi_timeline(folder_da, tl, tl.get("phien_ban", 0))
            m["da_xong"].append("long_tieng")
            self.ghi_lo(ws, lid, lo_data)
                
        if "xuat" in buoc and buoc["xuat"] is not None:
            cuoi_cung = (lo_data["muc"][-1]["nguon"] == m["nguon"])
            if lo_data.get("che_do") == "gom_mot_du_an" and not cuoi_cung:
                pass
            elif "xuat" not in da_xong:
                m["buoc_hien_tai"] = "Xuất video"
                self.ghi_lo(ws, lid, lo_data)
                
                tc = dict(buoc["xuat"])
                xep_xuat = getattr(self.r, "xep_xuat")
                viec, rel_path = xep_xuat(folder_da, pid, tc)
                
                hang_gpu = getattr(self.r, "hang_gpu")
                self._cho_viec(hang_gpu, viec.id, lid)
                
                m["da_xong"].append("xuat")
                self.ghi_lo(ws, lid, lo_data)

    def _thu_muc_da(self, ws: str, pid: str) -> str:
        the, bang = workspace.quet(ws, [])
        if pid in bang:
            return bang[pid]
        raise RuntimeError("Không tìm thấy dự án")

    def _cho_viec(self, hang, vid: str, lid: str):
        while True:
            if lid in self.huy_flag:
                hang.huy(vid)
                raise RuntimeError("Bị huỷ")
            ds = hang.danh_sach()
            v = next((x for x in ds if x["id"] == vid), None)
            if not v:
                raise RuntimeError("Mất tác vụ")
            if v["trang_thai"] == "xong":
                return v.get("ket_qua", {})
            if v["trang_thai"] in ("loi", "bi_ngat", "da_huy"):
                raise RuntimeError(v.get("loi") or "Lỗi tác vụ")
            time.sleep(1)
            
    def _cho_viec_media(self, qlm, mid: str, lid: str):
        while True:
            if lid in self.huy_flag:
                raise RuntimeError("Bị huỷ")
            song = False
            for h in qlm.cac_hang():
                for v in h.danh_sach():
                    if v.get("media") == mid and v["trang_thai"] in ("cho", "dang_chay"):
                        song = True
                        break
                if song: break
            if not song:
                return
            time.sleep(1)


def dang_ky_routes(r: APIRouter):
    mgr = QuanLyHangLoat(r)
    
    @r.post("/api/hang-loat")
    def tao_lo(body: HangLoatSchema):
        ws = workspace.lay_workspace({"editor": load_global_config().get("editor") or {}})
        lid = uuid.uuid4().hex[:8]
        
        muc = []
        files = list(body.files)
        if body.thu_muc:
            from orchestrator.storage import scan_video_files
            files.extend(scan_video_files(body.thu_muc))
        for f in files:
            muc.append({"nguon": f, "du_an_id": "", "buoc_hien_tai": "Chờ", "trang_thai": "cho", "loi": ""})
        for u in body.urls:
            muc.append({"nguon": u, "du_an_id": "", "buoc_hien_tai": "Chờ", "trang_thai": "cho", "loi": ""})
            
        data = {
            "id": lid,
            "tao_luc": luu_tru._iso(),
            "che_do": body.che_do,
            "ten": body.ten,
            "thong_so": body.thong_so,
            "buoc": body.buoc.model_dump(exclude_none=True),
            "muc": muc
        }
        mgr.ghi_lo(ws, lid, data)
        mgr.chay_lo(ws, lid)
        return {"id": lid}
        
    @r.get("/api/hang-loat")
    def get_lo_list():
        ws = workspace.lay_workspace({"editor": load_global_config().get("editor") or {}})
        mgr.kiem_tra_bi_ngat(ws)
        d = mgr.path_dir(ws)
        res = []
        for f in os.listdir(d):
            if f.endswith(".json"):
                data = mgr.doc_lo(ws, f[:-5])
                if data:
                    res.append(data)
        res.sort(key=lambda x: x.get("tao_luc", ""), reverse=True)
        return {"lo": res}
        
    @r.get("/api/hang-loat/{lid}")
    def get_lo(lid: str):
        ws = workspace.lay_workspace({"editor": load_global_config().get("editor") or {}})
        data = mgr.doc_lo(ws, lid)
        if not data:
            raise HTTPException(404, "Không có lô này")
        return {"lo": data}
        
    @r.post("/api/hang-loat/{lid}/chay-tiep")
    def chay_tiep_lo(lid: str):
        ws = workspace.lay_workspace({"editor": load_global_config().get("editor") or {}})
        data = mgr.doc_lo(ws, lid)
        if not data:
            raise HTTPException(404, "Không có lô này")
        if lid in mgr.luong and mgr.luong[lid].is_alive():
            raise HTTPException(409, "Lô đang chạy")
        mgr.chay_lo(ws, lid)
        return {"status": "success"}
        
    @r.post("/api/hang-loat/{lid}/huy")
    def huy_lo(lid: str):
        mgr.huy_flag.add(lid)
        return {"status": "success"}
