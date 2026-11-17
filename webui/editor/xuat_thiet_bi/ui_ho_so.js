/* Hộp Xuất › Thiết bị này: dùng hồ sơ máy (ho_so_may.js — số đo thật) để chỉ ra codec/độ phân giải máy làm được,
   ước lượng thời gian xuất từng lựa chọn, nút đo (lại). Hàm tính là hàm thuần (test Node). */
import { esc } from '../chung.js';
import { CODEC, DO_PHAN_GIAI } from './ho_so_may.js';

export const HE_SO_GHEP = 1.5;      // giải mã nguồn + ghép khung tốn thêm so với chỉ mã hoá (số đo hồ sơ)

/* Mục hồ sơ cho codec ở khung W×H: mục đo nhỏ nhất có số điểm ảnh ≥ W×H (khung dọc 1080×1920 = mục 1080p). */
export function mucChoKhung(hs, codec, W, H) {
    if (!hs || !hs.ma_hoa) return null;
    const dpg = DO_PHAN_GIAI.find(([, w, h]) => w * h >= W * H * 0.98);
    if (!dpg) return { codec, nhan: false, loi: 'lớn hơn 4K' };
    return hs.ma_hoa.find((m) => m.codec === codec && m.do_phan_giai === dpg[0]) || null;
}

/* {lam_duoc, giay (ước lượng thời gian xuất), chu} cho một lựa chọn; hs null (chưa đo) → không biết. */
export function danhGia(hs, codec, W, H, fps, giayVideo) {
    const m = mucChoKhung(hs, codec, W, H);
    if (!m) return { lam_duoc: null, giay: null, chu: '' };
    if (!m.nhan) return { lam_duoc: false, giay: null, chu: 'máy không mã hoá được' };
    if (m.loi || m.khung_giay === 0) return { lam_duoc: false, giay: null, chu: `lỗi khi chạy thử${m.loi ? `: ${m.loi}` : ''}` };
    if (!m.khung_giay) return { lam_duoc: true, giay: null, chu: 'chưa đo tốc độ' };
    const giay = Math.round(giayVideo * fps / m.khung_giay * HE_SO_GHEP);
    const quaCham = giay > giayVideo * 10;
    return { lam_duoc: !quaCham, giay, chu: quaCham ? `quá chậm (~${fmtGiay(giay)})` : `~${fmtGiay(giay)}${m.phan_cung ? '' : ' · mã hoá bằng CPU'}` };
}

export function fmtGiay(s) {
    if (s < 90) return `${Math.max(1, Math.round(s))} giây`;
    if (s < 5400) return `${Math.round(s / 60)} phút`;
    return `${(s / 3600).toFixed(1)} giờ`;
}

/* Tóm tắt hồ sơ: mỗi codec → độ phân giải lớn nhất máy làm được + tốc độ ở mức đó. */
export function tomTat(hs) {
    if (!hs || !hs.ma_hoa) return '';
    return CODEC.map(([k, ten]) => {
        const ok = hs.ma_hoa.filter((m) => m.codec === k && m.nhan && !m.loi && m.khung_giay !== 0);
        const top = ok[ok.length - 1];
        return top ? `${ten} tới ${top.do_phan_giai.toUpperCase()}${top.khung_giay ? ` (${top.khung_giay} khung/s)` : ''}` : `${ten}: không`;
    }).join(' · ');
}

/* HTML phần hồ sơ trong ô Thiết bị: chọn codec + tóm tắt + nút đo. */
export function htmlHoSo(hs, codec) {
    const coDo = !!(hs && hs.ma_hoa);
    const lam = (k) => !coDo || hs.ma_hoa.some((m) => m.codec === k && m.nhan && !m.loi && m.khung_giay !== 0);
    return `<div class="hang">
            <label>Codec<select name="codec_tb">${CODEC.map(([k, ten]) => `<option value="${k}" ${k === codec ? 'selected' : ''} ${lam(k) ? '' : 'disabled'}>${ten}${k === 'avc' ? ' (phát được mọi nơi)' : k === 'hevc' ? ' (nhẹ hơn ~40 %)' : ' (nhẹ nhất, máy mới)'}</option>`).join('')}</select></label>
        </div>
        <div class="goi-y-nho">${coDo ? `Máy này (đo ${new Date(hs.luc).toLocaleDateString('vi-VN')}): ${esc(tomTat(hs))}` : 'Chưa đo khả năng máy — đo để biết máy xuất được tới đâu và mất bao lâu.'}
            <button type="button" class="nut nut-nho" data-do-may>${coDo ? 'Đo lại' : 'Đo máy (~30 giây)'}</button> <span data-do-tt></span></div>`;
}

/* Ghi ước lượng / "không làm được" vào từng lựa chọn độ phân giải của hộp Xuất. kichThuoc(luaChon) → [W, H]. */
export function ghiLenDoPhanGiai(sel, hs, codec, fps, giayVideo, kichThuoc) {
    for (const o of sel.options) {
        if (o.dataset.goc == null) o.dataset.goc = o.textContent;
        const [W, H] = kichThuoc(o.value);
        const d = danhGia(hs, codec, W, H, fps, giayVideo);
        o.textContent = d.chu ? `${o.dataset.goc} — ${d.chu}` : o.dataset.goc;
    }
}

/* Bỏ chú thích (khi đổi sang máy xuất khác). */
export function xoaChuThich(sel) {
    for (const o of sel.options) if (o.dataset.goc != null) o.textContent = o.dataset.goc;
}
