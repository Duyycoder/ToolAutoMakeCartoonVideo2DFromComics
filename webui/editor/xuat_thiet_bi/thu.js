/* Trang thử xuất trên thiết bị (thu.html): hồ sơ máy, giải mã file gốc, mã hoá + ghi MP4.
   Kết quả cũng gán vào window.__thu để kiểm tự động (Chrome headless + CDP). */
import { doHoSo, hoSoDaLuu } from './ho_so_may.js';
import { NguonVideo } from './nguon_video.js';
import { moBanXuat } from './ghep_mp4.js';

const $ = (id) => document.getElementById(id);
const ghi = (s) => { $('nhatKy').textContent += `${new Date().toLocaleTimeString()} ${s}\n`; };
window.__thu = {};

function veBang(hs) {
    const dong = hs.ma_hoa.map((m) => `<tr><td>${m.ten}</td><td>${m.do_phan_giai}</td>
        <td class="${m.nhan ? 'ok' : 'khong'}">${m.nhan ? 'có' : 'không'}</td>
        <td>${m.phan_cung == null ? '–' : m.phan_cung ? 'phần cứng' : 'phần mềm'}</td>
        <td>${m.khung_giay == null ? '–' : `${m.khung_giay} khung/s`}${m.loi ? ` <span class="khong">${m.loi}</span>` : ''}</td></tr>`).join('');
    $('bangHoSo').innerHTML = `<div class="mo">WebCodecs: ${hs.webcodecs ? 'có' : 'KHÔNG'} · WebGL2: ${hs.webgl2 ? 'có' : 'không'}
        · texture tối đa ${hs.max_texture} · RAM ${hs.bo_nho_gb ?? '?'} GB · ${hs.luong_cpu ?? '?'} luồng · OPFS trống ${hs.opfs_trong_gb ?? '?'} GB</div>
        <table><tr><th>Codec</th><th>Độ phân giải</th><th>Nhận</th><th>Bộ mã hoá</th><th>Tốc độ</th></tr>${dong}</table>`;
}

async function chayDo(dayDu) {
    $('nutDo').disabled = $('nutLoc').disabled = true;
    try {
        const hs = await doHoSo({ chayThuDayDu: dayDu, baoTienDo: (p, t) => { $('ttDo').textContent = `${p}% — ${t}`; } });
        veBang(hs);
        window.__thu.hoSo = hs;
        ghi('Hồ sơ máy: xong');
    } catch (e) { ghi(`Hồ sơ lỗi: ${e.message}`); } finally { $('nutDo').disabled = $('nutLoc').disabled = false; }
}

async function thuGiaiMa() {
    const url = $('urlNguon').value.trim();
    if (!url) return;
    $('ttGiaiMa').textContent = 'Đang mở…';
    let n;
    try {
        const t0 = performance.now();
        n = await NguonVideo.mo(url);
        const info = { codec: n.codec, rong: n.rong, cao: n.cao, xoay: n.xoay, thoi_luong: n.thoiLuong, giai_ma_duoc: n.giaiMaDuoc };
        if (!n.giaiMaDuoc) { $('ttGiaiMa').textContent = `Máy KHÔNG giải mã được ${n.codec} — cần server chuyển mã.`; window.__thu.giaiMa = info; return; }
        const ds = Array.from({ length: 90 }, (_, i) => Math.min(n.thoiLuong - 0.01, i / 30));
        const t1 = performance.now();
        let dem = 0, dau = null;
        const cv = $('cvGiaiMa'), c2 = cv.getContext('2d');
        for await (const s of n.khungTai(ds)) {
            if (!s) continue;
            if (!dau) { dau = s.timestamp; cv.width = 320; cv.height = Math.round(320 * n.cao / n.rong); s.draw(c2, 0, 0, cv.width, cv.height); }
            dem++;
            s.close();
        }
        const giay = (performance.now() - t1) / 1000;
        Object.assign(info, { khung: dem, khung_giay: Math.round(dem / giay), mo_ms: Math.round(t1 - t0) });
        window.__thu.giaiMa = info;
        $('ttGiaiMa').textContent = `${n.codec} ${n.rong}×${n.cao}${n.xoay ? ` (xoay ${n.xoay}°)` : ''} · ${n.thoiLuong.toFixed(2)} s · giải mã ${dem} khung, ${info.khung_giay} khung/s · mở ${info.mo_ms} ms`;
    } catch (e) {
        $('ttGiaiMa').textContent = `Lỗi: ${e.message}`;
        window.__thu.giaiMa = { loi: e.message };
    } finally { n && n.dong(); }
}

