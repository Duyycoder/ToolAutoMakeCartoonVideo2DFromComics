/* Editor: nạp dự án → dựng các vùng → nối bộ lưu. Mọi vùng dùng chung một `ctx`. */
import { $, api, esc, toast, hoi } from './chung.js';
import { Store, thoiLuong, tao } from './store.js';
import { BoLuu } from './luu.js';
import { moCaiDat } from './cai_dat.js';
import { BangMedia } from './bang_media.js';
import { Timeline } from './timeline.js';
import { Preview } from './preview.js';
import { BangPhai } from './bang_phai.js';
import { BangPhuDe } from './bang_phu_de.js';
import { BangAi } from './bang_ai.js';
import { BangChe } from './bang_che.js';
import { BangChu } from './bang_chu.js';
import { BangDieuChinh } from './bang_dieu_chinh.js';
import { BangHieuUng } from './bang_hieu_ung.js';
import { BangChuyenCanh } from './bang_chuyen_canh.js';
import { ganXuat } from './xuat.js';

const UI_MAC_DINH = {
    dau_phat: 0, zoom_timeline: 0.45, cuon_timeline: { x: 0, y: 0 },
    bang_trai: 'media', bang_trai_mo: true, bang_phai_mo: true,
    tab_thuoc_tinh: 'video', muc_thu_gon: [], dang_chon: [], track_dang_chon: 'V1',
    kich_thuoc: { trai: 340, phai: 380, timeline: 280 },
    kho_media: { tab: 'media', loc: 'tat_ca', sap_xep: 'ngay', kieu: 'luoi', co_anh: 1, nhom: false, tim: '' },
    xem_truoc: { chat_luong: 'full', am_luong: 1, media: null },
    bat_dinh: true, lien_ket_am_thanh: true,
};

function tron(macDinh, luu) {
    const out = JSON.parse(JSON.stringify(macDinh));
    for (const [k, v] of Object.entries(luu || {})) {
        out[k] = (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k]))
            ? tron(out[k], v) : v;
    }
    return out;
}

/* Kênh sự kiện nhỏ giữa các vùng: 'media' (danh sách đổi), 'chon', 'dau_phat', 'timeline'. */
function taoBus() {
    const nghe = {};
    return {
        on(ten, fn) { (nghe[ten] = nghe[ten] || []).push(fn); },
        off(ten, fn) { if (nghe[ten]) nghe[ten] = nghe[ten].filter(x => x !== fn); },
        emit(ten, data) { (nghe[ten] || []).forEach((fn) => { try { fn(data); } catch (e) { console.error(e); } }); },
    };
}

const BANG_SAP_CO = {
    chu: ['Chữ', 'GĐ 3', ['Tiêu đề, chữ thường, mẫu chữ']],
};

