import { tao, idClipMoi, choTrong, opsThemTrack, clipChuMacDinh } from './store.js';
import { toast } from './chung.js';
import { taiLenFile } from './tai_len.js';

/* Ops thêm một clip chữ/hình dài `dai` giây tại đầu phát vào track lớp phủ còn trống đúng chỗ đó (không có thì track
   lớp phủ đầu tiên, dời về sau; chưa có track nào thì thêm track O1).
   Dùng chung cho bảng T Chữ và nhóm Hình dạng của bảng ⬠. `taoClip(id, track, bd, dai)` sinh clip mặc định. */
export function opsThemLopPhu(tl, t, dai, taoClip) {
    const cac = tl.tracks.filter((tr) => tr.loai === 'lop_phu' && !tr.khoa);
    let trackId = (cac.find((tr) => choTrong(tl, tr.id, t, dai) === t) || cac[0] || tl.tracks.find((tr) => tr.loai === 'lop_phu') || {}).id;
    const ops = [];
    if (!trackId) { const moi = opsThemTrack(tl, 'lop_phu'); trackId = moi.id; ops.push(...moi.ops); }
    const bd = choTrong(tl, trackId, t, dai);          // choTrong trả SỐ: giờ bắt đầu còn trống trên track
    const clip = taoClip(idClipMoi(tl), trackId, bd, dai);
    ops.push(tao.them(tl, ['clips'], clip));
    return { ops, clip };
}

/* Sticker emoji. Bản xuất vẽ chữ bằng libass (không có emoji màu) nên sticker KHÔNG phải clip chữ: emoji được vẽ ra ảnh PNG
   nền trong suốt ngay trên trình duyệt (dùng bộ emoji của máy), tải lên dự án như một ảnh, rồi đặt thành lớp video phủ —
   nhờ vậy sticker dời, phóng, xoay, đặt keyframe, hiệu ứng vào/ra y như mọi clip ảnh và xuất ra đúng như xem trước. */
export const STICKER = ['😀', '😂', '🤣', '😍', '🥰', '😎', '🤔', '😱', '😭', '😡', '🥺', '😴', '🤯', '🤡', '👀', '💀',
    '👍', '👎', '👏', '🙏', '💪', '👉', '👈', '👆', '👇', '✌️', '🤝', '❤️', '💔', '🔥', '✨', '⭐',
    '💯', '❗', '❓', '‼️', '✅', '❌', '⚠️', '💥', '💢', '💤', '💬', '💭', '🎉', '🎁', '🏆', '👑',
    '💰', '💸', '📌', '📢', '🔔', '🎵', '📷', '🎬', '⏰', '🚀', '🌈', '☀️', '🌙', '⚡', '🍀', '🌹'];

/* Emoji → File PNG 512×512 nền trong suốt. Tên file theo mã Unicode để cùng một emoji chỉ tải lên một lần. */
export function tenSticker(emoji) {
    return `sticker-${[...emoji].map((ch) => ch.codePointAt(0).toString(16)).join('-')}`;
}

function anhSticker(emoji) {
    const cv = document.createElement('canvas');
    cv.width = 512; cv.height = 512;
    const g = cv.getContext('2d');
    g.font = '400px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(emoji, 256, 280);
    return new Promise((xong) => cv.toBlob((b) => xong(new File([b], `${tenSticker(emoji)}.png`, { type: 'image/png' })), 'image/png'));
}

/* Mẫu chữ dựng sẵn: bấm là thêm clip chữ với kiểu này tại đầu phát (sửa tiếp ở bảng thuộc tính). */
export const MAU_CHU = [
    { ten: 'Tiêu đề lớn', kieu: { font: 'Impact', co: 110, mau: '#ffffff', vien_mau: '#000000', vien_day: 4, bong: true }, bien_doi: { y: 0.2 } },
    { ten: 'Vàng nổi bật', kieu: { font: 'Montserrat', co: 80, mau: '#ffd60a', vien_mau: '#000000', vien_day: 4, dam: true } },
    { ten: 'Hộp đen', kieu: { font: 'Arial', co: 56, mau: '#ffffff', nen: true, nen_mau: '#000000', dam: true } },
    { ten: 'Hộp trắng', kieu: { font: 'Arial', co: 56, mau: '#111111', nen: true, nen_mau: '#ffffff', dam: true } },
    { ten: 'Nhãn đỏ', kieu: { font: 'Montserrat', co: 60, mau: '#ffffff', nen: true, nen_mau: '#e63946', dam: true } },
    { ten: 'Chú thích', kieu: { font: 'Arial', co: 38, mau: '#ffffff', vien_mau: '#000000', vien_day: 2, nghieng: true }, bien_doi: { y: 0.85 } },
    { ten: 'Đánh máy', kieu: { font: 'Verdana', co: 52, mau: '#00ff9c', vien_mau: '#003322', vien_day: 2 }, hieu_ung_vao: 'danh_may' },
    { ten: 'Hồng dễ thương', kieu: { font: 'Comic Sans MS', co: 64, mau: '#ff8fab', vien_mau: '#ffffff', vien_day: 4, dam: true } },
];

