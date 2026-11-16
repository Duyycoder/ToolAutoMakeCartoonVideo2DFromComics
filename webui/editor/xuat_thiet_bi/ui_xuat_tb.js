/* Giao diện "Máy xuất: Thiết bị này" trong hộp Xuất video: mô tả + danh sách làm được / chưa được, chạy xuất có tiến độ
   và nút Huỷ, xong thì lưu file (điện thoại: bảng chia sẻ → Lưu video / Tệp; máy tính: tải về). */
import { esc, toast } from '../chung.js';
import { thoiLuong } from '../store.js';
import { phanLoai } from './phan_loai.js';
import { xuatTrenThietBi } from './vong_xuat.js';

/* HTML mô tả cho dự án hiện tại; trả {html, chan: bool}. */
export function moTaThietBi(ctx) {
    const coWebCodecs = typeof VideoEncoder === 'function' && typeof OffscreenCanvas === 'function';
    const tl = ctx.store.timeline;
    const pl = phanLoai(tl, ctx.media, 0, thoiLuong(tl));
    const ds = (xs, lop) => xs.map((x) => `<li class="${lop}">${esc(x)}</li>`).join('');
    const html = `<div class="goi-y-nho">Ghép + mã hoá ngay trên máy đang mở trang này (card đồ hoạ / chip của điện thoại, laptop).
        Tiếng do server dựng nên giữ nguyên mọi hiệu ứng âm thanh. Giữ trang mở và màn hình sáng tới khi xong.</div>
        ${coWebCodecs ? '' : '<div class="tb-loi">Trình duyệt này chưa hỗ trợ WebCodecs — cần Chrome/Edge mới hoặc Safari iOS 17+.</div>'}
        ${pl.chan.length ? `<div class="tb-loi">Thiết bị chưa ghép được (hãy chọn Server):</div><ul class="tb-ds">${ds(pl.chan, 'tb-loi')}</ul>` : ''}
        ${pl.canhBao.length ? `<ul class="tb-ds">${ds(pl.canhBao, 'tb-canh-bao')}</ul>` : ''}`;
    return { html, chan: !coWebCodecs || pl.chan.length > 0 };
}

async function luuFile(file, ten) {
    const f = file instanceof File ? file : new File([file], ten, { type: 'video/mp4' });
    if (matchMedia('(pointer: coarse)').matches && navigator.canShare && navigator.canShare({ files: [f] })) {
        try { await navigator.share({ files: [f], title: ten }); return; } catch (e) { if (e.name === 'AbortError') return; }
    }
    const url = URL.createObjectURL(f);
    const a = document.createElement('a');
    a.href = url;
    a.download = ten;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 120000);
}

let dangChay = false;

/* Chạy xuất trên thiết bị (đã đóng hộp Xuất). */
export async function chayXuatThietBi(ctx, tc) {
    if (dangChay) { toast('Đang có một lượt xuất trên thiết bị — chờ xong hoặc huỷ.', 'warn'); return; }
    dangChay = true;
    let huy = false;
    const nut = document.getElementById('btnXuat');
    const tb = toast('Chuẩn bị xuất trên thiết bị…', 'info', 24 * 3600 * 1000);
    const chu = document.createElement('span');
    const nutHuy = document.createElement('button');
    nutHuy.className = 'nut nut-nho';
    nutHuy.textContent = 'Huỷ';
    nutHuy.style.marginLeft = '8px';
    nutHuy.onclick = (e) => { e.stopPropagation(); huy = true; chu.textContent = 'Đang huỷ…'; };
    tb.textContent = '';
    tb.append(chu, nutHuy);
    const chanRoi = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', chanRoi);
    let khoa = null;
    try { khoa = await navigator.wakeLock?.request('screen'); } catch (e) { /* không giữ được màn hình */ }
    const canhBaoAn = () => { if (document.hidden) toast('Đang xuất trên máy: đừng khoá màn hình / chuyển app — trình duyệt có thể dừng xuất.', 'warn', 8000); };
    document.addEventListener('visibilitychange', canhBaoAn);
    try {
        const kq = await xuatTrenThietBi(ctx, tc, (p, t) => {
            chu.textContent = `${t} (${p}%)`;
            if (nut) nut.textContent = `Máy đang xuất ${p}%`;
        }, () => huy);
        tb.remove();
        const mb = (kq.file.size / 1e6).toFixed(1);
        const xong = toast(`✔ Xuất trên máy xong: ${kq.ten} (${kq.W}×${kq.H}, ${kq.fps} fps, ${mb} MB, ${kq.giay} s) — bấm để lưu lại.`, 'success', 120000);
        xong.style.cursor = 'pointer';
        xong.addEventListener('click', () => luuFile(kq.file, kq.ten));
        await luuFile(kq.file, kq.ten).catch(() => {});
    } catch (e) {
        tb.remove();
        toast(huy ? 'Đã huỷ xuất trên thiết bị.' : `Xuất trên thiết bị lỗi: ${e.message}`, huy ? 'info' : 'error', 15000);
    } finally {
        dangChay = false;
        if (nut) nut.textContent = 'Xuất video ▾';
        window.removeEventListener('beforeunload', chanRoi);
        document.removeEventListener('visibilitychange', canhBaoAn);
        try { khoa && khoa.release(); } catch (e) { /* đã nhả */ }
    }
}
