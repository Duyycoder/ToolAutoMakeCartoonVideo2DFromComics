// Kiểm tra proxy Gemini-API lúc mở app; cookie hết hạn / chưa có thì hiện hướng dẫn lấy cookie.
import { api, esc, toast } from './chung.js';

const CHO_TOI_DA_MS = 90000;
const KHOA_BO_QUA = 'gemini_cookie_de_sau';
const KHOA_DA_PING = 'gemini_cookie_da_ping';
// Cửa sổ app (WebView2) mất sessionStorage mỗi lần mở lại -> "Để sau" lưu localStorage kèm hạn.
const DE_SAU_MS = 12 * 3600 * 1000;

export const HUONG_DAN_COOKIE = `
<ol class="gemini-buoc">
  <li>Mở <b>gemini.google.com</b> bằng Chrome/Edge và đăng nhập tài khoản Google (bấm nút bên dưới).</li>
  <li>Nhấn <b>F12</b> → tab <b>Application</b> (Ứng dụng) → mục <b>Cookies</b> → chọn <code>https://gemini.google.com</code>.</li>
  <li>Gõ <code>1PSID</code> vào ô lọc. Nháy đúp ô <b>Value</b> của dòng <code>__Secure-1PSID</code>, Ctrl+A, Ctrl+C rồi dán vào ô thứ nhất.</li>
  <li>Làm tương tự với dòng <code>__Secure-1PSIDTS</code> cho ô thứ hai.</li>
  <li>Bấm <b>Lưu &amp; kết nối</b>. Đừng bấm Đăng xuất trên trang Gemini — đăng xuất là cookie mất hiệu lực ngay.</li>
</ol>
<p class="gemini-ghi-chu">Mẹo: dùng một cửa sổ ẩn danh để lấy cookie rồi đóng nó (không đăng xuất) thì cookie sống lâu hơn,
vì trình duyệt thường ngày không xoay vòng cookie đè lên.</p>`;

function chen_css() {
    if (document.getElementById('gemini-cookie-css')) return;
    const st = document.createElement('style');
    st.id = 'gemini-cookie-css';
    st.textContent = `
.gemini-buoc { margin: 0 0 6px 18px; padding: 0; display: grid; gap: 6px; font-size: 13px; line-height: 1.45; }
.gemini-buoc code { background: rgba(127,127,127,.18); padding: 0 4px; border-radius: 3px; }
.gemini-ghi-chu { font-size: 12px; opacity: .75; margin: 0; }
.gemini-o { display: grid; gap: 4px; font-size: 13px; }
.gemini-o input { width: 100%; font-family: monospace; }
.gemini-loi { color: #f87171; font-size: 12px; min-height: 16px; white-space: pre-wrap; }`;
    document.head.appendChild(st);
}

const ngu = (ms) => new Promise((r) => setTimeout(r, ms));

/** Chờ proxy hết trạng thái "đang khởi động" rồi trả trạng thái cuối. */
export async function choTrangThai(toiDa = CHO_TOI_DA_MS) {
    const het = Date.now() + toiDa;
    let tt = await api('/api/gemini/trang-thai');
    while (tt.ma === 'dang_khoi_dong' && Date.now() < het) {
        await ngu(1500);
        tt = await api('/api/gemini/trang-thai');
    }
    return tt;
}

/** Chờ proxy lên rồi gửi 1 câu hỏi thật. Trả {ok, thong_bao, tra_loi, ms, ...}. */
export async function pingGemini() {
    await choTrangThai();
    return api('/api/gemini/ping', { method: 'POST' });
}

