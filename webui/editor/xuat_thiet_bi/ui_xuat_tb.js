/* Giao diện "Máy xuất: Thiết bị này" trong hộp Xuất video: hồ sơ máy (codec, ước lượng), phần server dựng hộ, gợi ý xuất
   bằng server khi phần đó lớn; chạy xuất có tiến độ + nút Huỷ, xong thì lưu file (điện thoại: bảng chia sẻ → Lưu video / Tệp;
   máy tính: chọn chỗ lưu / tải về) và tuỳ chọn đưa bản xuất lên thư mục xuat/ của dự án (tai_len.js, tải tiếp được). */
import { esc, toast } from '../chung.js';
import { thoiLuong } from '../store.js';
import { taiLenFile } from '../tai_len.js';
import { NGUONG_GOI_Y_SERVER, phanLoai } from './phan_loai.js';
import { kichThuocXuat, xuatTrenThietBi } from './vong_xuat.js';
import { doHoSo, hoSoDaLuu } from './ho_so_may.js';
import { danhGia, fmtGiay, ghiLenDoPhanGiai, htmlHoSo, xoaChuThich } from './ui_ho_so.js';
import { docPhienDo } from './khuc_opfs.js';

/* HTML ô Thiết bị cho dự án hiện tại. chon = {codec, do_phan_giai, fps, vung: [t0, t1], dua_len}. → {html, chan} */
export function moTaThietBi(ctx, chon) {
    const coWebCodecs = typeof VideoEncoder === 'function' && typeof OffscreenCanvas === 'function';
    const tl = ctx.store.timeline, ts = ctx.du.thong_so || {};
    const fps = Number(chon.fps) || Number(ts.fps) || 30;
    const [t0, t1] = chon.vung || [0, thoiLuong(tl)];
    const pl = phanLoai(tl, ctx.media, Math.round(t0 * fps), Math.round(t1 * fps), fps);
    const hs = hoSoDaLuu();
    const [W, H] = kichThuocXuat(ts, chon.do_phan_giai);
    const dg = danhGia(hs, chon.codec, W, H, fps, t1 - t0);
    const li = (x, lop) => `<li class="${lop}">${esc(x)}</li>`;
    const server = [];
    if (pl.lopChu) server.push('chữ / hình vẽ / phụ đề — server vẽ, giống hệt bản xuất Server');
    if (pl.doan.length) server.push(`${Math.round(pl.tiLeNuong * 100)} % thời lượng server dựng sẵn: ${pl.lyDoNuong.join(', ')}`);
    const html = `<div class="goi-y-nho">Ghép + mã hoá ngay trên máy đang mở trang này (card đồ hoạ / chip của điện thoại, laptop).
        Tiếng do server dựng nên giữ nguyên mọi hiệu ứng âm thanh. Giữ trang mở và màn hình sáng tới khi xong.</div>
        ${coWebCodecs ? htmlHoSo(hs, chon.codec) : '<div class="tb-loi">Trình duyệt này chưa hỗ trợ WebCodecs — cần Chrome/Edge mới hoặc Safari iOS 17+.</div>'}
        ${dg.lam_duoc === false ? `<div class="tb-loi">${W}×${H} ${fps} fps: ${esc(dg.chu)} — chọn độ phân giải/codec khác hoặc xuất bằng Server.</div>`
            : dg.giay ? `<div class="goi-y-nho">Ước lượng trên máy này: ${esc(dg.chu)} (chưa gồm thời gian chờ server).</div>` : ''}
        ${server.length ? `<div class="goi-y-nho">Server làm hộ:</div><ul class="tb-ds">${server.map((x) => li(x, '')).join('')}</ul>` : ''}
        ${pl.tiLeNuong > NGUONG_GOI_Y_SERVER ? `<div class="tb-canh-bao">Phần server phải dựng lớn — xuất thẳng bằng Server sẽ nhanh hơn.
            <button type="button" class="nut nut-nho" data-sang-server>Xuất bằng Server</button></div>` : ''}
        ${pl.canhBao.length ? `<ul class="tb-ds">${pl.canhBao.map((x) => li(x, 'tb-canh-bao')).join('')}</ul>` : ''}
        <div data-phien-do></div>
        <label class="check"><input type="checkbox" name="dua_len" ${chon.dua_len ? 'checked' : ''}> Đưa bản xuất lên dự án (thư mục xuat/ trên server)</label>`;
    return { html, chan: !coWebCodecs || pl.chan.length > 0 || dg.lam_duoc === false };
}