export class BangChu {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `
            <div class="bang-dau"><h2>Chữ</h2></div>
            <div class="bang-noi" data-khu="noi" style="padding:12px">
                <div class="nhom-nut-chu" style="display:flex;flex-direction:column;gap:8px">
                    <button class="nut" data-l="them-tieu-de">+ Tiêu đề</button>
                    <button class="nut" data-l="them-chu-thuong">+ Chữ thường</button>
                </div>
                <h3 style="margin:16px 0 8px;font-size:12px;color:var(--chu-3)">STICKER</h3>
                <div class="nhom-sticker" style="display:grid;grid-template-columns:repeat(8,1fr);gap:2px">${STICKER.map((e) =>
                    `<button class="nut-icon" data-sticker="${e}" style="font-size:20px;width:auto;height:34px" title="Thêm sticker ${e} tại đầu phát">${e}</button>`).join('')}</div>
                <h3 style="margin:16px 0 8px;font-size:12px;color:var(--chu-3)">MẪU CHỮ</h3>
                <div class="nhom-mau-chu" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">${MAU_CHU.map((m, i) => `<button class="nut mau-chu" data-mau="${i}"
                    style="height:54px;font-family:'${m.kieu.font || 'Arial'}';font-weight:${m.kieu.dam ? 700 : 400};font-style:${m.kieu.nghieng ? 'italic' : 'normal'};color:${m.kieu.mau};
                    ${m.kieu.nen ? `background:${m.kieu.nen_mau};` : `background:#3a3f4b;text-shadow:0 0 2px ${m.kieu.vien_mau || '#000'},0 0 2px ${m.kieu.vien_mau || '#000'};`}">${m.ten}</button>`).join('')}</div>
            </div>`;
        this.el.querySelector('.nhom-sticker').addEventListener('click', (e) => {
            const b = e.target.closest('[data-sticker]');
            if (b) this.themSticker(b.dataset.sticker);
        });
        this.el.querySelector('.nhom-mau-chu').addEventListener('click', (e) => {
            const b = e.target.closest('[data-mau]');
            if (b) this.them(false, MAU_CHU[Number(b.dataset.mau)]);
        });
        this.el.querySelector('.nhom-nut-chu').addEventListener('click', (e) => {
            const b = e.target.closest('[data-l]');
            if (b) this.them(b.dataset.l === 'them-tieu-de');
        });
    }

    ve() {}

    /* Thêm sticker emoji tại đầu phát: dùng lại ảnh đã có trong dự án, chưa có thì vẽ và tải lên. Đặt cỡ 25% khung. */
    async themSticker(emoji) {
        if (this.ctx.store.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        const dat = (m) => {
            const tlUi = this.ctx.timeline;
            tlUi.themLopTaiDauPhat(m);
            const tl = this.ctx.store.timeline;
            const c = tl.clips.find((x) => x.id === this.ctx.chon.clip);
            if (c && c.media === m.id) this.ctx.sua('Cỡ sticker', [tao.dat(tl, ['clips', { id: c.id }, 'bien_doi'], { ...(c.bien_doi || {}), ti_le: 0.25 })]);
        };
        const ten = tenSticker(emoji);
        const co = this.ctx.media.find((m) => m.loai === 'anh' && m.ten === ten && m.trang_thai === 'san_sang' && !m.mat_file);
        if (co) { dat(co); return; }
        try {
            const file = await anhSticker(emoji);
            const hua = taiLenFile(this.ctx.id, this.ctx.boLuu.phien, file).then((ds) => ({ media: ds }));
            this.ctx.timeline._nhapRoiDat(hua, dat);
        } catch (e) { toast(`Không thêm được sticker: ${e.message}`, 'error'); }
    }

    them(laTieuDe, mau = null) {
        const tl = this.ctx.store.timeline;
        const { ops, clip } = opsThemLopPhu(tl, this.ctx.ui.dau_phat || 0, 3,
            (id, tr, bd, dai) => clipChuMacDinh(id, tr, bd, dai, laTieuDe, mau));
        if (this.ctx.sua('Thêm chữ', ops)) {
            this.ctx.timeline.chonClip(clip.id);
            this.ctx.timeline.datDauPhat(clip.bat_dau);
        }
    }
}