/** Hộp thoại điền cookie. Trả true nếu kết nối thành công. */
export function moHopCookie(tt = null) {
    chen_css();
    return new Promise((resolve) => {
        const nen = document.createElement('div');
        nen.className = 'modal-nen';
        const tieuDe = tt && tt.ma === 'cookie_het_han' ? 'Cookie Gemini đã hết hạn' : 'Kết nối Gemini (dịch bằng proxy cục bộ)';
        nen.innerHTML = `<div class="modal" role="dialog" aria-modal="true" style="width:min(620px,100%)">
            <h3>${esc(tieuDe)}</h3>
            ${tt && tt.thong_bao ? `<p class="modal-noi-dung">${esc(tt.thong_bao)}</p>` : ''}
            ${HUONG_DAN_COOKIE}
            <label class="gemini-o">__Secure-1PSID<input class="o-nhap" data-o="psid" type="text" spellcheck="false" autocomplete="off"></label>
            <label class="gemini-o">__Secure-1PSIDTS<input class="o-nhap" data-o="psidts" type="text" spellcheck="false" autocomplete="off"></label>
            <div class="gemini-loi"></div>
            <div class="modal-nut">
                <button class="nut" data-kq="mo">🌐 Mở gemini.google.com</button>
                <button class="nut" data-kq="sau">Để sau</button>
                <button class="nut nut-chinh" data-kq="luu">Lưu &amp; kết nối</button>
            </div></div>`;
        document.body.appendChild(nen);
        const o = (k) => nen.querySelector(`[data-o="${k}"]`);
        const loi = nen.querySelector('.gemini-loi');
        const nutLuu = nen.querySelector('[data-kq="luu"]');
        const dong = (kq) => { nen.remove(); resolve(kq); };

        nen.addEventListener('click', async (e) => {
            const kq = e.target.dataset && e.target.dataset.kq;
            if (kq === 'mo') { api('/api/gemini/mo-trang', { method: 'POST' }).catch(() => {}); return; }
            if (kq === 'sau') {
                try { localStorage.setItem(KHOA_BO_QUA, String(Date.now() + DE_SAU_MS)); } catch (_) { /* bỏ qua */ }
                dong(false);
                return;
            }
            if (kq !== 'luu') return;
            const psid = o('psid').value.trim().replace(/^__Secure-1PSID=?/, '');
            const psidts = o('psidts').value.trim().replace(/^__Secure-1PSIDTS=?/, '');
            if (!psid) { loi.textContent = 'Chưa dán __Secure-1PSID.'; return; }
            // Hay dán nhầm dòng khác (1PSIDCC, 1PAPISID...): __Secure-1PSID thật luôn bắt đầu bằng "g.a0" và dài ~150 ký tự.
            if (!/^g\.a0/.test(psid)) {
                loi.textContent = 'Ô thứ nhất không phải __Secure-1PSID (giá trị đúng bắt đầu bằng "g.a0..." và rất dài). '
                    + 'Kiểm tra lại cột Name là đúng __Secure-1PSID, không phải 1PSIDCC / 1PSIDRTS / 1PAPISID.';
                return;
            }
            nutLuu.disabled = true;
            loi.textContent = 'Đang kết nối Gemini...';
            try {
                const luu = await api('/api/gemini/cookie', { method: 'POST', body: { psid, psidts } });
                loi.textContent = `Đã lưu vào ${luu.cookies_json || 'cấu hình'}. Đang ping Gemini...`;
                const p = await pingGemini();
                if (p.ok) {
                    toast(`${p.thong_bao} Trả lời: "${p.tra_loi}"`, 'success', 6000);
                    dong(true);
                    return;
                }
                loi.textContent = p.thong_bao || 'Chưa kết nối được.';
            } catch (err) {
                loi.textContent = err.message;
            }
            nutLuu.disabled = false;
        });
        o('psid').focus();
    });
}

/** Gọi lúc mở app: ping Gemini bằng cookie đã lưu; cookie còn sống thì thôi, hỏng/chưa có mới hiện hộp điền
 *  (trừ khi đã bấm "Để sau" hoặc đã ping thành công trong phiên này). */
export async function kiemTraGeminiKhiMo() {
    try {
        if (Number(localStorage.getItem(KHOA_BO_QUA) || 0) > Date.now() || sessionStorage.getItem(KHOA_DA_PING)) return;
    } catch (_) { /* bỏ qua */ }
    let tt;
    try {
        tt = await api('/api/gemini/trang-thai');
        // Không dịch bằng cookie Gemini (máy mới mặc định Ollama) thì không làm phiền lúc mở app.
        if (tt.engine && tt.engine !== 'gemini_api') return;
        tt = await choTrangThai();
        // Chạy app không qua desktop.py thì proxy chưa bật — bật rồi mới ping được.
        if (tt.ma === 'da_tat') {
            await api('/api/gemini/khoi-dong-lai', { method: 'POST' });
            tt = await choTrangThai();
        }
    } catch (_) { return; }
    if (tt.ma === 'chua_co_cookie') { await moHopCookie(tt); return; }
    if (tt.ma !== 'san_sang' && tt.ma !== 'cookie_het_han') {
        if (tt.ma === 'loi') toast(`Gemini proxy lỗi: ${tt.thong_bao}`, 'error', 8000);
        return;  // không có proxy / thiếu venv / còn khởi động: không làm phiền
    }
    let p;
    try { p = await pingGemini(); } catch (_) { return; }
    if (p.ok) {
        try { sessionStorage.setItem(KHOA_DA_PING, '1'); } catch (_) { /* bỏ qua */ }
        return;
    }
    await moHopCookie({ ma: 'cookie_het_han', thong_bao: p.thong_bao });
}
