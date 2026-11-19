import { tao, idClipMoi, choTrong, opsThemTrack, clipChuMacDinh } from './store.js';

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
                <h3 style="margin:16px 0 8px;font-size:12px;color:var(--chu-3)">MẪU CHỮ</h3>
                <div class="nhom-mau-chu" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">${MAU_CHU.map((m, i) => `<button class="nut mau-chu" data-mau="${i}"
                    style="height:54px;font-family:'${m.kieu.font || 'Arial'}';font-weight:${m.kieu.dam ? 700 : 400};font-style:${m.kieu.nghieng ? 'italic' : 'normal'};color:${m.kieu.mau};
                    ${m.kieu.nen ? `background:${m.kieu.nen_mau};` : `background:#3a3f4b;text-shadow:0 0 2px ${m.kieu.vien_mau || '#000'},0 0 2px ${m.kieu.vien_mau || '#000'};`}">${m.ten}</button>`).join('')}</div>
            </div>`;
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