async function khoiDong() {
    const id = new URLSearchParams(location.search).get('id');
    if (!id) { location.href = '/home.html'; return; }
    const khoaPhien = `phien:${id}`;
    let phienCu = '';
    try { phienCu = sessionStorage.getItem(khoaPhien) || ''; } catch (e) { /* bỏ qua */ }

    let mo;
    try {
        mo = await api(`/api/du-an/${encodeURIComponent(id)}?phien=${encodeURIComponent(phienCu)}`);
    } catch (e) {
        document.body.innerHTML = `<div class="tc-rong" style="margin:60px auto;max-width:520px">
            <h2>Không mở được dự án</h2><p>${esc(e.message)}</p>
            <a class="nut nut-chinh" href="/home.html">← Về trang chủ</a></div>`;
        return;
    }
    try { sessionStorage.setItem(khoaPhien, mo.khoa.phien); } catch (e) { /* bỏ qua */ }

    const du = mo.du_an;
    const store = new Store(mo.timeline, mo.hoan_tac);
    store.chiDoc = mo.khoa.chi_doc;
    const ui = tron(UI_MAC_DINH, mo.ui);
    const cfg = mo.cau_hinh || {};
    const bus = taoBus();
    const ctx = { id, du, store, ui, bus, media: du.media || [], chon: { media: null } };

    document.title = `${du.name} — Editor`;
    $('tenDuAn').textContent = du.name;
    const veThongSo = () => {
        const ts = ctx.du.thong_so || {};
        $('thongSo').textContent = ts.rong ? `${ts.rong}×${ts.cao} │ ${ts.fps}fps` : '';
    };
    veThongSo();

    // ------------------------------------------------------------ bộ lưu
    const nutLuu = $('btnLuu');
    const boLuu = new BoLuu({
        duAnId: id, phien: mo.khoa.phien, phienBan: mo.timeline.phien_ban || 0, chiDoc: mo.khoa.chi_doc,
        tuLuuGiay: Number(cfg.tu_luu_giay) || 1.5,
        layTimeline: () => { store.timeline.thoi_luong = thoiLuong(store.timeline); return store.timeline; },
        layNgan: () => store.ngan(),
        layUi: () => ui,
        khiTrangThai: (tt) => {
            nutLuu.className = `nut nut-nho nut-luu ${tt}`;
            $('chuLuu').textContent = { dang: 'Đang lưu…', loi: 'Lưu lỗi', chi_doc: 'Chỉ xem' }[tt] || 'Lưu';
            nutLuu.title = { ban: 'Có thay đổi chưa lưu — tự lưu sau giây lát (Ctrl+S để lưu ngay)',
                sach: 'Đã lưu mọi thay đổi (Ctrl+S: tạo bản lưu có tên)', dang: 'Đang ghi xuống đĩa…',
                loi: 'Chưa ghi được — thử lại bằng Ctrl+S', chi_doc: 'Dự án đang mở ở cửa sổ khác' }[tt] || '';
        },
        khiXungDot: async (hienTai) => {
            const chon = await hoi({
                tieuDe: 'Dự án đã được sửa ở nơi khác',
                noiDung: 'Có một cửa sổ khác vừa lưu dự án này. Tải lại để lấy bản mới nhất, '
                    + 'hoặc ghi đè bằng bản bạn đang sửa (bản kia vẫn còn trong menu Phiên bản).',
                nut: 'Tải lại', huy: 'Ghi đè bằng bản của tôi',
            });
            if (chon) location.reload();
            else boLuu.ghiDe(hienTai).then(() => toast('Đã ghi đè.', 'success')).catch((e) => toast(e.message, 'error'));
        },
        khiMatKhoa: () => {
            store.chiDoc = true;
            hienChiDoc('Dự án đang mở ở một cửa sổ khác — cửa sổ này chỉ xem, mọi sửa đổi không được lưu.');
        },
        khiCoKhoa: () => {
            hienChiDoc('Cửa sổ kia đã đóng — tải lại trang để sửa được.', true);
        },
    });
    function hienChiDoc(chu, coNutTai = false) {
        const b = $('bangChiDoc');
        b.classList.remove('an');
        b.innerHTML = `🔒 ${esc(chu)} ${coNutTai ? '<button class="nut nut-nho" id="btnTaiLai">Tải lại</button>' : ''}`;
        if (coNutTai) $('btnTaiLai').onclick = () => location.reload();
    }
    if (mo.khoa.chi_doc) {
        hienChiDoc('Dự án đang mở ở một cửa sổ khác — cửa sổ này chỉ xem. '
            + 'Nếu cửa sổ kia đã tắt ngang, quyền sửa sẽ tự về đây sau chưa tới 1 phút.');
    }
    boLuu.khiTrangThai(boLuu.trangThai());
    ctx.boLuu = boLuu;
    ctx.luuUi = (som = false) => boLuu.danhDauUi(som);
    ctx.sua = (ten, ops, opts) => {
        try {
            return store.thucHien(ten, ops, opts);
        } catch (e) {
            toast(e.message, 'warn');
            return null;
        }
    };
    store.nghe(() => { boLuu.danhDauTimeline(); bus.emit('timeline'); });
    // desktop.py gọi dong() khi đóng cửa sổ và CHỜ Promise: lưu hết rồi nhả khoá. Người
    // dùng bấm Huỷ ở hộp "Bạn có chắc?" thì heartbeat kế tiếp lấy lại khoá (cùng mã phiên).
    window.editor = { flush: () => boLuu.flush(), dong: () => boLuu.dong(false), ctx };

    // ------------------------------------------------------------ bố cục
    const than = $('edThan');
    const apKichThuoc = () => {
        const k = ui.kich_thuoc;
        than.style.setProperty('--w-trai', `${k.trai}px`);
        than.style.setProperty('--w-phai', `${k.phai}px`);
        than.style.setProperty('--h-tl', `${k.timeline}px`);
        than.classList.toggle('dong-trai', !ui.bang_trai_mo);
        than.classList.toggle('dong-phai', !ui.bang_phai_mo);
        bus.emit('bo_cuc');
    };
    apKichThuoc();
    than.querySelectorAll('.keo').forEach((thanh) => {
        thanh.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            const loai = thanh.dataset.keo;
            const x0 = e.clientX, y0 = e.clientY, k0 = { ...ui.kich_thuoc };
            thanh.classList.add('dang-keo');
            thanh.setPointerCapture(e.pointerId);
            const di = (ev) => {
                const k = ui.kich_thuoc;
                if (loai === 'trai') k.trai = Math.max(240, Math.min(620, k0.trai + ev.clientX - x0));
                if (loai === 'phai') k.phai = Math.max(260, Math.min(640, k0.phai - (ev.clientX - x0)));
                if (loai === 'timeline') k.timeline = Math.max(150, Math.min(innerHeight - 260, k0.timeline - (ev.clientY - y0)));
                apKichThuoc();
            };
            const xong = () => {
                thanh.classList.remove('dang-keo');
                thanh.removeEventListener('pointermove', di);
                ctx.luuUi(true);
            };
            thanh.addEventListener('pointermove', di);
            thanh.addEventListener('pointerup', xong, { once: true });
            thanh.addEventListener('pointercancel', xong, { once: true });
        });
    });

    // ------------------------------------------------------------ các vùng
    const bangMedia = new BangMedia(ctx);
    const cacBang = { 
        media: bangMedia, phu_de: new BangPhuDe(ctx), ai: new BangAi(ctx), che: new BangChe(ctx), chu: new BangChu(ctx),
        dieu_chinh: new BangDieuChinh(ctx), hieu_ung: new BangHieuUng(ctx), chuyen_canh: new BangChuyenCanh(ctx),
    };
    bus.on('media_can_tai', () => bangMedia.tai());
    bus.on('tac_vu_moi', () => cacBang.ai.tai());
    ganXuat(ctx);
    const preview = new Preview(ctx);
    const timeline = new Timeline(ctx);
    const bangPhai = new BangPhai(ctx);
    ctx.preview = preview;
    ctx.timeline = timeline;

    const bangTrai = $('bangTrai');
    function veBangTrai() {
        $('thanhIcon').querySelectorAll('[data-bang]').forEach((b) =>
            b.classList.toggle('bat', ui.bang_trai_mo && b.dataset.bang === ui.bang_trai));
        bangTrai.innerHTML = '';
        const bang = cacBang[ui.bang_trai];
        if (bang) {
            bangTrai.appendChild(bang.el);
            bang.ve();
            return;
        }
        const [ten, gd, ds] = BANG_SAP_CO[ui.bang_trai] || ['?', '', []];
        bangTrai.innerHTML = `<div class="bang-dau"><h2>${esc(ten)}</h2></div>
            <div class="bang-noi"><div class="sap-co"><b>Có ở ${esc(gd)}</b> (xem docs/PLAN-editor.md):
            <ul>${ds.map((d) => `<li>${esc(d)}</li>`).join('')}</ul></div></div>`;
    }
    $('thanhIcon').addEventListener('click', (e) => {
        const b = e.target.closest('[data-bang]');
        if (!b) return;
        if (ui.bang_trai === b.dataset.bang && ui.bang_trai_mo) ui.bang_trai_mo = false;
        else { ui.bang_trai = b.dataset.bang; ui.bang_trai_mo = true; }
        apKichThuoc();
        veBangTrai();
        ctx.luuUi(true);
    });
    veBangTrai();
    // Mở một bảng trái từ nơi khác (vd áp dụng kết quả AI → bảng Phụ đề). moKieu: mở luôn mục Kiểu chữ.
    ctx.moBang = (ten, moKieu = false) => {
        ui.bang_trai = ten;
        ui.bang_trai_mo = true;
        apKichThuoc();
        veBangTrai();
        ctx.luuUi(true);
        if (moKieu) {
            const d = bangTrai.querySelector('[data-khu=kieu]');
            if (d) { d.open = true; d.scrollIntoView({ block: 'nearest' }); }
        }
    };
    bus.on('bat_bang_phai', () => { ui.bang_phai_mo = !ui.bang_phai_mo; apKichThuoc(); ctx.luuUi(true); });

    // ------------------------------------------------------------ thanh trên
    const ve = async () => {
        await boLuu.dong();
        location.href = '/home.html';
    };
    $('btnVe').addEventListener('click', ve);
    const caiDat = () => moCaiDat();
    $('btnCaiDat').addEventListener('click', caiDat);
    $('btnCaiDat2').addEventListener('click', caiDat);
    const luuTay = async () => {
        if (boLuu.chiDoc) { toast('Cửa sổ này chỉ xem.', 'warn'); return; }
        try {
            const r = await boLuu.luuTay();
            toast(`Đã lưu (bản ${r.ten.replace(/^luu_|\.json$/g, '')}).`, 'success', 2500);
        } catch (e) { toast(e.message, 'error'); }
    };
    nutLuu.addEventListener('click', luuTay);
    $('btnPhienBan').addEventListener('click', (e) => menuPhienBan(ctx, e.currentTarget));

    // ------------------------------------------------------------ phím tắt
    document.addEventListener('keydown', (e) => {
        const dangGo = e.target.closest('input, textarea, select, [contenteditable]');
        const ctrl = e.ctrlKey || e.metaKey;
        if (ctrl && e.key.toLowerCase() === 's') { e.preventDefault(); luuTay(); return; }
        if (dangGo || document.querySelector('.modal-nen')) return;
        if (ctrl && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); hoanTac(); return; }
        if (ctrl && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) { e.preventDefault(); lamLai(); return; }
        if (e.key === ' ') { e.preventDefault(); preview.batTat(); return; }
        if (!ctrl && e.key.toLowerCase() === 'k') { e.preventDefault(); preview.dung(); return; }
        if (!ctrl && e.key.toLowerCase() === 'l') { e.preventDefault(); preview.phatToiL(); return; }
        if (!ctrl && e.key.toLowerCase() === 'j') { e.preventDefault(); preview.phatLuiJ(); return; }
        if (e.shiftKey && (e.key === 'Delete' || e.key === 'Backspace')) { e.preventDefault(); timeline.xoaGonDangChon(); return; }
        if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); timeline.xoaDangChon(); return; }
        
        if (ctrl && e.key.toLowerCase() === 'c') { e.preventDefault(); timeline.saoChep(); return; }
        if (ctrl && e.key.toLowerCase() === 'x') { e.preventDefault(); if (timeline.saoChep()) timeline.xoaDangChon(); return; }
        if (ctrl && e.key.toLowerCase() === 'v') { e.preventDefault(); timeline.dan(); return; }
        if (ctrl && e.key.toLowerCase() === 'd') { e.preventDefault(); timeline.nhanDoi(); return; }
        if (ctrl && e.key.toLowerCase() === 'a') { e.preventDefault(); timeline.chonTatCa(); return; }
        
        if (e.key === 'Escape') { 
            e.preventDefault(); 
            const m = document.querySelectorAll('.menu');
            if (m.length) { m.forEach(x => x.remove()); return; }
            timeline.chonClip(null); 
            return; 
        }
        if (!ctrl && e.key.toLowerCase() === 'm') { e.preventDefault(); timeline.danhDau(); return; }
        if (!ctrl && e.key.toLowerCase() === 'q') { e.preventDefault(); timeline.tiaToiDauPhat('truoc', !e.altKey); return; }
        if (!ctrl && e.key.toLowerCase() === 'w') { e.preventDefault(); timeline.tiaToiDauPhat('sau', !e.altKey); return; }
        
        if (!ctrl && e.key.toLowerCase() === 's') { e.preventDefault(); timeline.catTaiDauPhat(); return; }
        
        const fps = Number((ctx.du.thong_so || {}).fps) || 30;
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Home' || e.key === 'End' || e.key === 'ArrowUp' || e.key === 'ArrowDown') preview.dung();
        if (e.key === 'ArrowUp') { e.preventDefault(); timeline.nhayDiemCat('truoc'); return; }
        if (e.key === 'ArrowDown') { e.preventDefault(); timeline.nhayDiemCat('sau'); return; }
        if (e.key === 'ArrowLeft') { e.preventDefault(); timeline.datDauPhat(ui.dau_phat - (e.shiftKey ? 1 : 1 / fps)); }
        if (e.key === 'ArrowRight') { e.preventDefault(); timeline.datDauPhat(ui.dau_phat + (e.shiftKey ? 1 : 1 / fps)); }
        if (e.key === 'Home') { e.preventDefault(); timeline.datDauPhat(0); }
        if (e.key === 'End') { e.preventDefault(); timeline.datDauPhat(thoiLuong(store.timeline)); }
        if (e.key === '[') {
            e.preventDefault();
            if (e.altKey) {
                ctx.sua('Xoá vùng xuất', [tao.dat(store.timeline, ['vung_vao'], null), tao.dat(store.timeline, ['vung_ra'], null)]);
                return;
            }
            const t = Math.round(ui.dau_phat * 1000) / 1000;
            const ra = store.timeline.vung_ra;
            if (ra != null && t >= ra) return toast('Vùng vào phải trước vùng ra', 'warn');
            ctx.sua('Đặt vùng vào', [tao.dat(store.timeline, ['vung_vao'], t)]);
        }
        if (e.key === ']') {
            e.preventDefault();
            if (e.altKey) {
                ctx.sua('Xoá vùng xuất', [tao.dat(store.timeline, ['vung_vao'], null), tao.dat(store.timeline, ['vung_ra'], null)]);
                return;
            }
            const t = Math.round(ui.dau_phat * 1000) / 1000;
            const vao = store.timeline.vung_vao || 0;
            if (t <= vao) return toast('Vùng ra phải sau vùng vào', 'warn');
            ctx.sua('Đặt vùng ra', [tao.dat(store.timeline, ['vung_ra'], t)]);
        }
    });
    function hoanTac() {
        const l = store.hoanTacMot();
        if (l) toast(`↶ Hoàn tác: ${l.ten}`, 'info', 1500);
    }
    function lamLai() {
        const l = store.lamLaiMot();
        if (l) toast(`↷ Làm lại: ${l.ten}`, 'info', 1500);
    }
    ctx.hoanTac = hoanTac;
    ctx.lamLai = lamLai;

    // Khôi phục lựa chọn lần trước: clip đang chọn, hoặc media đang xem trước.
    const clipCu = (ui.dang_chon || []).filter((cid) => store.timeline.clips.some((c) => c.id === cid));
    ui.dang_chon = clipCu;
    ctx.chon.clip = clipCu[clipCu.length - 1] || null;
    ctx.chon.media = null;   // mở lại luôn ở chế độ xem timeline
    bus.on('thong_so', () => { veThongSo(); bus.emit('bo_cuc'); });

    mo.thong_bao.forEach((tb) => toast(tb, 'warn', 9000));
    bus.emit('timeline');
    bus.emit('chon');
    bus.emit('dau_phat');
    bangPhai.ve();
}

