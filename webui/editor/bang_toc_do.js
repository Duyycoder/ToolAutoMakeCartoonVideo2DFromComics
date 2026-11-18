/* Mục "Tốc độ" của bảng thuộc tính clip (bang_phai.js):
 *  - Thường: thanh trượt 0.1×–10× (thang log) + ô số + vài mốc nhanh.
 *  - Đồ thị: mẫu có sẵn (toc_do_cong.js MAU_DO_THI) + đồ thị kéo điểm (trục ngang = vị trí trên clip,
 *    trục đứng = tốc độ thang log). Bấm đúp vào đường để thêm điểm, bấm đúp vào điểm để xoá.
 * Mỗi lần kéo/gõ là một lệnh hoàn tác (gộp theo clip). Chậm lại mà đè clip sau thì không nhận. */
import { esc, toast } from './chung.js';
import { tao, chongClip, opsDatTocDo } from './store.js';
import { MAU_DO_THI, TOC_MIN, TOC_MAX, chuan, tuMau, tocTai, tocTrungBinh } from './toc_do_cong.js';

const H = 140;                                    // cao vùng vẽ (px)
const LE_TRAI = 34;                               // chỗ cho nhãn trục tốc độ
const LO = Math.log10(TOC_MIN), HI = Math.log10(TOC_MAX);
const LUOI = [0.1, 0.25, 0.5, 1, 2, 4, 10];
const MOC = [0.25, 0.5, 1, 1.5, 2, 4];
const yCua = (v) => 10 + (H - 20) * (1 - (Math.log10(v) - LO) / (HI - LO));
const vCua = (y) => 10 ** (LO + (1 - (y - 10) / (H - 20)) * (HI - LO));
const kep = (x, a, b) => Math.min(b, Math.max(a, x));
const tron2 = (v) => Math.round(v * 100) / 100;
const fmtX = (v) => `${tron2(v)}×`;
const fmtS = (s) => `${s.toFixed(2)} s`;
const dai = (c, toc) => (Number(c.ra || 0) - Number(c.vao || 0)) / toc;

let chonDiem = { clip: null, i: -1 };
let lan = 0;          // mỗi thao tác (một lần kéo / bấm / gõ) là một bước hoàn tác riêng

export function htmlTocDo(ctx, c) {
    const cong = chuan(c.toc_do_cong);
    const doThi = !!cong || ctx.ui.che_do_toc === 'do_thi';
    const toc = Number(c.toc_do) || 1;
    const tab = (id, ten) => `<button type="button" class="nut nut-nho ${(id === 'do_thi') === doThi ? 'dang' : ''}" data-toc-tab="${id}">${ten}</button>`;
    let than;
    if (!doThi) {
        than = `<div class="toc-hang">
                <input type="range" data-toc="truot" min="${LO}" max="${HI}" step="0.005" value="${Math.log10(toc)}">
                <input type="number" data-toc="so" min="${TOC_MIN}" max="${TOC_MAX}" step="0.05" value="${tron2(toc)}"><span>×</span>
            </div>
            <div class="toc-chip">${MOC.map((v) => `<button type="button" class="nut nut-nho ${Math.abs(v - toc) < 1e-6 ? 'dang' : ''}" data-toc-moc="${v}">${v}×</button>`).join('')}</div>`;
    } else {
        than = `<div class="toc-chip">
                <button type="button" class="nut nut-nho" data-toc-mau="">Không</button>
                <button type="button" class="nut nut-nho" data-toc-mau="tu_ve">Tự vẽ</button>
                ${MAU_DO_THI.map((m) => `<button type="button" class="nut nut-nho" data-toc-mau="${m.id}">${esc(m.ten)}</button>`).join('')}
            </div>`
            + (cong ? `<svg class="toc-svg" height="${H}"></svg>
            <div class="toc-hang toc-diem"></div>
            <div class="goi-y-kf">Kéo điểm lên/xuống để đổi tốc độ, sang ngang để dời. Bấm đúp vào đường để thêm điểm,
                bấm đúp vào điểm để xoá. Đồ thị co giãn theo clip khi tỉa.</div>` : '<div class="goi-y-kf">Chọn một mẫu hoặc “Tự vẽ”.</div>');
    }
    return `<div class="toc-do" data-clip="${esc(c.id)}">
        <div class="toc-dau"><span>Tốc độ</span><span class="toc-tab">${tab('thuong', 'Thường')}${tab('do_thi', 'Đồ thị')}</span></div>
        ${than}
        <div class="toc-dai"></div>
    </div>`;
}

