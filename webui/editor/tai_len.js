/* Tải file từ trình duyệt lên server theo từng phần 8 MB (xem orchestrator/editor/tai_len.py).
   Một request chứa nguyên video điện thoại bị tunnel cắt (HTTP 408/413); mỗi phần nhỏ thì không.
   - Gửi SONG_SONG phần cùng lúc: mạng di động qua tunnel mỗi request chỉ ~1 MB/s.
   - Phần lỗi mạng được gửi lại nhiều lần (iPhone khoá màn hình làm Safari ngắt kết nối).
   - Nhớ phiên theo file (localStorage): chọn lại đúng file đó thì server báo phần đã có, chỉ gửi phần thiếu.
   - Giữ màn hình sáng (Wake Lock) trong lúc tải để Safari không bị treo ngầm. */
import { api } from './chung.js';

const CO_PHAN = 8 * 1024 * 1024;
const SONG_SONG = 3;
const SO_LAN_THU = 8;

const cho = (ms) => new Promise((r) => setTimeout(r, ms));
const khoaNho = (pid, f) => `tai-len:${pid}:${f.name}:${f.size}:${f.lastModified}`;

function nho(k, v) {
    try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e) { /* chế độ ẩn danh */ }
}
function doc(k) {
    try { return localStorage.getItem(k) || ''; } catch (e) { return ''; }
}

async function giuManHinh() {
    try { return await navigator.wakeLock?.request('screen'); } catch (e) { return null; }
}

async function guiPhan(url, phan) {
    for (let lan = 1; ; lan++) {
        try {
            const res = await fetch(url, { method: 'PUT', body: phan, headers: { 'Content-Type': 'application/octet-stream' } });
            const data = await res.json().catch(() => ({}));
            if (res.ok) return data;
            // 4xx là lỗi dữ liệu/phiên — gửi lại cũng vô ích (trừ 408 timeout, 429 quá tải).
            if (res.status < 500 && ![408, 429].includes(res.status)) {
                throw Object.assign(new Error(data.detail || `HTTP ${res.status}`), { khongThuLai: true, ma: res.status });
            }
            if (lan >= SO_LAN_THU) throw new Error(data.detail || `HTTP ${res.status}`);
        } catch (e) {
            if (e.khongThuLai || lan >= SO_LAN_THU) throw e;
        }
        // Đang ẩn (khoá màn hình/chuyển app) thì chờ quay lại rồi mới thử, khỏi đốt hết lượt thử.
        while (document.hidden) await cho(1000);
        await cho(Math.min(15000, 1000 * 2 ** (lan - 1)));
    }
}

async function phienCu(goc, k) {
    const uid = doc(k);
    if (!uid) return null;
    try {
        const tt = await api(`${goc}/${uid}`);
        return { uid, daCo: new Set(tt.phan || []) };
    } catch (e) { nho(k, ''); return null; }
}

/* Tải một File lên dự án `pid`; `baoTienDo(phanTram)` được gọi sau mỗi phần. Trả về danh sách media mới. */
export async function taiLenFile(pid, phien, file, baoTienDo = () => {}) {
    const goc = `/api/du-an/${encodeURIComponent(pid)}/media/tai-len`;
    const k = khoaNho(pid, file);
    const cu = await phienCu(goc, k);
    const uid = cu?.uid || (await api(goc, { method: 'POST', body: { phien, ten: file.name, kich_thuoc: file.size } })).uid;
    nho(k, uid);
    const viTri = [];
    for (let vt = 0; vt < file.size; vt += CO_PHAN) if (!cu?.daCo.has(vt)) viTri.push(vt);
    let daGui = file.size - viTri.reduce((s, vt) => s + Math.min(CO_PHAN, file.size - vt), 0);
    baoTienDo(Math.round(daGui * 100 / file.size));

    let khoa = await giuManHinh();
    const layLai = async () => { if (!document.hidden && khoa?.released) khoa = await giuManHinh(); };
    document.addEventListener('visibilitychange', layLai);
    try {
        const tho = async () => {
            while (viTri.length) {
                const vt = viTri.shift();
                const phan = file.slice(vt, vt + CO_PHAN);
                await guiPhan(`${goc}/${uid}?vi_tri=${vt}&phien=${encodeURIComponent(phien)}`, phan);
                daGui += phan.size;
                baoTienDo(Math.min(100, Math.round(daGui * 100 / file.size)));
            }
        };
        await Promise.all(Array.from({ length: SONG_SONG }, tho));
        nho(k, '');   // đủ byte rồi — lỗi đổi định dạng ở bước sau không tải tiếp được
        try {
            return (await api(`${goc}/${uid}/xong`, { method: 'POST', body: { phien } })).media;
        } catch (e) { throw Object.assign(e, { khongThuLai: true }); }
    } catch (e) {
        // Lỗi mạng: giữ phiên để chọn lại file là tải tiếp. Lỗi dữ liệu/phiên: bỏ hẳn.
        if (e.khongThuLai) {
            nho(k, '');
            api(`${goc}/${uid}`, { method: 'DELETE' }).catch(() => {});
        } else {
            e.message += ' — chọn lại đúng file này để tải tiếp phần còn thiếu.';
        }
        throw e;
    } finally {
        document.removeEventListener('visibilitychange', layLai);
        khoa?.release?.().catch?.(() => {});
    }
}
