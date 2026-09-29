/* Trang chủ: lưới dự án trong Nơi làm việc + tạo/nhập/đổi tên/xoá dự án. */
import { $, api, esc, toast, truoc, hoi, chonFile, tiLe } from './chung.js';
import { moCaiDat } from './cai_dat.js';

const st = { duAn: [], duongDan: '' };
const LUU_LOC = 'tc.loc';

async function taiDanhSach() {
    const r = await api('/api/workspace');
    st.duAn = r.du_an;
    st.duongDan = r.duong_dan;
    $('noiLam').textContent = r.duong_dan + (r.mac_dinh ? '  (mặc định)' : '');
    const fps = [...new Set(st.duAn.map((d) => d.thong_so && d.thong_so.fps).filter(Boolean))].sort((a, b) => a - b);
    const chon = $('locFps').value;
    $('locFps').innerHTML = '<option value="">Mọi FPS</option>' + fps.map((f) => `<option value="${f}">${f} fps</option>`).join('');
    $('locFps').value = fps.map(String).includes(chon) ? chon : '';
    ve();
}

function khung(ts) {
    if (!ts || !ts.rong) return '';
    return ts.rong > ts.cao ? 'ngang' : ts.rong < ts.cao ? 'doc' : 'vuong';
}

function ve() {
    const tim = $('timDuAn').value.trim().toLowerCase();
    const locK = $('locDoPhanGiai').value, locF = $('locFps').value, sx = $('sapXep').value;
    try { localStorage.setItem(LUU_LOC, JSON.stringify({ locK, locF, sx })); } catch (e) { /* bỏ qua */ }
    let ds = st.duAn.filter((d) => (!tim || (d.name + ' ' + d.mo_ta).toLowerCase().includes(tim))
        && (!locK || khung(d.thong_so) === locK)
        && (!locF || String((d.thong_so || {}).fps) === locF));
    if (sx === 'ten') ds = ds.slice().sort((a, b) => a.name.localeCompare(b.name, 'vi'));
    if (sx === 'tao') ds = ds.slice().sort((a, b) => (b.tao_luc || '').localeCompare(a.tao_luc || ''));
    const luoi = $('luoiDuAn');
    if (!st.duAn.length) {
        luoi.style.display = 'block';
        luoi.innerHTML = `<div class="tc-rong"><h2>Chưa có dự án nào</h2>
            <p>Tạo dự án mới, hoặc nhập một thư mục video/dự án có sẵn trên máy.</p>
            <button class="nut nut-chinh" data-lam="moi">＋ Dự án mới</button></div>`;
        return;
    }
    luoi.style.display = '';
    if (!ds.length) {
        luoi.innerHTML = '<p style="color:var(--chu-2)">Không có dự án khớp bộ lọc.</p>';
        return;
    }
    luoi.innerHTML = ds.map((d) => {
        const ts = d.thong_so || {};
        const bia = d.co_anh_bia ? `style="background-image:url('/api/du-an/${d.id}/anh-bia?t=${Math.floor(d.sua_ts)}')"` : '';
        return `<article class="the-da" data-id="${esc(d.id)}" tabindex="0" title="${esc(d.folder)}">
            <div class="bia" ${bia}>${d.co_anh_bia ? '' : '🎞'}</div>
            <div class="noi">
                <div class="ten">${esc(d.name)}</div>
                <div class="phu">Sửa ${esc(truoc(d.sua_luc))}${d.so_media ? ` · ${d.so_media} media` : ''}</div>
                <div class="chip">
                    ${ts.rong ? `<span class="so">${ts.rong}×${ts.cao}</span><span>${esc(ts.fps)} fps</span><span>${esc(ts.ti_le || tiLe(ts.rong, ts.cao))}</span>` : ''}
                    ${d.can_nang_cap ? '<span class="nhan-nho cam">dự án cũ</span>' : ''}
                    ${d.ngoai ? '<span>ngoài Nơi làm việc</span>' : ''}
                </div>
            </div>
            <button class="nut-icon nut-menu" data-menu title="Tuỳ chọn">⋮</button>
        </article>`;
    }).join('');
}

