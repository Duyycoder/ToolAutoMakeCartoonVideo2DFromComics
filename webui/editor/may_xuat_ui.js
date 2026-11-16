/* Ô chọn "Máy xuất" (máy này / laptop GPU chạy run-worker.bat qua Tailscale) + địa chỉ, mã bí mật.
 * Dùng chung cho hộp Xuất video của editor và bước Xuất của Chạy lô (trang chủ).
 * Địa chỉ + mã lưu ở server máy này (/api/may-xuat); mã không gửi ngược về trình duyệt. */
import { api, toast } from './chung.js';

export function htmlMayXuat(chon) {
    const laptop = chon === 'laptop';
    return `<label>Máy xuất<select name="may_xuat">
                <option value="" ${laptop ? '' : 'selected'}>Máy này</option>
                <option value="laptop" ${laptop ? 'selected' : ''}>Laptop GPU qua Tailscale</option></select></label>
            <div class="o-may-xuat" ${laptop ? '' : 'hidden'}>
                <div class="hang">
                    <label>Địa chỉ laptop<input type="text" name="mx_url" placeholder="http://100.x.x.x:8300"></label>
                    <label>Mã bí mật<input type="password" name="mx_token" placeholder="dán mã từ run-worker.bat" autocomplete="off"></label>
                </div>
                <div class="hang-nut"><button type="button" class="nut nut-nho" data-mx-thu>Kiểm tra kết nối</button><span class="goi-y-nho" data-mx-tt></span></div>
            </div>`;
}

const o = (goc, ten) => goc.querySelector(`[name=${ten}]`);

/** Có thay đổi địa chỉ/mã chưa lưu không (lưu trước khi xuất). */
export function mayXuatCanLuu(goc) {
    return o(goc, 'may_xuat').value === 'laptop' && (o(goc, 'mx_token').value || o(goc, 'mx_url').value !== o(goc, 'mx_url').defaultValue);
}

export async function luuMayXuat(goc) {
    const tt = goc.querySelector('[data-mx-tt]');
    const url = o(goc, 'mx_url'), token = o(goc, 'mx_token');
    tt.textContent = 'Đang kết nối…';
    const r = await api('/api/may-xuat', { method: 'POST', body: { url: url.value, token: token.value } });
    token.value = '';
    token.placeholder = 'đã lưu — nhập để đổi';
    url.defaultValue = url.value;
    tt.textContent = r.ok ? `✔ ${r.may || 'Laptop'} sẵn sàng${r.nvenc ? ' · NVENC' : ' · không có NVENC'}` : `✘ ${r.loi}`;
    return r;
}

export function ganMayXuat(goc, khiDoi = () => {}) {
    const chon = o(goc, 'may_xuat'), khoi = goc.querySelector('.o-may-xuat');
    chon.addEventListener('change', () => { khoi.hidden = chon.value !== 'laptop'; khiDoi(chon.value); });
    goc.querySelector('[data-mx-thu]').addEventListener('click', () => luuMayXuat(goc).catch((e) => toast(e.message, 'error')));
    api('/api/may-xuat').then((c) => {
        o(goc, 'mx_url').value = o(goc, 'mx_url').defaultValue = c.url || '';
        if (c.co_token) o(goc, 'mx_token').placeholder = 'đã lưu — nhập để đổi';
    }).catch(() => {});
}