/* Khung thử có chuyển động + chữ giờ (nhìn bằng mắt kiểm được khung không lặp/thiếu). */
function veKhungThu(c, w, h, i, fps) {
    const t = i / fps;
    const g = c.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, `hsl(${(t * 60) % 360} 70% 45%)`); g.addColorStop(1, `hsl(${(t * 60 + 180) % 360} 70% 25%)`);
    c.fillStyle = g; c.fillRect(0, 0, w, h);
    c.fillStyle = '#fff'; c.beginPath(); c.arc((t * w / 3) % w, h / 2, h / 8, 0, 7); c.fill();
    c.font = `bold ${Math.round(h / 10)}px system-ui`; c.fillText(`${t.toFixed(3)} s  #${i}`, w * 0.05, h * 0.9);
}

async function thuXuat() {
    const [w, h] = $('chonDpg').value.split('x').map(Number), fps = Number($('chonFps').value), codec = $('chonCodec').value;
    $('nutXuat').disabled = true;
    try {
        const ban = await moBanXuat({ codec, rong: w, cao: h, fps, bitrate: Math.round(w * h * fps * 0.1), ten: `thu_${codec}_${h}p${fps}.mp4` });
        const cv = new OffscreenCanvas(w, h), c = cv.getContext('2d');
        const so = 3 * fps, t0 = performance.now();
        for (let i = 0; i < so; i++) {
            veKhungThu(c, w, h, i, fps);
            await ban.them(cv, i / fps);
            if (i % fps === 0) $('ttXuat').textContent = `Mã hoá ${i}/${so}…`;
        }
        const { file, opfs } = await ban.xong();
        const giay = (performance.now() - t0) / 1000;
        const url = URL.createObjectURL(file);
        window.__thu.xuat = { codec, w, h, fps, khung: so, giay: Math.round(giay * 100) / 100, khung_giay: Math.round(so / giay), byte: file.size, opfs };
        $('ttXuat').innerHTML = `Xong ${so} khung trong ${giay.toFixed(1)} s (${Math.round(so / giay)} khung/s) · ${(file.size / 1e6).toFixed(1)} MB
            · ${opfs ? 'ghi luồng vào OPFS' : 'giữ trong RAM'} · <a href="${url}" download="thu_${codec}_${h}p${fps}.mp4">⬇ tải</a>`;
    } catch (e) {
        $('ttXuat').textContent = `Lỗi: ${e.message}`;
        window.__thu.xuat = { loi: e.message };
    } finally { $('nutXuat').disabled = false; }
}

$('nutDo').onclick = () => chayDo(true);
$('nutLoc').onclick = () => chayDo(false);
$('nutGiaiMa').onclick = thuGiaiMa;
$('nutXuat').onclick = thuXuat;
const cu = hoSoDaLuu();
if (cu) { veBang(cu); $('ttDo').textContent = `Kết quả đo lúc ${new Date(cu.luc).toLocaleString('vi-VN')} — bấm Đo để đo lại.`; }
const q = new URLSearchParams(location.search);
if (q.get('url')) $('urlNguon').value = q.get('url');
window.__thu.chayDo = chayDo; window.__thu.thuGiaiMa = thuGiaiMa; window.__thu.thuXuat = thuXuat;
