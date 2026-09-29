import { tao, idClipMoi, choTrong, opsThemTrack, clipChuMacDinh } from './store.js';

/* Ops thêm một clip chữ/hình dài `dai` giây tại đầu phát vào track lớp phủ đang có (chưa có thì thêm track O1).
   Dùng chung cho bảng T Chữ và nhóm Hình dạng của bảng ⬠. `taoClip(id, track, bd, dai)` sinh clip mặc định. */
export function opsThemLopPhu(tl, t, dai, taoClip) {
    let trackId = (tl.tracks.find((tr) => tr.loai === 'lop_phu') || {}).id;
    const ops = [];
    if (!trackId) { const moi = opsThemTrack(tl, 'lop_phu'); trackId = moi.id; ops.push(...moi.ops); }
    const bd = choTrong(tl, trackId, t, dai);          // choTrong trả SỐ: giờ bắt đầu còn trống trên track
    const clip = taoClip(idClipMoi(tl), trackId, bd, dai);
    ops.push(tao.them(tl, ['clips'], clip));
    return { ops, clip };
}

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
            </div>`;
        this.el.querySelector('.nhom-nut-chu').addEventListener('click', (e) => {
            const b = e.target.closest('[data-l]');
            if (b) this.them(b.dataset.l === 'them-tieu-de');
        });
    }

    ve() {}

    them(laTieuDe) {
        const tl = this.ctx.store.timeline;
        const { ops, clip } = opsThemLopPhu(tl, this.ctx.ui.dau_phat || 0, 3,
            (id, tr, bd, dai) => clipChuMacDinh(id, tr, bd, dai, laTieuDe));
        if (this.ctx.sua('Thêm chữ', ops)) {
            this.ctx.timeline.chonClip(clip.id);
            this.ctx.timeline.datDauPhat(clip.bat_dau);
        }
    }
}