/* Gắn sự kiện sau khi bang_phai vẽ xong. `bang` = BangPhai (ctx, tl, _clip(), ve(), _dangSua). */
export function ganTocDo(bang) {
    const goc = bang.el.querySelector('.toc-do');
    if (!goc) return;
    const ctx = bang.ctx;
    const clip = () => bang._clip();
    let canhBao = 0;

    const sua = (ops, c, tocMoi) => {
        if (chongClip(bang.tl, c.track, Number(c.bat_dau), Number(c.bat_dau) + dai(c, tocMoi), [c.id])) {
            if (Date.now() - canhBao > 3000) toast('Chậm lại thì clip dài ra và đè clip sau — dời clip sau hoặc tỉa bớt trước.', 'warn');
            canhBao = Date.now();
            return false;
        }
        bang._dangSua = true;
        ctx.sua('Tốc độ clip', ops, { gop: `toc:${c.id}:${lan}` });
        bang._dangSua = false;
        return true;
    };
    const datCong = (cong) => {
        const c = clip();
        const p = (k) => ['clips', { id: c.id }, k];
        cong = chuan(cong);                 // lưu đúng bản đã làm tròn → toc_do khớp diện tích đồ thị
        const toc = tocTrungBinh(cong);
        return sua([tao.dat(bang.tl, p('toc_do'), toc), tao.dat(bang.tl, p('toc_do_cong'), cong)], c, toc);
    };
    const datToc = (v) => {
        const c = clip();
        v = kep(tron2(v), TOC_MIN, TOC_MAX);
        return sua(opsDatTocDo(bang.tl, c, v), c, v);
    };
    const veDai = () => {
        const c = clip();
        goc.querySelector('.toc-dai').textContent =
            `Độ dài: ${fmtS(dai(c, Number(c.toc_do) || 1))} (gốc ${fmtS(dai(c, 1))}) · trung bình ${fmtX(Number(c.toc_do) || 1)}`;
    };
    veDai();

    goc.addEventListener('click', (e) => {
        const t = e.target.closest('[data-toc-tab], [data-toc-moc], [data-toc-mau], [data-toc-hd]');
        if (!t) return;
        const c = clip();
        lan += 1;
        if (t.dataset.tocTab) {
            ctx.ui.che_do_toc = t.dataset.tocTab;
            ctx.luuUi();
            if (t.dataset.tocTab === 'thuong' && c.toc_do_cong) datToc(Number(c.toc_do) || 1);
        } else if (t.dataset.tocMoc) {
            datToc(Number(t.dataset.tocMoc));
        } else if (t.dataset.tocMau != null) {
            const id = t.dataset.tocMau;
            const toc = Number(c.toc_do) || 1;
            if (!id) datToc(1);
            else datCong(id === 'tu_ve' ? chuan([{ q: 0, v: toc }, { q: 0.5, v: toc }, { q: 1, v: toc }]) : tuMau(id));
        } else if (t.dataset.tocHd === 'them') {
            themDiem();
            return;
        } else if (t.dataset.tocHd === 'xoa') {
            xoaDiem(chonDiem.i);
            return;
        }
        bang.ve();
    });

    // ---------------------------------------------------------------- tốc độ cố định
    const truot = goc.querySelector('[data-toc=truot]');
    const so = goc.querySelector('[data-toc=so]');
    if (truot) {
        truot.addEventListener('input', () => {
            let v = 10 ** Number(truot.value);
            if (Math.abs(Math.log10(v)) < 0.02) v = 1;          // hút về 1×
            if (datToc(v)) { so.value = tron2(v); veDai(); }
        });
        truot.addEventListener('change', () => { lan += 1; bang.ve(); });
        so.addEventListener('change', () => { lan += 1; datToc(Number(so.value) || 1); bang.ve(); });
    }

    // ---------------------------------------------------------------- đồ thị
    const svg = goc.querySelector('.toc-svg');
    if (!svg) return;
    const W = () => Math.max(120, svg.clientWidth || 260);
    const xCua = (q) => LE_TRAI + (W() - LE_TRAI - 10) * q;
    const qCua = (x) => (x - LE_TRAI) / (W() - LE_TRAI - 10);
    const cong = () => chuan(clip().toc_do_cong);
    if (chonDiem.clip !== clip().id) chonDiem = { clip: clip().id, i: -1 };

    const ve = () => {
        const d = cong();
        if (!d) return;
        const w = W();
        svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
        const c = clip();
        const D = dai(c, Number(c.toc_do) || 1);
        const qDau = D > 0 ? (ctx.ui.dau_phat - Number(c.bat_dau || 0)) / D : -1;
        const duong = d.map((x) => `${xCua(x.q).toFixed(1)},${yCua(x.v).toFixed(1)}`).join(' ');
        svg.innerHTML = LUOI.map((v) => `<line x1="${LE_TRAI - 4}" x2="${w}" y1="${yCua(v)}" y2="${yCua(v)}" class="${v === 1 ? 'toc-1x' : 'toc-luoi'}"/>`
            + `<text x="${LE_TRAI - 7}" y="${yCua(v) + 3.5}" text-anchor="end" class="toc-nhan">${v}×</text>`).join('')
            + `<polygon points="${xCua(0)},${H} ${duong} ${xCua(1)},${H}" class="toc-nen"/>`
            + `<polyline points="${duong}" class="toc-duong"/>`
            + (qDau >= 0 && qDau <= 1 ? `<line x1="${xCua(qDau)}" x2="${xCua(qDau)}" y1="0" y2="${H}" class="toc-dau-phat"/>` : '')
            + d.map((x, i) => `<circle cx="${xCua(x.q)}" cy="${yCua(x.v)}" r="${i === chonDiem.i ? 7 : 5.5}" data-i="${i}" class="toc-diem-tron ${i === chonDiem.i ? 'chon' : ''}"/>`).join('');
        vePanel();
    };
    const vePanel = () => {
        const d = cong();
        const diem = d[chonDiem.i];
        goc.querySelector('.toc-diem').innerHTML = diem
            ? `<label>Điểm ${chonDiem.i + 1}: tốc độ <input type="number" data-toc="diem" min="${TOC_MIN}" max="${TOC_MAX}" step="0.05" value="${tron2(diem.v)}"></label>
               <button type="button" class="nut nut-nho" data-toc-hd="xoa" ${chonDiem.i === 0 || chonDiem.i === d.length - 1 ? 'disabled' : ''}>Xoá điểm</button>`
            : '<button type="button" class="nut nut-nho" data-toc-hd="them">＋ Thêm điểm ở đầu phát</button>';
        veDai();
    };
    const themDiem = (q = null, v = null) => {
        const d = cong(), c = clip();
        const D = dai(c, Number(c.toc_do) || 1);
        q = q ?? (ctx.ui.dau_phat - Number(c.bat_dau || 0)) / D;
        if (!(q > 0.01 && q < 0.99)) { toast('Đặt đầu phát vào giữa clip để thêm điểm.', 'warn'); return; }
        if (d.some((x) => Math.abs(x.q - q) < 0.02)) { toast('Đã có điểm sát chỗ này.', 'warn'); return; }
        const moi = chuan([...d, { q, v: v ?? tocTai(d, q) }]);
        chonDiem.i = moi.findIndex((x) => Math.abs(x.q - Math.round(q * 1e4) / 1e4) < 1e-9);
        if (datCong(moi)) ve();
    };
    const xoaDiem = (i) => {
        const d = cong();
        if (i <= 0 || i >= d.length - 1) return;
        d.splice(i, 1);
        chonDiem.i = -1;
        if (datCong(d)) ve();
    };
    ve();
    new ResizeObserver(() => { if (svg.isConnected) ve(); }).observe(svg);

    const viTri = (e) => {
        const r = svg.getBoundingClientRect();
        return { x: e.clientX - r.left, y: e.clientY - r.top };
    };
    let keo = null;
    svg.addEventListener('pointerdown', (e) => {
        const o = e.target.closest('circle[data-i]');
        if (!o) return;
        e.preventDefault();
        lan += 1;
        chonDiem.i = Number(o.dataset.i);
        keo = { i: chonDiem.i, da_keo: false };
        svg.setPointerCapture(e.pointerId);
        // Chỉ đổi thuộc tính, KHÔNG vẽ lại: thay node giữa hai lần bấm thì dblclick (xoá điểm) không tới.
        svg.querySelectorAll('circle[data-i]').forEach((x) => {
            const la = Number(x.dataset.i) === chonDiem.i;
            x.classList.toggle('chon', la);
            x.setAttribute('r', la ? 7 : 5.5);
        });
    });
    svg.addEventListener('pointermove', (e) => {
        if (!keo) return;
        const d = cong();
        const { x, y } = viTri(e);
        const i = keo.i;
        const p = { ...d[i], v: tron2(kep(vCua(y), TOC_MIN, TOC_MAX)) };
        if (Math.abs(Math.log10(p.v)) < 0.03) p.v = 1;           // hút về 1×
        const a = i > 0 ? d[i - 1].q + 0.01 : 0, b = i < d.length - 1 ? d[i + 1].q - 0.01 : 1;
        if (i > 0 && i < d.length - 1 && a <= b) p.q = kep(qCua(x), a, b);   // không vượt điểm bên cạnh
        d[i] = p;
        keo.da_keo = true;
        if (datCong(d)) ve();
    });
    const tha = () => {
        if (!keo) return;
        const daKeo = keo.da_keo;
        keo = null;
        if (daKeo) bang.ve(); else vePanel();
    };
    svg.addEventListener('pointerup', tha);
    svg.addEventListener('pointercancel', tha);
    svg.addEventListener('dblclick', (e) => {
        lan += 1;
        // Theo toạ độ, không theo e.target: lúc kéo đã setPointerCapture nên dblclick có thể rơi vào svg.
        const { x, y } = viTri(e);
        const gan = cong().findIndex((d) => Math.hypot(xCua(d.q) - x, yCua(d.v) - y) <= 9);
        if (gan >= 0) { xoaDiem(gan); return; }
        themDiem(qCua(x), kep(tron2(vCua(y)), TOC_MIN, TOC_MAX));
    });
    goc.addEventListener('change', (e) => {
        if (e.target.dataset.toc !== 'diem') return;
        lan += 1;
        const d = cong();
        if (!d[chonDiem.i]) return;
        d[chonDiem.i] = { ...d[chonDiem.i], v: kep(Number(e.target.value) || 1, TOC_MIN, TOC_MAX) };
        if (datCong(d)) ve();
    });
}
