/* ⬠ Bảng Hình dạng & Che phụ đề. GĐ 1a: vùng che (mờ / mosaic / delogo / màu đặc) NEO theo
 * video nguồn — kéo vùng trên xem trước, chỉnh ở bảng Thuộc tính. Hình dạng trang trí: GĐ 3. */
import { esc, toast } from './chung.js';
import { tao, idClipMoi, clipTai, thoiDiemMedia, hienThiNeo, clipHinhMacDinh } from './store.js';
import { opsThemLopPhu } from './bang_chu.js';

const KIEU = { blur: 'Làm mờ', mosaic: 'Mosaic (ô vuông)', delogo: 'Xoá logo (delogo)', mau: 'Màu đặc' };

export class BangChe {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>Hình dạng &amp; Che phụ đề</h2></div><div class="bang-noi" data-khu="noi"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        this.noi.addEventListener('click', (e) => {
            const b = e.target.closest('[data-l]');
            if (b && b.dataset.l === 'them') this.them();
            if (b && b.dataset.l === 'them-hinh') this.themHinh(b.dataset.dang);
            const d = e.target.closest('.dong-che');
            if (d && !b) {
                const bd = Number(d.dataset.bd);
                if (!Number.isNaN(bd)) this.ctx.timeline.datDauPhat(bd + 0.01);
                this.ctx.timeline.chonClip(d.dataset.id);
            }
        });
        ctx.bus.on('timeline', () => { if (this.el.isConnected) this.ve(); });
    }

    get tl() { return this.ctx.store.timeline; }

    async them() {
        const t = this.ctx.ui.dau_phat;
        const v = this.tl.tracks.filter((x) => x.loai === 'video').map((x) => clipTai(this.tl, x.id, t)).find((c) => c && c.media);
        if (!v) { toast('Đưa đầu phát vào một clip video trước — vùng che neo theo video đó.', 'warn'); return; }
        const trO = this.tl.tracks.find((x) => x.loai === 'lop_phu');
        const id = idClipMoi(this.tl);
        const clip = { id, track: trO.id, loai: 'che_phu_de', tu_media: v.media,
            t_vao: Math.round(thoiDiemMedia(v, t) * 1000) / 1000, t_ra: Number(v.ra),
            vung: { x: 0.08, y: 0.8, w: 0.84, h: 0.12 }, kieu: 'blur', do_manh: 20, mau: '#000000' };
        if (this.ctx.sua('Thêm vùng che phụ đề', [tao.them(this.tl, ['clips'], clip)])) {
            this.ctx.timeline.chonClip(id);
            toast('Kéo vùng che trên khung xem trước để dời, kéo góc dưới-phải để đổi cỡ.', 'info', 4000);
        }
    }

    themHinh(dang) {
        const { ops, clip } = opsThemLopPhu(this.tl, this.ctx.ui.dau_phat || 0, 3, (id, tr, bd, dai) => {
            const c = clipHinhMacDinh(id, tr, bd, dai, dang);
            if (dang === 'da_giac') c.so_canh = 5;
            return c;
        });
        if (this.ctx.sua('Thêm hình dạng', ops)) {
            this.ctx.timeline.chonClip(clip.id);
            this.ctx.timeline.datDauPhat(clip.bat_dau);
        }
    }

    ve() {
        const ds = this.tl.clips.filter((c) => c.loai === 'che_phu_de');
        const chon = new Set(this.ctx.ui.dang_chon || []);
        const media = Object.fromEntries(this.ctx.media.map((m) => [m.id, m]));
        this.noi.innerHTML = `
            <div class="sap-co" style="margin-bottom:10px">Che sub cứng gốc (chữ Trung, logo…) để phụ đề mới không đè lên.
                Tạo tự động khi nhận diện OCR, hoặc thêm tay:</div>
            <button class="nut nut-chinh" data-l="them" style="width:100%;justify-content:center">＋ Vùng che tại đầu phát</button>
            <div style="margin-top:12px">${ds.map((c) => {
                const k = hienThiNeo(this.tl, c)[0];
                return `<div class="dong-che ${chon.has(c.id) ? 'chon' : ''}" data-id="${esc(c.id)}" data-bd="${k ? k.bd : ''}">
                    <b>▦ ${esc(KIEU[c.kieu] || c.kieu)}</b>
                    <span class="goi-y-nho">${esc((media[c.tu_media] || {}).ten || 'video?')} · ${k ? `${k.bd.toFixed(1)}s → ${k.kt.toFixed(1)}s` : 'ngoài timeline'}</span></div>`;
            }).join('')}</div>
            <div class="sap-co" style="margin-top:14px"><b>Hình dạng trang trí</b></div>
            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:8px">
                <button class="nut" data-l="them-hinh" data-dang="chu_nhat">Chữ nhật</button>
                <button class="nut" data-l="them-hinh" data-dang="tron">Tròn</button>
                <button class="nut" data-l="them-hinh" data-dang="elip">Elip</button>
                <button class="nut" data-l="them-hinh" data-dang="sao">Sao</button>
                <button class="nut" data-l="them-hinh" data-dang="da_giac">Đa giác</button>
                <button class="nut" data-l="them-hinh" data-dang="tim">Tim</button>
                <button class="nut" data-l="them-hinh" data-dang="mui_ten">Mũi tên</button>
            </div>`;
    }
}

export { KIEU as KIEU_CHE };