function moDuAn(id) {
    window.location.href = `/editor.html?id=${encodeURIComponent(id)}`;
}

function menuThe(id, x, y) {
    document.querySelectorAll('.menu').forEach((m) => m.remove());
    const d = st.duAn.find((v) => v.id === id);
    if (!d) return;
    const m = document.createElement('div');
    m.className = 'menu';
    m.innerHTML = `<button data-l="mo">▶ Mở</button>
        <button data-l="nhan-ban">📑 Nhân bản</button>
        <button data-l="ten">✎ Đổi tên</button>
        <button data-l="mo-ta">📝 Sửa mô tả</button>
        <button data-l="thu-muc">📂 Mở thư mục</button><hr>
        <button data-l="xoa" class="nguy">🗑 Xoá (chuyển vào Thùng rác)</button>`;
    document.body.appendChild(m);
    const r = m.getBoundingClientRect();
    m.style.left = `${Math.min(x, innerWidth - r.width - 8)}px`;
    m.style.top = `${Math.min(y, innerHeight - r.height - 8)}px`;
    m.addEventListener('click', async (e) => {
        const l = e.target.closest('button') && e.target.closest('button').dataset.l;
        if (!l) return;
        m.remove();
        try {
            if (l === 'mo') moDuAn(id);
            if (l === 'thu-muc') await api(`/api/du-an/${id}/mo-thu-muc`, { method: 'POST' });
            if (l === 'nhan-ban') {
                const ten = await hoi({ tieuDe: 'Nhân bản dự án', o: { giaTri: d.name + ' (bản sao)' }, nut: 'Nhân bản' });
                if (ten && ten.trim()) {
                    await api(`/api/du-an/${id}/nhan-ban`, { method: 'POST', body: { ten } });
                    toast('Đã nhân bản.', 'success');
                    await taiDanhSach();
                }
            }
            if (l === 'ten') {
                const ten = await hoi({ tieuDe: 'Đổi tên dự án', o: { giaTri: d.name }, nut: 'Đổi tên' });
                if (ten && ten.trim()) {
                    await api(`/api/du-an/${id}`, { method: 'PATCH', body: { ten } });
                    await taiDanhSach();
                }
            }
            if (l === 'mo-ta') {
                const mt = await hoi({ tieuDe: 'Mô tả dự án', o: { giaTri: d.mo_ta, nhieuDong: 4 }, nut: 'Lưu' });
                if (mt !== null) {
                    await api(`/api/du-an/${id}`, { method: 'PATCH', body: { mo_ta: mt } });
                    await taiDanhSach();
                }
            }
            if (l === 'xoa') {
                const ok = await hoi({
                    tieuDe: `Xoá dự án "${d.name}"?`, nguyHiem: true, nut: 'Chuyển vào Thùng rác',
                    noiDung: `Cả thư mục (kể cả media đã chép vào) sẽ được chuyển vào Thùng rác của Windows — khôi phục lại được từ đó.\n\n${d.folder}`,
                });
                if (ok) {
                    await api(`/api/du-an/${id}/xoa`, { method: 'POST' });
                    toast('Đã chuyển dự án vào Thùng rác.', 'success');
                    await taiDanhSach();
                }
            }
        } catch (err) { toast(err.message, 'error'); }
    });
    setTimeout(() => document.addEventListener('click', () => m.remove(), { once: true }), 0);
}

/* ------------------------------------------------------------ Dự án mới */
const MAU = [
    { k: '16:9', rong: 1920, cao: 1080, nhan: 'YouTube' },
    { k: '9:16', rong: 1080, cao: 1920, nhan: 'TikTok/Shorts' },
    { k: '1:1', rong: 1080, cao: 1080, nhan: 'Vuông' },
    { k: 'tuy', rong: 0, cao: 0, nhan: 'Tuỳ chỉnh' },
];

