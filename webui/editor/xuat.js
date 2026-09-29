/* Hộp Xuất video: độ phân giải, fps, chất lượng, bộ mã hoá (NVENC nếu có), chỉ âm thanh, kèm .srt.
 * Xuất chạy ở hàng đợi GPU của server; tiến độ hiện ngay trên nút "Xuất video". */
import { $, api, esc, toast, fmtThoiGian, coFile } from './chung.js';
import { thoiLuong } from './store.js';

export function ganXuat(ctx) {
    const nut = $('btnXuat');
    nut.disabled = false;
    nut.title = 'Xuất video (ffmpeg, dùng file gốc)';
    nut.textContent = 'Xuất video ▾';
    let dangXuat = null;
    nut.addEventListener('click', () => {
        if (dangXuat) { ctx.moBang('ai'); return; }
        moHop(ctx);
    });
    ctx.bus.on('tac_vu', (ds) => {
        const v = ds.find((x) => x.loai === 'xuat' && ['cho', 'dang_chay'].includes(x.trang_thai));
        if (v) {
            dangXuat = v.id;
            nut.textContent = v.trang_thai === 'cho' ? 'Chờ lượt xuất…' : `Đang xuất ${Math.floor(v.tien_do || 0)}%`;
            return;
        }
        if (dangXuat) {
            const xong = ds.find((x) => x.id === dangXuat);
            dangXuat = null;
            nut.textContent = 'Xuất video ▾';
            if (xong && xong.trang_thai === 'xong') {
                const kq = xong.ket_qua || {};
                const t = toast(`✔ Đã xuất ${kq.file} (${coFile(kq.dung_luong)}, ${kq.bo_ma_hoa}) — bấm để mở thư mục.`, 'success', 12000);
                t.style.cursor = 'pointer';
                t.addEventListener('click', () => api(`/api/du-an/${encodeURIComponent(ctx.id)}/mo-thu-muc-con?ten=xuat`, { method: 'POST' }));
            }
        }
    });
}

function moHop(ctx) {
    const tl = ctx.store.timeline;
    const tong = thoiLuong(tl);
    if (!tong) { toast('Timeline trống — kéo media xuống trước khi xuất.', 'warn'); return; }
    const ts = ctx.du.thong_so || {};
    const coGiong = tl.tracks.some((t) => t.vai === 'long_tieng') && tl.clips.some((c) => c.long_tieng_cho);
    const nho = ctx.ui.xuat || {};
    const nen = document.createElement('div');
    nen.className = 'modal-nen';
    nen.innerHTML = `<form class="modal" style="width:min(480px,100%)">
        <h3>Xuất video</h3>
        <p class="modal-noi-dung">Dài ${fmtThoiGian(tong)} · khung dự án ${ts.rong}×${ts.cao} · ${ts.fps} fps. Lưu vào thư mục xuat/ của dự án.</p>
        <div class="o-form">
            <label>Tên file<input type="text" name="ten" value="${esc(nho.ten || ctx.du.name)}"></label>
            <div class="hang">
                <label>Độ phân giải<select name="do_phan_giai">
                    ${[['', `Theo dự án (${ts.rong}×${ts.cao})`], ['720p', '720p'], ['1080p', '1080p'], ['1440p', '1440p (2K)'], ['4k', '4K']]
                        .map(([v, t]) => `<option value="${v}" ${(nho.do_phan_giai || '') === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
                <label>FPS<select name="fps">${[['', `Theo dự án (${ts.fps})`], ['24', '24'], ['25', '25'], ['30', '30'], ['60', '60']]
                        .map(([v, t]) => `<option value="${v}" ${String(nho.fps || '') === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
            </div>
            <div class="hang">
                <label>Chất lượng<select name="crf">${[[16, 'Rất cao (file lớn)'], [19, 'Cao'], [22, 'Vừa'], [26, 'Nhẹ']]
                        .map(([v, t]) => `<option value="${v}" ${Number(nho.crf || 19) === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
                <label>Bộ mã hoá<select name="bo_ma_hoa">${[['auto', 'Tự chọn (NVENC nếu có GPU)'], ['nvenc', 'NVENC (GPU NVIDIA)'], ['x264', 'x264 (CPU)']]
                        .map(([v, t]) => `<option value="${v}" ${(nho.bo_ma_hoa || 'auto') === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
            </div>
            ${coGiong ? `<label>Giảm nhạc nền khi có giọng lồng <span class="gt">${nho.giam_nhac_nen ?? 90}%</span>
                <input type="range" name="giam_nhac_nen" min="0" max="100" value="${nho.giam_nhac_nen ?? 90}"></label>` : ''}
            <label class="check"><input type="checkbox" name="xuat_srt" ${nho.xuat_srt !== false ? 'checked' : ''}> Kèm file phụ đề .srt</label>
            <label class="check"><input type="checkbox" name="chi_am_thanh" ${nho.chi_am_thanh ? 'checked' : ''}> Chỉ xuất âm thanh (.m4a)</label>
            ${(tl.vung_vao != null || tl.vung_ra != null) ? `<label class="check"><input type="checkbox" name="chi_vung" checked> Chỉ xuất vùng [ ] (${fmtThoiGian(tl.vung_vao || 0)} → ${fmtThoiGian(tl.vung_ra ?? tong)})</label>` : ''}
        </div>
        <div class="modal-nut"><button type="button" class="nut" data-huy>Huỷ</button><button type="submit" class="nut nut-chinh">Xuất</button></div>
    </form>`;
    document.body.appendChild(nen);
    const f = nen.querySelector('form');
    const r = f.querySelector('[name=giam_nhac_nen]');
    if (r) r.addEventListener('input', () => { r.closest('label').querySelector('.gt').textContent = `${r.value}%`; });
    const dong = () => nen.remove();
    nen.querySelector('[data-huy]').addEventListener('click', dong);
    nen.addEventListener('keydown', (e) => { if (e.key === 'Escape') dong(); });
    f.addEventListener('submit', async (e) => {
        e.preventDefault();
        const tc = {
            ten: f.ten.value.trim() || ctx.du.name, do_phan_giai: f.do_phan_giai.value, fps: f.fps.value ? Number(f.fps.value) : null,
            crf: Number(f.crf.value), bo_ma_hoa: f.bo_ma_hoa.value, xuat_srt: f.xuat_srt.checked, chi_am_thanh: f.chi_am_thanh.checked,
            giam_nhac_nen: r ? Number(r.value) : 90,
        };
        if (f.chi_vung && f.chi_vung.checked) {
            tc.vung_vao = tl.vung_vao || 0;
            tc.vung_ra = tl.vung_ra ?? tong;
        }
        ctx.ui.xuat = tc;
        ctx.luuUi();
        const nut = f.querySelector('[type=submit]');
        nut.disabled = true;
        try {
            await ctx.boLuu.flush();        // xuất đọc timeline TRÊN ĐĨA — phải lưu hết trước
            const kq = await api(`/api/du-an/${encodeURIComponent(ctx.id)}/xuat`, { method: 'POST', body: { phien: ctx.boLuu.phien, tuy_chon: tc } });
            dong();
            toast(`Bắt đầu xuất ${kq.file}…`, 'info', 3000);
            ctx.bus.emit('tac_vu_moi');
        } catch (err) {
            toast(err.message, 'error');
            nut.disabled = false;
        }
    });
    f.ten.focus();
    f.ten.select();
}
