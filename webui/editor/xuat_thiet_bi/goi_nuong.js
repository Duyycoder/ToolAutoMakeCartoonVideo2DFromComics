/* Gọi server "nướng" phần máy không tự làm (orchestrator/editor/nuong.py) rồi phục vụ lại cho bộ ghép khung:
   - lớp chữ: ảnh PNG trong suốt do libass vẽ (chữ, hình vẽ, phụ đề) — chồng lên khung đã ghép, khớp bản server;
   - đoạn nướng: các khung [a, b) server dựng sẵn (chỉnh màu nâng cao, chuyển cảnh lạ, nguồn máy không giải mã được).
   Khung đánh số trên lưới fps xuất (n = t × fps); bộ ghép hỏi theo n TĂNG DẦN. */
import { api } from '../chung.js';
import { choTacVu } from './tieng_server.js';
import { NguonVideo } from './nguon_video.js';

export class KetQuaNuong {
    /* Gửi việc + chờ xong. tc: {do_phan_giai, fps}. doan: [[a, b], …] khung. */
    static async tao(pid, phien, tc, n0, n1, lopChu, doan, baoTienDo, daHuy) {
        const g = `/api/du-an/${encodeURIComponent(pid)}`;
        const r = await api(`${g}/nuong`, { method: 'POST', body: { phien, tuy_chon: tc, n0, n1, lop_chu: lopChu, doan } });
        const k = new KetQuaNuong();
        k.goc = `${g}/nuong/${encodeURIComponent(r.viec.id)}`;
        try {
            const v = await choTacVu(g, r.viec.id, 'dựng phần máy không làm được', baoTienDo, daHuy);
            await k._mo(v.ket_qua || {});
        } catch (e) { k.dong(); throw e; }
        return k;
    }

    async _mo(kq) {
        this.chu = kq.lop_chu || [];          // [{tu, den, file}] tăng dần
        this.iChu = 0;
        this.anh = new Map();                 // file → Promise<ImageBitmap>
        this.khuc = (kq.doan && kq.doan.khuc) || [];
        if (kq.doan) {
            this.nguon = await NguonVideo.mo(`${this.goc}/${kq.doan.file}`);
            if (!this.nguon.giaiMaDuoc) throw new Error('Máy không giải mã được đoạn server dựng (H.264).');
            this.fps = Number(kq.fps);
            this.soKhung = kq.doan.so_khung;
        }
    }

    /* Xuất tiếp từ khung n: bỏ qua các khung nướng đứng trước (đoạn nướng nối liền: khung thứ j của file = j / fps). */
    datBatDau(n) {
        this.boQua = this.khuc.reduce((s, [a, b]) => s + Math.max(0, Math.min(b, n) - a), 0);
    }

    _luong() {
        if (!this.luong) {
            const ds = [];
            for (let j = this.boQua || 0; j < this.soKhung; j++) ds.push(j / this.fps);
            this.luong = this.nguon.khungTai(ds)[Symbol.asyncIterator]();
        }
        return this.luong;
    }

    laNuong(n) {
        return this.khuc.some(([a, b]) => n >= a && n < b);
    }

    /* Khung server dựng cho n (chỉ gọi khi laNuong(n), n tăng dần) → VideoSample (đóng ở lần gọi sau / dong()). */
    async khungNuong() {
        const r = await this._luong().next();
        if (r.done || !r.value) return this.mau;
        if (this.mau) this.mau.close();
        this.mau = r.value;
        return this.mau;
    }

    _taiAnh(file) {
        if (!this.anh.has(file)) {
            this.anh.set(file, fetch(`${this.goc}/${file}`).then((x) => {
                if (!x.ok) throw new Error(`Không tải được lớp chữ (HTTP ${x.status})`);
                return x.blob();
            }).then((b) => createImageBitmap(b)));
        }
        return this.anh.get(file);
    }

    /* Ảnh lớp chữ cho khung n (null nếu không có chữ). Tải trước 3 ảnh kế tiếp, nhả ảnh đã qua. */
    async anhChu(n) {
        while (this.iChu < this.chu.length && this.chu[this.iChu].den <= n) {
            const cu = this.chu[this.iChu++].file;
            if (!this.chu.slice(this.iChu).some((x) => x.file === cu) && this.anh.has(cu)) {
                this.anh.get(cu).then((b) => b.close(), () => {});
                this.anh.delete(cu);
            }
        }
        for (let j = this.iChu; j < Math.min(this.chu.length, this.iChu + 4); j++) this._taiAnh(this.chu[j].file);
        const x = this.chu[this.iChu];
        return x && x.tu <= n ? this._taiAnh(x.file) : null;
    }

    dong() {
        try { if (this.mau) this.mau.close(); } catch (e) { /* đã đóng */ }
        if (this.luong && this.luong.return) this.luong.return();
        if (this.nguon) this.nguon.dong();
        for (const p of (this.anh || new Map()).values()) p.then((b) => b.close(), () => {});
        if (this.goc) api(this.goc, { method: 'DELETE' }).catch(() => {});
    }
}
