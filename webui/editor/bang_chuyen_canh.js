/* Bảng ⊘ Chuyển cảnh — lưới các kiểu xfade với minh hoạ CSS animation.
 * Theo mẫu bang_hieu_ung.js (lượt 8): đăng ký trong main.js › cacBang.
 *
 * Bấm thẻ khi đang chọn một clip trên track nền → áp vào điểm nối CUỐI clip đó.
 * Kéo thẻ thả lên timeline gần điểm nối (±12 px) → áp vào điểm nối đó.
 */
import { esc, toast } from './chung.js';
import { ketThucClip, opsThemChuyenCanh, trackVideoTuDuoiLen } from './store.js';

// Giải thích: Danh sách kiểu xfade cố định, khớp với CAC_KIEU_XFADE trong render.py.
// Mỗi mục có id (tên ffmpeg), tên tiếng Việt để hiển thị.
const CAC_KIEU = [
    { id: 'fade', ten: 'Mờ dần' },
    { id: 'fadeblack', ten: 'Mờ qua đen' },
    { id: 'fadewhite', ten: 'Mờ qua trắng' },
    { id: 'dissolve', ten: 'Tan biến' },
    { id: 'wipeleft', ten: 'Lau trái' },
    { id: 'wiperight', ten: 'Lau phải' },
    { id: 'wipeup', ten: 'Lau lên' },
    { id: 'wipedown', ten: 'Lau xuống' },
    { id: 'slideleft', ten: 'Trượt trái' },
    { id: 'slideright', ten: 'Trượt phải' },
    { id: 'slideup', ten: 'Trượt lên' },
    { id: 'slidedown', ten: 'Trượt xuống' },
    { id: 'smoothleft', ten: 'Trơn trái' },
    { id: 'smoothright', ten: 'Trơn phải' },
    { id: 'circleopen', ten: 'Tròn mở' },
    { id: 'circleclose', ten: 'Tròn đóng' },
    { id: 'radial', ten: 'Xoay tia' },
    { id: 'pixelize', ten: 'Vỡ hạt' },
    { id: 'diagtl', ten: 'Chéo TL' },
    { id: 'diagtr', ten: 'Chéo TR' },
    { id: 'diagbl', ten: 'Chéo BL' },
    { id: 'diagbr', ten: 'Chéo BR' },
    { id: 'zoomin', ten: 'Phóng vào' },
    { id: 'squeezeh', ten: 'Ép ngang' },
    { id: 'squeezev', ten: 'Ép dọc' },
];

// Giải thích: Export danh sách kiểu để các module khác (bang_phai.js) lấy tên tiếng Việt.
export { CAC_KIEU };

export class BangChuyenCanh {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Chuyển cảnh</h2></div><div class="bang-noi" data-khu="noi" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;padding:10px;overflow-y:auto"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');

        this.noi.addEventListener('click', (e) => {
            const the = e.target.closest('.the-cc');
            if (the) this._apDung(the.dataset.loai);
        });

        // Giải thích: Kéo thẻ chuyển cảnh → dragstart với dữ liệu kiểu xfade,
        // timeline.js sẽ nhận drop gần điểm nối (±12px).
        this.noi.addEventListener('dragstart', (e) => {
            const the = e.target.closest('.the-cc');
            if (!the) return;
            e.dataTransfer.setData('application/x-chuyen-canh', the.dataset.loai);
            e.dataTransfer.effectAllowed = 'copy';
        });

        ctx.bus.on('chon', () => { if (this.el.isConnected) this.ve(true); });
        ctx.bus.on('timeline', () => {
            if (this.el.isConnected) {
                if (document.activeElement && this.el.contains(document.activeElement)
                    && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
                this.ve();
            }
        });
    }

    get tl() { return this.ctx.store.timeline; }

    ve(ep = false) {
        if (!ep && this._daVe) return;
        this._daVe = true;

        const html = CAC_KIEU.map(k => {
            // Giải thích: Minh hoạ bằng CSS animation đơn giản — 2 ô màu chuyển nhau.
            // Ô trái (đỏ) mờ dần, ô phải (xanh) hiện lên, tạo hiệu ứng chuyển cảnh gần đúng.
            return `<div class="the-cc" data-loai="${esc(k.id)}" draggable="true"
                style="cursor:grab;border:1px solid var(--vien);border-radius:4px;overflow:hidden;text-align:center">
                <div style="height:40px;position:relative;overflow:hidden;background:#2196f3">
                    <div style="position:absolute;inset:0;background:#f44336;animation:cc-minh-hoa 2s ease-in-out infinite alternate"></div>
                </div>
                <div style="padding:3px 2px;font-size:11px;background:var(--nen-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(k.ten)}</div>
            </div>`;
        }).join('');
        this.noi.innerHTML = html;

        // Giải thích: Thêm CSS animation một lần (nếu chưa có) — đơn giản fade.
        if (!document.getElementById('cc-anim-style')) {
            const s = document.createElement('style');
            s.id = 'cc-anim-style';
            s.textContent = '@keyframes cc-minh-hoa{0%{opacity:1}100%{opacity:0}}';
            document.head.appendChild(s);
        }
    }

    _apDung(loai) {
        const chon = this.ctx.ui.dang_chon;
        if (!chon || chon.length !== 1) {
            toast('Chọn một clip trên track nền trước.', 'warn');
            return;
        }
        const cid = chon[0];
        const c = this.tl.clips.find(x => x.id === cid);
        if (!c) return;

        // Giải thích: Chỉ áp cho clip trên track video NỀN (track cuối trong danh sách video).
        const vTracks = trackVideoTuDuoiLen(this.tl);
        const trackNen = vTracks.length ? vTracks[0].id : null;
        if (!trackNen || c.track !== trackNen) {
            toast('Chỉ áp chuyển cảnh cho clip trên track nền.', 'warn');
            return;
        }

        // Tìm clip kề SAU clip đang chọn
        const kt = ketThucClip(c);
        const clipsNen = this.tl.clips.filter(x => x.track === trackNen)
            .sort((a, b) => Number(a.bat_dau || 0) - Number(b.bat_dau || 0));
        const sau = clipsNen.find(x => Math.abs(Number(x.bat_dau || 0) - kt) <= 0.05 && x.id !== c.id);
        if (!sau) {
            toast('Không có clip kề sau để áp chuyển cảnh.', 'warn');
            return;
        }

        const ops = opsThemChuyenCanh(this.tl, cid, sau.id, loai, 0.5);
        this.ctx.sua(`Thêm chuyển cảnh ${loai}`, ops);
    }
}