/* Gắn ô Thiết bị vào form hộp Xuất: vẽ lại khi đổi máy xuất/độ phân giải/fps/vùng/codec, nút Đo máy, nút sang Server.
   Trả {ve, luaChon()} — luaChon() là phần tuỳ chọn riêng của thiết bị gộp vào tc khi bấm Xuất. */
export function ganThietBi(ctx, f, nho) {
    const o = f.querySelector('[data-tb]'), nutXuat = f.querySelector('[type=submit]');
    const tl = ctx.store.timeline, ts = ctx.du.thong_so || {};
    let codec = nho.codec_tb || 'avc', duaLen = !!nho.dua_len, lamLai = false;
    const ve = () => {
        const sel = f.do_phan_giai;
        if (!o || f.may_xuat.value !== 'thiet_bi') { nutXuat.disabled = false; xoaChuThich(sel); return; }
        const fps = Number(f.fps.value) || Number(ts.fps) || 30;
        const tong = thoiLuong(tl);
        const vung = f.chi_vung && f.chi_vung.checked ? [tl.vung_vao || 0, tl.vung_ra ?? tong] : [0, tong];
        const mt = moTaThietBi(ctx, { codec, do_phan_giai: sel.value, fps, vung, dua_len: duaLen });
        o.innerHTML = mt.html;
        nutXuat.disabled = mt.chan;
        ghiLenDoPhanGiai(sel, hoSoDaLuu(), codec, fps, vung[1] - vung[0], (v) => kichThuocXuat(ts, v));
        // Lượt xuất trước bị dừng giữa chừng (khoá màn hình, đóng tab…) → các khúc đã xong còn trong bộ nhớ trình duyệt.
        docPhienDo(ctx.id).then((tt) => {
            const o2 = o.querySelector('[data-phien-do]');
            if (!o2 || !tt) return;
            o2.innerHTML = `<div class="tb-canh-bao">Lượt xuất trước dừng ở ${fmtGiay(tt.so_khuc * 10)} / ${fmtGiay(tt.giay || 0)}
                (${new Date(tt.luc).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}).
                Bấm Xuất để xuất tiếp — nếu dự án hoặc tuỳ chọn đã đổi thì tự làm lại từ đầu.</div>
                <label class="check"><input type="checkbox" name="lam_lai" ${lamLai ? 'checked' : ''}> Làm lại từ đầu</label>`;
        });
    };
    if (o) {
        o.addEventListener('change', (e) => {
            if (e.target.name === 'codec_tb') { codec = e.target.value; ve(); }
            if (e.target.name === 'dua_len') duaLen = e.target.checked;
            if (e.target.name === 'lam_lai') lamLai = e.target.checked;
        });
        o.addEventListener('click', async (e) => {
            if (e.target.closest('[data-sang-server]')) {
                f.may_xuat.value = '';
                f.may_xuat.dispatchEvent(new Event('change'));
            }
            const b = e.target.closest('[data-do-may]');
            if (!b) return;
            b.disabled = true;
            const tt = o.querySelector('[data-do-tt]');
            try { await doHoSo({ baoTienDo: (p, chu) => { tt.textContent = `${chu} ${p}%`; } }); } catch (err) { toast(err.message, 'error'); }
            ve();
        });
    }
    for (const ten of ['do_phan_giai', 'fps', 'chi_vung']) if (f[ten]) f[ten].addEventListener('change', ve);
    return { ve, luaChon: () => ({ codec_tb: codec, dua_len: duaLen, lam_lai: lamLai }) };
}