function hopDuAnMoi() {
    const nen = document.createElement('div');
    nen.className = 'modal-nen';
    nen.innerHTML = `<form class="modal" style="width:min(520px,100%)" novalidate>
        <h3>Dự án mới</h3>
        <div class="o-form">
            <label>Tên dự án<input type="text" name="ten" required placeholder="vd: Phim hoạt hình tập 1" autocomplete="off"></label>
            <div>
                <div style="color:var(--chu-2);font-size:12.5px;margin-bottom:5px">Khung hình</div>
                <div class="chon-mau">${MAU.map((m, i) => {
                    const w = m.rong ? Math.round(28 * m.rong / Math.max(m.rong, m.cao)) : 22;
                    const h = m.rong ? Math.round(28 * m.cao / Math.max(m.rong, m.cao)) : 22;
                    return `<button type="button" data-mau="${i}" class="${i === 0 ? 'bat' : ''}">
                        <span class="khung" style="width:${w}px;height:${h}px;${m.rong ? '' : 'border-style:dashed'}"></span>
                        <b>${m.k === 'tuy' ? '…' : m.k}</b><span>${m.nhan}</span></button>`;
                }).join('')}</div>
            </div>
            <div class="hang" id="oTuyChinh" style="display:none">
                <label>Rộng (px)<input type="number" name="rong" value="1920" min="16" max="8192" step="2"></label>
                <label>Cao (px)<input type="number" name="cao" value="1080" min="16" max="8192" step="2"></label>
            </div>
            <div class="hang">
                <label>FPS<select name="fps"><option>24</option><option>25</option><option selected>30</option><option>60</option></select></label>
                <label>Độ phân giải<input type="text" name="xem" disabled></label>
            </div>
            <label class="check"><input type="checkbox" name="theo_video_dau"> Lấy khung hình &amp; FPS theo video đầu tiên nhập vào</label>
            <label>Mô tả (tuỳ chọn)<textarea name="mo_ta" rows="2"></textarea></label>
        </div>
        <div class="modal-nut"><button type="button" class="nut" data-huy>Huỷ</button>
            <button type="submit" class="nut nut-chinh">Tạo dự án</button></div>
    </form>`;
    document.body.appendChild(nen);
    const f = nen.querySelector('form');
    let mau = 0;
    const capNhat = () => {
        const m = MAU[mau];
        $('oTuyChinh').style.display = m.rong ? 'none' : '';
        const rong = m.rong || Number(f.rong.value), cao = m.cao || Number(f.cao.value);
        f.xem.value = rong && cao ? `${rong}×${cao}` : '';
    };
    nen.querySelectorAll('[data-mau]').forEach((b) => b.addEventListener('click', () => {
        mau = Number(b.dataset.mau);
        nen.querySelectorAll('[data-mau]').forEach((x) => x.classList.toggle('bat', x === b));
        capNhat();
    }));
    f.rong.addEventListener('input', capNhat);
    f.cao.addEventListener('input', capNhat);
    capNhat();
    const dong = () => nen.remove();
    nen.querySelector('[data-huy]').addEventListener('click', dong);
    nen.addEventListener('keydown', (e) => { if (e.key === 'Escape') dong(); });
    nen.addEventListener('mousedown', (e) => { if (e.target === nen) dong(); });
    f.addEventListener('submit', async (e) => {
        e.preventDefault();
        const ten = f.ten.value.trim();
        if (!ten) { f.ten.focus(); toast('Phải đặt tên dự án.', 'warn'); return; }
        const m = MAU[mau];
        const nut = f.querySelector('[type=submit]');
        nut.disabled = true;
        try {
            const the = await api('/api/du-an', {
                method: 'POST', body: {
                    ten, mo_ta: f.mo_ta.value, thong_so: {
                        rong: m.rong || Number(f.rong.value), cao: m.cao || Number(f.cao.value),
                        fps: Number(f.fps.value), theo_video_dau: f.theo_video_dau.checked,
                    },
                },
            });
            moDuAn(the.id);
        } catch (err) {
            toast(err.message, 'error');
            nut.disabled = false;
        }
    });
    f.ten.focus();
}

