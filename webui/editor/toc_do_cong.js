/* Tốc độ clip theo ĐỒ THỊ (speed ramp) — hàm thuần, bản Python: orchestrator/editor/toc_do_cong.py.
 * Hai bản chạy chung ca test tests/js/ca_toc_do_cong.json.
 *
 * clip.toc_do_cong = [{q, v}]: q ∈ [0, 1] là vị trí trên clip ĐÃ ĐỔI tốc (thời gian timeline, chuẩn hoá),
 * v = tốc độ (×) tại đó; nối thẳng giữa các điểm. Khi có đồ thị, clip.toc_do = tốc độ TRUNG BÌNH của đồ thị
 * nên độ dài clip vẫn = (ra − vao) / toc_do như clip tốc độ cố định — mọi chỗ tính độ dài giữ nguyên.
 *
 * Vị trí nguồn: P(q) = ∫₀^q v / ∫₀¹ v ∈ [0, 1]  →  giây trong media = vao + (ra − vao)·P(q).
 * Ngoài [0, 1] (phần kéo dài cho chuyển cảnh) chạy tiếp bằng tốc độ ở mép.
 */
export const TOC_MIN = 0.1;
export const TOC_MAX = 10;

/* Mẫu đồ thị có sẵn: [q, v]. */
export const MAU_DO_THI = [
    { id: 'montage', ten: 'Montage', diem: [[0, 1], [0.18, 1], [0.3, 4], [0.45, 0.4], [0.6, 0.4], [0.78, 4], [1, 1]] },
    { id: 'anh_hung', ten: 'Anh hùng', diem: [[0, 2.5], [0.3, 2.5], [0.42, 0.25], [0.62, 0.25], [0.75, 2.5], [1, 2.5]] },
    { id: 'dan_ban', ten: 'Đạn bắn', diem: [[0, 1], [0.35, 1], [0.42, 0.15], [0.62, 0.15], [0.7, 1], [1, 1]] },
    { id: 'nhay_cat', ten: 'Nhảy cắt', diem: [[0, 1], [0.4, 1], [0.44, 8], [0.56, 8], [0.6, 1], [1, 1]] },
    { id: 'vao_nhanh', ten: 'Vào nhanh', diem: [[0, 6], [0.25, 6], [0.5, 1], [1, 1]] },
    { id: 'ra_nhanh', ten: 'Ra nhanh', diem: [[0, 1], [0.5, 1], [0.75, 6], [1, 6]] },
    { id: 'tang_dan', ten: 'Nhanh dần', diem: [[0, 0.5], [1, 3]] },
    { id: 'giam_dan', ten: 'Chậm dần', diem: [[0, 3], [1, 0.5]] },
];

const kep = (x, a, b) => Math.min(b, Math.max(a, x));
const tron = (x, k = 1e4) => Math.round(x * k) / k;

/* Sắp theo q, kẹp giá trị, bảo đảm có điểm ở q=0 và q=1. Ít hơn 2 điểm → null (không dùng đồ thị). */
export function chuan(cong) {
    if (!Array.isArray(cong) || cong.length < 2) return null;
    const d = cong.map((x) => ({ q: tron(kep(Number(x.q) || 0, 0, 1)), v: tron(kep(Number(x.v) || 1, TOC_MIN, TOC_MAX), 1e3) }))
        .sort((a, b) => a.q - b.q);
    if (d[0].q > 0) d.unshift({ q: 0, v: d[0].v });
    if (d[d.length - 1].q < 1) d.push({ q: 1, v: d[d.length - 1].v });
    return d;
}

export function tuMau(id) {
    const m = MAU_DO_THI.find((x) => x.id === id);
    return m ? chuan(m.diem.map(([q, v]) => ({ q, v }))) : null;
}

export function tocTai(cong, q) {
    if (q <= cong[0].q) return cong[0].v;
    for (let i = 1; i < cong.length; i += 1) {
        const a = cong[i - 1], b = cong[i];
        if (q <= b.q) return b.q - a.q < 1e-9 ? b.v : a.v + (b.v - a.v) * (q - a.q) / (b.q - a.q);
    }
    return cong[cong.length - 1].v;
}

/* Diện tích tích luỹ ∫₀^{q_i} v ở từng điểm. */
function tichLuy(cong) {
    const A = [0];
    for (let i = 1; i < cong.length; i += 1) A.push(A[i - 1] + (cong[i].q - cong[i - 1].q) * (cong[i].v + cong[i - 1].v) / 2);
    return A;
}

export function trungBinh(cong) {
    const A = tichLuy(cong);
    return A[A.length - 1];
}

/* q (timeline, chuẩn hoá) → P (nguồn, chuẩn hoá). */
export function nguonTai(cong, q) {
    const A = tichLuy(cong), M = A[A.length - 1];
    if (q <= 0) return q * cong[0].v / M;
    if (q >= 1) return 1 + (q - 1) * cong[cong.length - 1].v / M;
    for (let i = 1; i < cong.length; i += 1) {
        const a = cong[i - 1], b = cong[i];
        if (q <= b.q) {
            const x = q - a.q;
            return (A[i - 1] + a.v * x + (tocTai(cong, q) - a.v) * x / 2) / M;
        }
    }
    return 1;
}

/* P (nguồn, chuẩn hoá) → q: nghịch đảo nguonTai (giải phương trình bậc hai trong từng đoạn). */
export function viTriTai(cong, p) {
    const A = tichLuy(cong), M = A[A.length - 1];
    if (p <= 0) return p * M / cong[0].v;
    if (p >= 1) return 1 + (p - 1) * M / cong[cong.length - 1].v;
    const can = p * M;
    for (let i = 1; i < cong.length; i += 1) {
        if (can <= A[i] + 1e-12) {
            const a = cong[i - 1], b = cong[i], h = b.q - a.q;
            if (h < 1e-9) return a.q;
            const r = can - A[i - 1], k = (b.v - a.v) / h;
            // k/2·x² + va·x − r = 0 → x = 2r / (va + √(va² + 2kr)) (ổn định số cả khi k ≈ 0)
            return a.q + 2 * r / (a.v + Math.sqrt(Math.max(0, a.v * a.v + 2 * k * r)));
        }
    }
    return 1;
}

/* Cắt đồ thị tại q → [trái, phải], mỗi bên chuẩn hoá lại về [0, 1]. */
export function catCong(cong, q) {
    const vq = tocTai(cong, q);
    const trai = [...cong.filter((x) => x.q < q - 1e-9).map((x) => ({ q: x.q / q, v: x.v })), { q: 1, v: vq }];
    const phai = [{ q: 0, v: vq }, ...cong.filter((x) => x.q > q + 1e-9).map((x) => ({ q: (x.q - q) / (1 - q), v: x.v }))];
    return [chuan(trai), chuan(phai)];
}

/* Tốc độ trung bình làm clip.toc_do (6 chữ số — độ dài clip tính từ đây). */
export const tocTrungBinh = (cong) => Math.round(trungBinh(cong) * 1e6) / 1e6;