async function menuPhienBan(ctx, nut) {
    document.querySelectorAll('.menu').forEach((m) => m.remove());
    let ds;
    try { ds = await api(`/api/du-an/${encodeURIComponent(ctx.id)}/phien-ban`); } catch (e) { toast(e.message, 'error'); return; }
    const m = document.createElement('div');
    m.className = 'menu';
    m.style.maxHeight = '60vh';
    m.style.overflow = 'auto';
    m.innerHTML = ds.length ? ds.map((b) => `<button data-ten="${esc(b.ten)}">
            ${b.loai === 'luu' ? '💾' : '🕘'} <span>${esc(b.luc_hien)}${b.nhan ? ` — ${esc(b.nhan)}` : ''}</span></button>`).join('')
        : '<div style="padding:10px;color:var(--chu-2)">Chưa có bản lưu nào. App tự lưu một bản mỗi 5 phút có thay đổi; Ctrl+S tạo bản có tên.</div>';
    document.body.appendChild(m);
    const r = nut.getBoundingClientRect();
    m.style.left = `${Math.max(8, r.right - m.offsetWidth)}px`;
    m.style.top = `${r.bottom + 4}px`;
    m.addEventListener('click', async (e) => {
        const b = e.target.closest('[data-ten]');
        if (!b) return;
        m.remove();
        const ok = await hoi({ tieuDe: 'Khôi phục bản này?', nut: 'Khôi phục',
            noiDung: 'Timeline hiện tại được chụp lại trước khi thay, và thao tác này hoàn tác được (Ctrl+Z).' });
        if (!ok) return;
        try {
            await ctx.boLuu.flush();
            const kq = await api(`/api/du-an/${encodeURIComponent(ctx.id)}/phien-ban/${encodeURIComponent(b.dataset.ten)}/khoi-phuc`,
                { method: 'POST', body: { phien: ctx.boLuu.phien, phien_ban: ctx.boLuu.phienBan } });
            ctx.boLuu.phienBan = kq.timeline.phien_ban;
            ctx.store.thayToanBo('Khôi phục phiên bản', kq.timeline);
            toast('Đã khôi phục.', 'success');
        } catch (err) { toast(err.message, 'error'); }
    });
    setTimeout(() => document.addEventListener('click', () => m.remove(), { once: true }), 0);
}

khoiDong().catch((e) => { console.error(e); toast(`Lỗi khởi động editor: ${e.message}`, 'error'); });
