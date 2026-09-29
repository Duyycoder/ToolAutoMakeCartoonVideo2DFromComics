/* Bảng thuộc tính (phải) theo thứ đang chọn:
 *  - clip video/âm thanh: tốc độ, âm lượng (+ thông tin clip & media nguồn)
 *  - câu phụ đề: chữ, bản gốc, giờ (neo theo video nào)
 *  - vùng che: kiểu, độ mạnh, màu, vùng (kéo lại trên xem trước)
 *  - chuyển cảnh (bấm ⧓ trên timeline): kiểu, thời lượng, xoá
 * Mọi thay đổi là lệnh hoàn tác được; kéo thanh trượt gộp thành một bước. */
import { $, esc, fmtThoiGian, coFile, toast } from './chung.js';
import { ketThucClip, tao, hienThiNeo, chongClip, idClipMoi, opsThemChuyenCanh, opsXoaChuyenCanh, giaTriTai } from './store.js';
import { KIEU_CHE } from './bang_che.js';
import { CAC_KIEU as KIEU_CC } from './bang_chuyen_canh.js';

const TAB = [['video', 'Video'], ['am_thanh', 'Âm thanh'], ['hieu_ung', 'Hiệu ứng']];
const TOC = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];

export class BangPhai {
    constructor(ctx) {
        this.ctx = ctx;
        this.el = $('bangPhai');
        this._dangSua = false;
        this.el.addEventListener('click', (e) => {
            const b = e.target.closest('[data-tab]');
            if (b) { ctx.ui.tab_thuoc_tinh = b.dataset.tab; ctx.luuUi(true); this.ve(); }
            const muc = e.target.closest('[data-muc]');
            if (muc) {
                const ds = new Set(ctx.ui.muc_thu_gon || []);
                if (ds.has(muc.dataset.muc)) ds.delete(muc.dataset.muc); else ds.add(muc.dataset.muc);
                ctx.ui.muc_thu_gon = [...ds];
                ctx.luuUi();
                this.ve();
            }
            const hd = e.target.closest('[data-hd]');
            if (hd && hd.dataset.hd === 'tach-am') this._tachAm();
            
            const l = e.target.closest('[data-l]');
            if (l && l.dataset.l === 've-lai-vung') this._veLaiVung();
            if (l && l.dataset.l === 'xoa-cc') ctx.timeline.xoaDangChon();
            if (l && l.dataset.l === 'mo-kieu') ctx.moBang('phu_de', true);
            
            const hu = e.target.closest('[data-hu]');
            if (hu) this._xuLyHieuUng(hu.dataset.hu, hu.dataset.idHu);
            
            const kfBtn = e.target.closest('[data-kf]');
            if (kfBtn) this._xuLyKF(kfBtn);
        });
        this.el.addEventListener('input', (e) => this._sua(e));
        this.el.addEventListener('change', (e) => { if (e.target.matches('select, [data-k=text]')) this._sua(e); });
        ['chon', 'timeline', 'media'].forEach((ev) => ctx.bus.on(ev, () => { 
            if (!this._dangSua && this.el.isConnected) {
                if (document.activeElement && this.el.contains(document.activeElement) && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
                this.ve(); 
            }
        }));
    }

    _xuLyHieuUng(hanhDong, idHu) {
        const c = this._clip();
        if (!c || !c.hieu_ung) return;
        let hu = [...c.hieu_ung];
        const idx = hu.findIndex(x => x.id === idHu);
        if (idx === -1) return;
        
        if (hanhDong === 'xoa') {
            hu.splice(idx, 1);
        } else if (hanhDong === 'len' && idx > 0) {
            [hu[idx - 1], hu[idx]] = [hu[idx], hu[idx - 1]];
        } else if (hanhDong === 'xuong' && idx < hu.length - 1) {
            [hu[idx + 1], hu[idx]] = [hu[idx], hu[idx + 1]];
        } else if (hanhDong === 'bat') {
            hu[idx] = { ...hu[idx], bat: !hu[idx].bat };
        }
        
        this.ctx.sua(`Đổi hiệu ứng`, [tao.dat(this.tl, ['clips', { id: c.id }, 'hieu_ung'], hu)]);
    }

    _tachAm() {
        const c = this._clip();
        if (!c) return;
        const ctx = this.ctx;
        let trA = this.tl.tracks.find(t => t.loai === 'audio');
        let ops = [];
        if (!trA) {
            trA = { id: 'A1', loai: 'audio' };
            ops.push(tao.them(this.tl, ['tracks'], trA));
        }
        ops.push(tao.dat(this.tl, ['clips', { id: c.id }, 'tat_am'], true));
        
        const am_clip = {
            id: idClipMoi(this.tl), track: trA.id, media: c.media, bat_dau: c.bat_dau, 
            vao: c.vao, ra: c.ra, toc_do: c.toc_do, am_luong: c.am_luong || 1,
            am_vao: c.am_vao || 0, am_ra: c.am_ra || 0
        };
        ops.push(tao.them(this.tl, ['clips'], am_clip));
        ctx.sua('Tách âm thanh', ops);
    }

    _nutKF(clip, duongDan) {
        if (!clip) return '';
        const t = this.ctx.ui.dau_phat - (clip.bat_dau || 0);
        const kf = (clip.keyframes || {})[duongDan] || [];
        const coKFNay = kf.some(k => Math.abs(k.t - t) < 1e-4);
        const coBatKy = kf.length > 0;
        
        let html = `<div class="kf-nhom" data-dd="${duongDan}" style="display:inline-flex;align-items:center;gap:2px;margin-left:4px;vertical-align:middle;">`;
        
        const kfTruoc = [...kf].reverse().find(k => k.t < t - 1e-4);
        html += `<button class="nut-icon nut-nho" data-kf="truoc" ${kfTruoc ? '' : 'disabled'} title="Keyframe trước" style="font-size:10px;padding:2px;width:16px;height:16px;opacity:0.7;">◀</button>`;
        
        if (coKFNay) {
            html += `<button class="nut-icon nut-nho" data-kf="xoa" title="Xóa keyframe này" style="font-size:10px;padding:2px;width:16px;height:16px;opacity:1;color:var(--xanh);">◆</button>`;
        } else {
            html += `<button class="nut-icon nut-nho" data-kf="them" title="${coBatKy ? 'Thêm keyframe' : 'Bật keyframe'}" style="font-size:10px;padding:2px;width:16px;height:16px;opacity:0.7;${coBatKy ? 'color:var(--xanh);' : ''}">◇</button>`;
        }
        
        const kfSau = kf.find(k => k.t > t + 1e-4);
        html += `<button class="nut-icon nut-nho" data-kf="sau" ${kfSau ? '' : 'disabled'} title="Keyframe tiếp" style="font-size:10px;padding:2px;width:16px;height:16px;opacity:0.7;">▶</button>`;
        
        html += `</div>`;
        return html;
    }

    _xuLyKF(btn) {
        const c = this._clip();
        if (!c) return;
        const nhom = btn.closest('.kf-nhom');
        if (!nhom) return;
        const dd = nhom.dataset.dd;
        const hanhDong = btn.dataset.kf;
        
        const tCucBo = this.ctx.ui.dau_phat - (c.bat_dau || 0);
        let kfs = (c.keyframes || {})[dd] || [];
        
        if (hanhDong === 'truoc') {
            const kf = [...kfs].reverse().find(k => k.t < tCucBo - 1e-4);
            if (kf) this.ctx.timeline.datDauPhat((c.bat_dau || 0) + kf.t);
            return;
        }
        if (hanhDong === 'sau') {
            const kf = kfs.find(k => k.t > tCucBo + 1e-4);
            if (kf) this.ctx.timeline.datDauPhat((c.bat_dau || 0) + kf.t);
            return;
        }
        
        let moi = [...kfs];
        if (hanhDong === 'xoa') {
            moi = moi.filter(k => Math.abs(k.t - tCucBo) >= 1e-4);
        } else if (hanhDong === 'them') {
            const val = giaTriTai(c, dd, tCucBo) ?? 0;
            moi.push({ t: tCucBo, v: val, em: 'tuyen_tinh' });
            moi.sort((a, b) => a.t - b.t);
        }
        
        this.ctx.sua(`Keyframe ${dd}`, [tao.dat(this.tl, ['clips', { id: c.id }, 'keyframes', dd], moi)]);
    }

    get tl() { return this.ctx.store.timeline; }

    _clip() {
        const cid = this.ctx.chon.clip;
        return cid ? this.tl.clips.find((c) => c.id === cid) : null;
    }

    /* Chuyển cảnh đang chọn (chỉ khi không chọn clip nào). */
    _chuyenCanh() {
        if (this._clip()) return null;
        return (this.tl.chuyen_canh || []).find((x) => x.id === this.ctx.ui.chuyen_canh_chon) || null;
    }

    /* Thời lượng tối đa = nửa clip ngắn hơn trong hai clip (khớp `chuyenCanhHopLe`). */
    _daiToiDaCC(cc) {
        const dai = (id) => { const c = this.tl.clips.find((x) => x.id === id); return c ? ketThucClip(c) - Number(c.bat_dau || 0) : 0; };
        return Math.max(0.1, Math.floor(Math.min(dai(cc.truoc), dai(cc.sau)) / 2 * 20) / 20);
    }

    _suaCC(o, cc) {
        const k = o.dataset.cck;
        const loai = k === 'loai' ? o.value : cc.loai;
        const dai = k === 'dai' ? Number(o.value) : Number(cc.dai);
        this._dangSua = true;
        this.ctx.sua(k === 'dai' ? 'Thời lượng chuyển cảnh' : 'Kiểu chuyển cảnh',
            opsThemChuyenCanh(this.tl, cc.truoc, cc.sau, loai, dai), { gop: `cc:${cc.id}:${k}` });
        this._dangSua = false;
        const gt = o.closest('label') && o.closest('label').querySelector('.gt');
        if (gt) gt.textContent = `${dai.toFixed(2)} s`;
    }

    _sua(e) {
        const occ = e.target.closest('[data-cck]');
        const cc = occ && this._chuyenCanh();
        if (cc) { this._suaCC(occ, cc); return; }
        const o = e.target.closest('[data-k]');
        const c = this._clip();
        if (!o || !c) return;
        const k = o.dataset.k;
        let v = o.type === 'range' || o.type === 'number' || o.tagName === 'SELECT' && o.dataset.so ? Number(o.value) : o.value;
        const p = (...x) => ['clips', { id: c.id }, ...x];
        let ops;
        if (k === 'toc_do') {
            const kt = Number(c.bat_dau) + (Number(c.ra) - Number(c.vao)) / v;
            if (chongClip(this.tl, c.track, Number(c.bat_dau), kt, [c.id])) {
                toast('Chậm lại thì clip dài ra và đè clip sau — dời clip sau hoặc tỉa bớt trước.', 'warn');
                o.value = c.toc_do || 1;
                return;
            }
            ops = [tao.dat(this.tl, p('toc_do'), v)];
        } else if (k.startsWith('hieu_ung.')) {
            const [, iStr, truong] = k.split('.');
            const i = parseInt(iStr);
            let hu = [...(c.hieu_ung || [])];
            hu[i] = { ...hu[i], [truong]: Number(o.value) };
            ops = [tao.dat(this.tl, p('hieu_ung'), hu)];
        } else if (k.includes('.')) {
            const [nhom, truong] = k.split('.');
            let val = truong === 'hoa_tron' ? o.value : Number(o.value);
            if (nhom === 'bien_doi' && truong !== 'xoay') val /= 100;
            if (nhom === 'cat_khung') val /= 100;
            if (nhom === 'vung') val /= 100;
            if (nhom === 'hien_thi' && truong === 'do_mo') val /= 100;
            
            const tCucBo = this.ctx.ui.dau_phat - (c.bat_dau || 0);
            const kfs = (c.keyframes || {})[k] || [];
            if (kfs.length > 0 || kfs.some(kf => Math.abs(kf.t - tCucBo) < 1e-4)) {
                let moi = [...kfs];
                const idx = moi.findIndex(kf => Math.abs(kf.t - tCucBo) < 1e-4);
                if (idx >= 0) moi[idx] = { ...moi[idx], v: val };
                else moi.push({ t: tCucBo, v: val, em: 'tuyen_tinh' });
                moi.sort((a, b) => a.t - b.t);
                ops = [tao.dat(this.tl, p('keyframes', k), moi)];
            } else {
                const obj = { ...(c[nhom] || {}), [truong]: val };
                if (truong === 'hoa_tron' && val === 'normal') delete obj[truong];
                ops = [tao.dat(this.tl, p(nhom), obj)];
            }
        } else {
            const tCucBo = this.ctx.ui.dau_phat - (c.bat_dau || 0);
            const kfs = (c.keyframes || {})[k] || [];
            if (kfs.length > 0 || kfs.some(kf => Math.abs(kf.t - tCucBo) < 1e-4)) {
                let moi = [...kfs];
                const idx = moi.findIndex(kf => Math.abs(kf.t - tCucBo) < 1e-4);
                if (idx >= 0) moi[idx] = { ...moi[idx], v };
                else moi.push({ t: tCucBo, v, em: 'tuyen_tinh' });
                moi.sort((a, b) => a.t - b.t);
                ops = [tao.dat(this.tl, p('keyframes', k), moi)];
            } else {
                ops = [tao.dat(this.tl, p(k), v)];
            }
        }
        this._dangSua = true;
        this.ctx.sua(TEN_SUA[k] || 'Sửa thuộc tính', ops, { gop: `tt:${c.id}:${k}` });
        this._dangSua = false;
        const gt = o.closest('label') && o.closest('label').querySelector('.gt');
        if (gt) gt.textContent = k === 'am_luong' ? `${Math.round(v * 100)}%` : o.value;
    }

    async _veLaiVung() {
        const c = this._clip();
        if (!c) return;
        const k = hienThiNeo(this.tl, c)[0];
        if (k && (this.ctx.ui.dau_phat < k.bd || this.ctx.ui.dau_phat >= k.kt)) {
            this.ctx.timeline.datDauPhat(k.bd + 0.05);
            await new Promise((r) => setTimeout(r, 300));
        }
        const vung = await this.ctx.preview.veVung('Kéo khung vùng cần che', c.tu_media);
        if (vung) this.ctx.sua('Đặt lại vùng che', [tao.dat(this.tl, ['clips', { id: c.id }, 'vung'], vung)]);
    }

    _muc(khoa, tieuDe, noi) {
        const gon = (this.ctx.ui.muc_thu_gon || []).includes(khoa);
        return `<div class="muc"><div class="muc-dau" data-muc="${khoa}"><span>${esc(tieuDe)}</span><span>${gon ? '▸' : '▾'}</span></div>
            ${gon ? '' : noi}</div>`;
    }

    _bang(dong) {
        return `<div class="dong-tt">${dong.filter(([, v]) => v !== '' && v != null)
            .map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join('')}</div>`;
    }

    ve() {
        const ctx = this.ctx;
        const clip = this._clip();
        const m = ctx.media.find((x) => x.id === (clip ? (clip.media || clip.tu_media) : ctx.chon.media));
        const fps = Number((ctx.du.thong_so || {}).fps) || 30;
        let tieuDe = 'Thuộc tính', noi = '';
        const cc = this._chuyenCanh();
        if (cc) {
            tieuDe = 'Chuyển cảnh';
            const ten = (id) => { const c = this.tl.clips.find((x) => x.id === id); const mm = c && ctx.media.find((x) => x.id === c.media); return mm ? mm.ten : id; };
            const toiDa = this._daiToiDaCC(cc);
            const co = KIEU_CC.some((x) => x.id === cc.loai) ? KIEU_CC : [...KIEU_CC, { id: cc.loai, ten: cc.loai }];
            noi = `<div class="bang-noi o-form" style="padding-top:4px">
                <label>Kiểu<select data-cck="loai">${co.map((x) => `<option value="${esc(x.id)}" ${x.id === cc.loai ? 'selected' : ''}>${esc(x.ten)}</option>`).join('')}</select></label>
                <label>Thời lượng <span class="gt">${Number(cc.dai).toFixed(2)} s</span>
                    <input type="range" data-cck="dai" min="0.1" max="${toiDa}" step="0.05" value="${Math.min(Number(cc.dai), toiDa)}"></label>
                ${this._bang([['Giữa', `${esc(ten(cc.truoc))} → ${esc(ten(cc.sau))}`], ['Tối đa', `${toiDa.toFixed(2)} s (nửa clip ngắn hơn)`]])}
                <button class="nut nut-nho" data-l="xoa-cc">✕ Xoá chuyển cảnh (Delete)</button>
                <div class="goi-y-nho">Chuyển cảnh nằm giữa điểm nối: ăn nửa thời lượng vào cuối clip trước và nửa vào đầu clip sau, tổng độ dài video không đổi.</div></div>`;
        } else if (clip && clip.loai === 'phu_de') {
            tieuDe = 'Câu phụ đề';
            const k = hienThiNeo(this.tl, clip)[0];
            noi = `<div class="bang-noi o-form" style="padding-top:4px">
                <label>Nội dung<textarea data-k="text" rows="3">${esc(clip.text || '')}</textarea></label>
                ${clip.text_goc && clip.text_goc !== clip.text ? `<div class="goc-pd">Bản gốc: ${esc(clip.text_goc)}</div>` : ''}
                ${this._bang([['Hiện', k ? `${fmtThoiGian(k.bd, true, fps)} → ${fmtThoiGian(k.kt, true, fps)}` : 'ngoài đoạn video trên timeline'],
                    ['Neo theo', clip.tu_media ? `${(m || {}).ten || clip.tu_media} (${clip.t_vao}s → ${clip.t_ra}s trong video)` : 'giờ tuyệt đối']])}
                <button class="nut nut-nho" data-l="mo-kieu">Kiểu chữ (phông, cỡ, màu, vị trí)…</button></div>`;
        } else if (clip && clip.loai === 'che_phu_de') {
            tieuDe = 'Vùng che phụ đề';
            const v = clip.vung || {};
            const pc = (x) => Math.round((x || 0) * 100);
            noi = `<div class="bang-noi o-form" style="padding-top:4px">
                <label>Kiểu che<select data-k="kieu">${Object.entries(KIEU_CHE).map(([kk, t]) => `<option value="${kk}" ${kk === (clip.kieu || 'blur') ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
                ${clip.kieu === 'mau' ? `<label>Màu<input type="color" data-k="mau" value="${esc(clip.mau || '#000000')}"></label>`
                    : `<label>Độ mạnh <span class="gt">${clip.do_manh ?? 20}</span><input type="range" data-k="do_manh" min="2" max="60" value="${clip.do_manh ?? 20}"></label>`}
                <div class="hang"><label>X %<input type="number" data-k="vung.x" min="0" max="100" value="${pc(v.x)}"></label>
                    <label>Y %<input type="number" data-k="vung.y" min="0" max="100" value="${pc(v.y)}"></label></div>
                <div class="hang"><label>Rộng %<input type="number" data-k="vung.w" min="1" max="100" value="${pc(v.w)}"></label>
                    <label>Cao %<input type="number" data-k="vung.h" min="1" max="100" value="${pc(v.h)}"></label></div>
                <button class="nut nut-nho" data-l="ve-lai-vung">▭ Kéo lại vùng trên xem trước</button>
                <div class="goi-y-nho">Kéo thân vùng che trên khung xem trước để dời, góc dưới-phải để đổi cỡ. Xem trước là gần đúng — bản xuất dùng ffmpeg.</div></div>`;
        } else if (clip && clip.loai === 'chu') {
            tieuDe = 'Thuộc tính Chữ';
            const k = clip.kieu || {};
            noi = `<div class="bang-noi o-form" style="padding-top:4px">
                <label>Nội dung<textarea data-k="noi_dung" rows="3">${esc(clip.noi_dung || '')}</textarea></label>
                <div class="hang">
                    <label>Font<input type="text" data-k="kieu.font" value="${esc(k.font || 'Arial')}"></label>
                    <label>Cỡ chữ<input type="number" data-k="kieu.co" value="${k.co || 48}"></label>
                </div>
                <div class="hang">
                    <label>Màu chữ<input type="color" data-k="kieu.mau" value="${esc(k.mau || '#ffffff')}"></label>
                    <label>Độ mờ <span class="gt">${(clip.hien_thi?.do_mo ?? 1).toFixed(2)}</span><input type="range" data-k="hien_thi.do_mo" min="0" max="1" step="0.05" value="${clip.hien_thi?.do_mo ?? 1}"></label>
                </div>
                <div class="hang">
                    <label>Viền màu<input type="color" data-k="kieu.vien_mau" value="${esc(k.vien_mau || '#000000')}"></label>
                    <label>Viền dày<input type="number" data-k="kieu.vien_day" value="${k.vien_day || 0}"></label>
                </div>
                <div class="hang">
                    <label>Vào
                        <select data-k="hieu_ung_vao">
                            <option value="" ${!clip.hieu_ung_vao ? 'selected' : ''}>Không</option>
                            <option value="mo_dan" ${clip.hieu_ung_vao === 'mo_dan' ? 'selected' : ''}>Mờ dần</option>
                            <option value="truot_len" ${clip.hieu_ung_vao === 'truot_len' ? 'selected' : ''}>Trượt lên</option>
                            <option value="danh_may" ${clip.hieu_ung_vao === 'danh_may' ? 'selected' : ''}>Đánh máy</option>
                        </select>
                    </label>
                    <label>Ra
                        <select data-k="hieu_ung_ra">
                            <option value="" ${!clip.hieu_ung_ra ? 'selected' : ''}>Không</option>
                            <option value="mo_dan" ${clip.hieu_ung_ra === 'mo_dan' ? 'selected' : ''}>Mờ dần</option>
                        </select>
                    </label>
                </div>
            </div>`;
        } else if (clip && clip.loai === 'hinh') {
            tieuDe = 'Thuộc tính Hình dạng';
            const bd = clip.bien_doi || {};
            const pc = (x) => Math.round((x || 0) * 100);
            noi = `<div class="bang-noi o-form" style="padding-top:4px">
                <div class="hang">
                    <label>Màu<input type="color" data-k="mau" value="${esc(clip.mau || '#ffffff')}"></label>
                    <label>Độ mờ <span class="gt">${(clip.do_mo ?? 1).toFixed(2)}</span><input type="range" data-k="do_mo" min="0" max="1" step="0.05" value="${clip.do_mo ?? 1}"></label>
                </div>
                <div class="hang">
                    <label>Viền màu<input type="color" data-k="vien_mau" value="${esc(clip.vien_mau || '#000000')}"></label>
                    <label>Viền dày<input type="number" data-k="vien_day" value="${clip.vien_day || 0}"></label>
                </div>
                ${clip.dang === 'da_giac' ? `<label>Số cạnh<input type="number" data-k="so_canh" min="3" max="20" value="${clip.so_canh || 5}"></label>` : ''}
                <div class="hang">
                    <label>Rộng %<input type="number" data-k="bien_doi.rong" min="1" max="100" value="${pc(bd.rong ?? 0.2)}"></label>
                    <label>Cao %<input type="number" data-k="bien_doi.cao" min="1" max="100" value="${pc(bd.cao ?? 0.2)}"></label>
                </div>
            </div>`;
        } else if (clip) {
            tieuDe = `Thuộc tính – ${m ? m.ten : clip.id}`;
            const tab = ctx.ui.tab_thuoc_tinh || 'video';
            const tr = this.tl.tracks.find((x) => x.id === clip.track) || {};
            let than = '';
            if (tab === 'video') {
                const bd = clip.bien_doi || {};
                const ck = clip.cat_khung || {};
                const ht = clip.hien_thi || {};
                const pc = (x) => Math.round((x || 0) * 100);
                const tCucBo = this.ctx.ui.dau_phat - (clip.bat_dau || 0);
                const val = (k, fb) => giaTriTai(clip, k, tCucBo) ?? fb;
                
                than = this._muc('clip', 'Clip', this._bang([
                    ['Track', clip.track], ['Bắt đầu', fmtThoiGian(clip.bat_dau, true, fps)],
                    ['Kết thúc', fmtThoiGian(ketThucClip(clip), true, fps)],
                    ['Đoạn trong media', `${fmtThoiGian(clip.vao, true, fps)} → ${fmtThoiGian(clip.ra, true, fps)}`],
                ]) + `<div class="o-form" style="margin-top:8px"><label>Tốc độ<select data-k="toc_do" data-so="1">${TOC.map((x) => `<option value="${x}" ${Number(clip.toc_do || 1) === x ? 'selected' : ''}>${x}×</option>`).join('')}</select></label></div>`)
                    + this._muc('bien_doi', 'Biến đổi', `<div class="o-form">
                        <div class="hang"><label>X % ${this._nutKF(clip, 'bien_doi.x')}<input type="number" data-k="bien_doi.x" step="1" value="${pc(val('bien_doi.x', bd.x ?? 0.5))}"></label>
                            <label>Y % ${this._nutKF(clip, 'bien_doi.y')}<input type="number" data-k="bien_doi.y" step="1" value="${pc(val('bien_doi.y', bd.y ?? 0.5))}"></label></div>
                        <div class="hang"><label>Tỉ lệ % ${this._nutKF(clip, 'bien_doi.ti_le')}<input type="number" data-k="bien_doi.ti_le" step="1" value="${pc(val('bien_doi.ti_le', bd.ti_le ?? 1))}"></label>
                            <label>Xoay ° ${this._nutKF(clip, 'bien_doi.xoay')}<input type="number" data-k="bien_doi.xoay" step="1" value="${val('bien_doi.xoay', bd.xoay ?? 0)}"></label></div>
                    </div>`)
                    + this._muc('cat_khung', 'Cắt khung', `<div class="o-form">
                        <div class="hang"><label>Trái %<input type="number" data-k="cat_khung.trai" min="0" max="100" value="${pc(ck.trai)}"></label>
                            <label>Phải %<input type="number" data-k="cat_khung.phai" min="0" max="100" value="${pc(ck.phai)}"></label></div>
                        <div class="hang"><label>Trên %<input type="number" data-k="cat_khung.tren" min="0" max="100" value="${pc(ck.tren)}"></label>
                            <label>Dưới %<input type="number" data-k="cat_khung.duoi" min="0" max="100" value="${pc(ck.duoi)}"></label></div>
                    </div>`)
                    + this._muc('hien_thi', 'Hiển thị', `<div class="o-form">
                        <label>Độ mờ <span class="gt">${pc(val('hien_thi.do_mo', ht.do_mo ?? 1))}%</span> ${this._nutKF(clip, 'hien_thi.do_mo')}<input type="range" data-k="hien_thi.do_mo" min="0" max="100" value="${pc(val('hien_thi.do_mo', ht.do_mo ?? 1))}"></label>
                        <label>Bo góc <span class="gt">${ht.bo_goc ?? 0}</span><input type="range" data-k="hien_thi.bo_goc" min="0" max="100" value="${ht.bo_goc ?? 0}"></label>
                        <label>Hoà trộn<select data-k="hien_thi.hoa_tron">
                            <option value="normal" ${!ht.hoa_tron || ht.hoa_tron === 'normal' ? 'selected' : ''}>Bình thường</option>
                            <option value="multiply" ${ht.hoa_tron === 'multiply' ? 'selected' : ''}>Multiply</option>
                            <option value="screen" ${ht.hoa_tron === 'screen' ? 'selected' : ''}>Screen</option>
                            <option value="overlay" ${ht.hoa_tron === 'overlay' ? 'selected' : ''}>Overlay</option>
                            <option value="darken" ${ht.hoa_tron === 'darken' ? 'selected' : ''}>Darken</option>
                            <option value="lighten" ${ht.hoa_tron === 'lighten' ? 'selected' : ''}>Lighten</option>
                        </select></label>
                    </div>`);
            } else if (tab === 'am_thanh') {
                const pc = (x) => Math.round((x || 0) * 100);
                const tCucBo = this.ctx.ui.dau_phat - (clip.bat_dau || 0);
                const val = (k, fb) => giaTriTai(clip, k, tCucBo) ?? fb;
                
                than = `<div class="o-form">${tr.loai === 'video' && m && m.co_am_thanh === false ? '<div class="goi-y-nho">Video này không có tiếng.</div>' : ''}
                    <label>Âm lượng <span class="gt">${Math.round(Number(val('am_luong', clip.am_luong ?? 1)) * 100)}%</span> ${this._nutKF(clip, 'am_luong')}
                        <input type="range" data-k="am_luong" min="0" max="2" step="0.05" value="${val('am_luong', clip.am_luong ?? 1)}"></label>
                    ${clip.long_tieng_cho ? '<div class="goi-y-nho">Clip giọng lồng tiếng — lúc xuất, nhạc nền của video tự giảm khi có lời.</div>' : ''}
                    <div class="hang">
                        <label>Fade vào (s)<input type="number" data-k="am_vao" min="0" step="0.1" value="${clip.am_vao ?? 0}"></label>
                        <label>Fade ra (s)<input type="number" data-k="am_ra" min="0" step="0.1" value="${clip.am_ra ?? 0}"></label>
                    </div>
                    ${tr.loai === 'video' && m && m.co_am_thanh !== false ? `<div style="margin-top:8px"><button class="nut nut-nho" data-hd="tach-am">↧ Tách âm thanh</button></div>` : ''}
                    <div class="sap-co">Giảm ồn, đổi giọng — GĐ 3.</div></div>`;
            } else if (tab === 'hieu_ung') {
                const hu = clip.hieu_ung || [];
                if (!hu.length) {
                    than = '<div class="goi-y-nho">Chưa có hiệu ứng nào. Hãy thêm từ bảng Hiệu ứng (◈) bên trái.</div>';
                } else {
                    than = '<div class="o-form">' + hu.map((h, i) => {
                        return `<div class="muc-hieu-ung" style="border: 1px solid var(--vien); border-radius: 4px; padding: 6px; margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                <b style="font-size: 13px; opacity: ${h.bat === false ? 0.5 : 1}">${esc(h.loai)}</b>
                                <div style="display: flex; gap: 4px;">
                                    <button class="nut-icon nut-nho" data-hu="bat" data-id-hu="${h.id}" title="Bật/tắt">${h.bat === false ? '👁‍🗨' : '👁'}</button>
                                    <button class="nut-icon nut-nho" data-hu="len" data-id-hu="${h.id}" ${i === 0 ? 'disabled' : ''} title="Đưa lên">↑</button>
                                    <button class="nut-icon nut-nho" data-hu="xuong" data-id-hu="${h.id}" ${i === hu.length - 1 ? 'disabled' : ''} title="Đưa xuống">↓</button>
                                    <button class="nut-icon nut-nho" data-hu="xoa" data-id-hu="${h.id}" style="color: #ff4444" title="Xoá">✕</button>
                                </div>
                            </div>
                            ${['vintage', 'noir', 'cold', 'warm', 'dramatic', 'faded', 'sepia', 'grayscale', 'invert', 'mo_hop', 'mo_gauss', 'mosaic'].includes(h.loai) ? `
                            <div style="display: flex; align-items: center; gap: 8px; opacity: ${h.bat === false ? 0.5 : 1}; pointer-events: ${h.bat === false ? 'none' : 'auto'}">
                                <span style="font-size: 11px">Độ mạnh</span>
                                <input type="range" style="flex: 1" data-k="hieu_ung.${i}.do_manh" min="0" max="100" value="${h.do_manh !== undefined ? h.do_manh : 100}">
                                <span style="width: 2em; text-align: right; font-size: 11px" class="gt">${h.do_manh !== undefined ? h.do_manh : 100}</span>
                            </div>` : ''}
                        </div>`;
                    }).join('') + '</div>';
                }
            }
            noi = `<div class="tab-thuoc-tinh">${TAB.map(([k, t]) => `<button data-tab="${k}" class="${k === tab ? 'bat' : ''}">${t}</button>`).join('')}</div>
                <div class="bang-noi" style="padding-top:4px">${than}
                ${m ? this._muc('media', 'Media nguồn', this._bang(this._dongMedia(m))) : ''}</div>`;
        } else if (m) {
            tieuDe = `Media – ${m.ten}`;
            noi = `<div class="bang-noi" style="padding-top:4px">${this._muc('media', 'Thông tin', this._bang(this._dongMedia(m)))}</div>`;
        } else {
            noi = `<div class="bang-noi"><div class="sap-co">Chọn một clip, câu phụ đề hoặc vùng che trên timeline để xem và chỉnh thuộc tính.</div>
                ${this._muc('du_an', 'Dự án', this._bang(this._dongDuAn()))}</div>`;
        }
        this.el.innerHTML = `<div class="bang-dau"><h2 style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(tieuDe)}</h2></div>${noi}`;
    }

    _dongMedia(m) {
        return [
            ['File', m.file], ['Loại', m.loai], ['Thời lượng', m.thoi_luong ? fmtThoiGian(m.thoi_luong) : ''],
            ['Khung hình', m.rong ? `${m.rong}×${m.cao}` : ''], ['FPS', m.fps || ''],
            ['Codec', [m.codec, m.codec_am].filter(Boolean).join(' / ')], ['Dung lượng', m.kich_thuoc ? coFile(m.kich_thuoc) : ''],
            ['Xem trước', m.proxy === 'xong' ? 'bản nhẹ (proxy) — xuất vẫn dùng file gốc' : m.proxy === 'dang_tao' ? 'đang tạo proxy…'
                : m.phat_duoc === true ? 'phát trực tiếp' : ''],
            ['Nguồn', m.url || m.nguon || ''], ['Nhập lúc', (m.nhap_luc || '').replace('T', ' ')],
        ];
    }

    _dongDuAn() {
        const du = this.ctx.du, ts = du.thong_so || {};
        return [['Tên', du.name], ['Khung hình', ts.rong ? `${ts.rong}×${ts.cao} (${ts.ti_le || ''})` : ''],
            ['FPS', ts.fps], ['Thư mục', du.folder], ['Mô tả', du.mo_ta || '']];
    }
}

const TEN_SUA = { text: 'Sửa phụ đề', kieu: 'Đổi kiểu che', do_manh: 'Độ mạnh vùng che', mau: 'Màu vùng che',
    am_luong: 'Âm lượng clip', toc_do: 'Tốc độ clip' };