/* ------------------------------------------------------------------ Gắn sự kiện */
function ganSuKien() {
    $('btnDuAnMoi').addEventListener('click', hopDuAnMoi);
    $('btnCaiDat').addEventListener('click', () => moCaiDat(() => taiDanhSach().catch(() => {})));
    $('btnMoNoiLam').addEventListener('click', () => api('/api/workspace/mo-thu-muc', { method: 'POST' })
        .catch((e) => toast(e.message, 'error')));
    $('btnDoiNoiLam').addEventListener('click', async () => {
        try {
            const folder = await chonFile('folder');
            if (!folder) return;
            await api('/api/workspace', { method: 'POST', body: { duong_dan: folder } });
            await taiDanhSach();
            toast('Đã đổi Nơi làm việc.', 'success');
        } catch (e) { toast(e.message, 'error'); }
    });
    $('btnNhapDuAn').addEventListener('click', async () => {
        try {
            const folder = await chonFile('folder');
            if (!folder) return;
            const t = toast('Đang nhập dự án (đọc thông số từng video)…', 'info', 60000);
            try {
                const the = await api('/api/du-an/nhap', { method: 'POST', body: { folder } });
                toast(`Đã nhập "${the.name}".`, 'success');
                await taiDanhSach();
            } finally { t.remove(); }
        } catch (e) { toast(e.message, 'error'); }
    });
    ['timDuAn', 'locDoPhanGiai', 'locFps', 'sapXep'].forEach((id) => $(id).addEventListener('input', ve));
    const luoi = $('luoiDuAn');
    luoi.addEventListener('click', (e) => {
        if (e.target.closest('[data-lam=moi]')) return hopDuAnMoi();
        const the = e.target.closest('.the-da');
        if (!the) return;
        if (e.target.closest('[data-menu]')) {
            e.stopPropagation();
            const r = e.target.getBoundingClientRect();
            return menuThe(the.dataset.id, r.left, r.bottom + 4);
        }
        moDuAn(the.dataset.id);
    });
    luoi.addEventListener('contextmenu', (e) => {
        const the = e.target.closest('.the-da');
        if (!the) return;
        e.preventDefault();
        menuThe(the.dataset.id, e.clientX, e.clientY);
    });
    luoi.addEventListener('keydown', (e) => {
        const the = e.target.closest('.the-da');
        if (the && e.key === 'Enter') moDuAn(the.dataset.id);
    });
    $('tcTab').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        $('tcTab').querySelectorAll('button').forEach((x) => x.classList.toggle('bat', x === b));
        $('tabDuAn').classList.toggle('an', b.dataset.tab !== 'du-an');
        $('tabHangLoat').classList.toggle('an', b.dataset.tab !== 'hang-loat');
        $('tabHuongDan').classList.toggle('an', b.dataset.tab !== 'huong-dan');
    });
    // Quay lại từ editor bằng nút Back của trình duyệt: danh sách phải mới.
    window.addEventListener('pageshow', (e) => { if (e.persisted) taiDanhSach().catch(() => {}); });
}

import { initHangLoat } from './hang_loat.js';

try {
    const l = JSON.parse(localStorage.getItem(LUU_LOC) || '{}');
    if (l.locK) $('locDoPhanGiai').value = l.locK;
    if (l.sx) $('sapXep').value = l.sx;
} catch (e) { /* bỏ qua */ }
ganSuKien();
taiDanhSach().catch((e) => toast(`Không tải được danh sách dự án: ${e.message}`, 'error'));
initHangLoat();
