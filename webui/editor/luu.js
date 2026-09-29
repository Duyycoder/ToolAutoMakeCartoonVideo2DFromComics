/* Bộ lưu tiến độ: tự lưu, khoá/heartbeat, flush khi đóng, xung đột phiên bản.
 *
 * - Timeline: sửa xong 1,5 s (cấu hình `editor.tu_luu_giay`) không thao tác thì PUT, kèm
 *   `phien_ban` → server trả 409 nếu dự án đã sửa ở cửa sổ khác.
 * - ui.json: thưa hơn (3 s), hoặc ngay khi đổi bảng / tạm dừng ở đầu phát mới.
 * - Đóng: desktop.py gọi `window.editor.flush()` và CHỜ Promise (đường chính). Trình
 *   duyệt thường thì `pagehide`: sendBeacon ui.json (chỉ POST, ≤64 KB) + fetch keepalive
 *   cho timeline nếu vừa cỡ; lớn hơn thì chấp nhận mất tối đa 1,5 s thao tác cuối.
 */
import { api, LoiApi } from './chung.js';

const GIOI_HAN_KEEPALIVE = 60000;

export class BoLuu {
    constructor({ duAnId, phien, phienBan, chiDoc, tuLuuGiay = 1.5, layTimeline, layNgan, layUi,
        khiTrangThai = () => {}, khiXungDot = () => {}, khiMatKhoa = () => {}, khiCoKhoa = () => {} }) {
        Object.assign(this, { duAnId, phien, phienBan, chiDoc, layTimeline, layNgan, layUi,
            khiTrangThai, khiXungDot, khiMatKhoa, khiCoKhoa });
        this.treTimeline = Math.max(300, tuLuuGiay * 1000);
        this.treUi = 3000;
        this.banTimeline = false;
        this.banUi = false;
        this._hTimeline = null;
        this._hUi = null;
        this._dangLuu = null;       // Promise lần PUT timeline đang bay
        this._loi = false;
        this._nhip = setInterval(() => this.nhip(), 15000);
        this._ganDong();
    }

    get url() { return `/api/du-an/${encodeURIComponent(this.duAnId)}`; }

    trangThai() {
        if (this.chiDoc) return 'chi_doc';
        if (this._dangLuu) return 'dang';
        if (this._loi) return 'loi';
        return this.banTimeline ? 'ban' : 'sach';
    }

    _bao() { this.khiTrangThai(this.trangThai()); }

    danhDauTimeline() {
        if (this.chiDoc) return;
        this.banTimeline = true;
        clearTimeout(this._hTimeline);
        this._hTimeline = setTimeout(() => this.luuTimeline().catch(() => {}), this.treTimeline);
        this._bao();
    }

    danhDauUi(som = false) {
        if (this.chiDoc) return;
        this.banUi = true;
        clearTimeout(this._hUi);
        this._hUi = setTimeout(() => this.luuUi().catch(() => {}), som ? 150 : this.treUi);
    }

    async luuTimeline() {
        clearTimeout(this._hTimeline);
        if (this._dangLuu) await this._dangLuu.catch(() => {});
        if (!this.banTimeline || this.chiDoc) return;
        this.banTimeline = false;
        const body = { phien: this.phien, phien_ban: this.phienBan, timeline: this.layTimeline(), hoan_tac: this.layNgan() };
        this._dangLuu = api(`${this.url}/timeline`, { method: 'PUT', body });
        this._bao();
        try {
            const r = await this._dangLuu;
            this.phienBan = r.phien_ban;
            this._loi = false;
        } catch (e) {
            this.banTimeline = true;   // chưa ghi được thì vẫn còn "bẩn"
            this._loi = true;
            this._xuLyLoi(e);
            throw e;
        } finally {
            this._dangLuu = null;
            this._bao();
        }
    }

    async luuUi() {
        clearTimeout(this._hUi);
        if (!this.banUi || this.chiDoc) return;
        this.banUi = false;
        try {
            await api(`${this.url}/ui`, { method: 'PUT', body: { phien: this.phien, ui: this.layUi() } });
        } catch (e) {
            this.banUi = true;
            this._xuLyLoi(e);
        }
    }

    _xuLyLoi(e) {
        if (!(e instanceof LoiApi)) return;
        if (e.status === 409) this.khiXungDot(e.detail && e.detail.hien_tai);
        if (e.status === 423) { this.chiDoc = true; this.khiMatKhoa(); this._bao(); }
    }

    /* Ghi đè bản trên đĩa bằng bản đang sửa (người dùng chọn sau khi gặp 409). */
    async ghiDe(hienTai) {
        this.phienBan = hienTai;
        this.banTimeline = true;
        await this.luuTimeline();
    }

    /* Lưu hết ngay (nút Lưu, Ctrl+S, quay về trang chủ, desktop.py đóng cửa sổ). */
    async flush() {
        await Promise.all([this.luuTimeline().catch(() => {}), this.luuUi()]);
        return !this.banTimeline;
    }

    async luuTay(nhan = '') {
        await this.flush();
        if (this.banTimeline) throw new Error('Chưa ghi được tiến độ — xem lỗi phía trên.');
        return api(`${this.url}/luu`, { method: 'POST', body: { phien: this.phien, nhan } });
    }

    async nhip() {
        try {
            const r = await api(`${this.url}/nhip`, { method: 'POST', body: { phien: this.phien } });
            if (r.giu_khoa && this.chiDoc) this.khiCoKhoa();
            if (!r.giu_khoa && !this.chiDoc) { this.chiDoc = true; this.khiMatKhoa(); this._bao(); }
        } catch (e) { /* server đang tắt — lần sau thử lại */ }
    }

    /* Lưu hết + nhả khoá. `ngungNhip=false` khi cửa sổ có thể còn sống (desktop hỏi xác nhận). */
    async dong(ngungNhip = true) {
        if (ngungNhip) clearInterval(this._nhip);
        await this.flush();
        if (!this.chiDoc) await api(`${this.url}/dong`, { method: 'POST', body: { phien: this.phien } }).catch(() => {});
    }

    _ganDong() {
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') this.flush();
        });
        window.addEventListener('pagehide', () => {
            if (this.chiDoc) return;
            if (this.banTimeline && !this._dangLuu) {
                const body = JSON.stringify({ phien: this.phien, phien_ban: this.phienBan,
                    timeline: this.layTimeline(), hoan_tac: this.layNgan() });
                if (body.length < GIOI_HAN_KEEPALIVE) {
                    fetch(`${this.url}/timeline`, { method: 'PUT', keepalive: true, body,
                        headers: { 'Content-Type': 'application/json' } }).catch(() => {});
                }
            }
            // dong:true = nhả khoá luôn; F5 thì trang mới mở lại bằng CÙNG mã phiên nên lấy lại ngay.
            const ui = JSON.stringify({ phien: this.phien, ui: this.layUi(), dong: true });
            if (ui.length < GIOI_HAN_KEEPALIVE) navigator.sendBeacon(`${this.url}/ui-beacon`, ui);
        });
    }
}