async function luuFile(file, ten) {
    const f = file instanceof File ? file : new File([file], ten, { type: 'video/mp4' });
    if (matchMedia('(pointer: coarse)').matches && navigator.canShare && navigator.canShare({ files: [f] })) {
        try { await navigator.share({ files: [f], title: ten }); return; } catch (e) { if (e.name === 'AbortError') return; }
    }
    if (typeof window.showSaveFilePicker === 'function') {
        try {
            const fh = await window.showSaveFilePicker({ suggestedName: ten, types: [{ description: 'Video MP4', accept: { 'video/mp4': ['.mp4'] } }] });
            const w = await fh.createWritable();
            await f.stream().pipeTo(w);          // chép theo luồng từ OPFS — không đọc cả file vào RAM
            toast(`✔ Đã lưu ${fh.name}`, 'success', 6000);
            return;
        } catch (e) { if (e.name === 'AbortError') return; }
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

async function duaLenDuAn(ctx, kq) {
    const f = new File([kq.file], kq.ten, { type: 'video/mp4' });     // tham chiếu file OPFS, không chép vào RAM
    const tb = toast('Đang đưa bản xuất lên dự án… 0%', 'info', 24 * 3600 * 1000);
    try {
        const r = await taiLenFile(ctx.id, ctx.boLuu.phien, f, (p) => { tb.textContent = `Đang đưa bản xuất lên dự án… ${p}%`; }, true);
        tb.remove();
        toast(`✔ Đã đưa lên dự án: xuat/${r.ten}`, 'success', 8000);
    } catch (e) {
        tb.remove();
        toast(`Đưa lên dự án lỗi: ${e.message}`, 'error', 15000);
    }
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
    const giuSang = async () => { try { khoa = await navigator.wakeLock?.request('screen'); } catch (e) { /* không giữ được */ } };
    await giuSang();
    const khiAn = () => {
        if (document.hidden) toast('Đang xuất trên máy: đừng khoá màn hình / chuyển app — trình duyệt có thể dừng xuất.', 'warn', 8000);
        else if (!khoa || khoa.released) giuSang();          // quay lại: xin giữ màn hình lại (bị nhả khi ẩn)
    };
    document.addEventListener('visibilitychange', khiAn);
    try {
        const kq = await xuatTrenThietBi(ctx, tc, (p, t) => {
            chu.textContent = `${t} (${p}%)`;
            if (nut) nut.textContent = `Máy đang xuất ${p}%`;
        }, () => huy);
        tb.remove();
        const mb = (kq.file.size / 1e6).toFixed(1);
        const tiep = kq.tiep_tu ? `, xuất tiếp từ ${fmtGiay(kq.tiep_tu)}` : '';
        const xong = toast(`✔ Xuất trên máy xong: ${kq.ten} (${kq.W}×${kq.H}, ${kq.fps} fps, ${mb} MB, ${kq.giay} s${tiep}) — bấm để lưu lại.`, 'success', 120000);
        xong.style.cursor = 'pointer';
        xong.addEventListener('click', () => luuFile(kq.file, kq.ten));
        if (tc.dua_len) duaLenDuAn(ctx, kq);
        await luuFile(kq.file, kq.ten).catch(() => {});
    } catch (e) {
        tb.remove();
        toast(huy ? 'Đã huỷ xuất trên thiết bị.' : `Xuất trên thiết bị lỗi: ${e.message}`, huy ? 'info' : 'error', 15000);
    } finally {
        dangChay = false;
        if (nut) nut.textContent = 'Xuất video ▾';
        window.removeEventListener('beforeunload', chanRoi);
        document.removeEventListener('visibilitychange', khiAn);
        try { khoa && khoa.release(); } catch (e) { /* đã nhả */ }
    }
}
