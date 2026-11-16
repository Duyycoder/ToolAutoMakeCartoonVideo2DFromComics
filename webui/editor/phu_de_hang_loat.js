/* Tạo phụ đề (Whisper) cho NHIỀU video một lần: chọn trong danh sách media của dự án (không cần có trên
 * timeline — câu neo theo giờ trong media, kéo video xuống sau vẫn hiện), xếp mỗi video một việc vào hàng đợi GPU.
 * Việc chạy lần lượt trên server; xong việc nào tự đưa phụ đề của video đó vào timeline (như tạo từng video). */
import { esc, hoi, toast, fmtNgan } from './chung.js';
import { cauCuaMedia } from './store.js';
import { NGON_NGU, layModelWhisperMacDinh } from './bang_ai.js';

/** Media tạo phụ đề được: video/âm thanh đã nhập xong, còn file. */
export function mediaTaoPhuDeDuoc(ctx) {
    return (ctx.media || []).filter((m) => ['video', 'audio'].includes(m.loai) && m.trang_thai === 'san_sang' && !m.mat_file);
}

/**
 * Mở hộp chọn video rồi xếp việc 'phu-de' cho từng video được tick.
 * @param midsGoiY danh sách id tick sẵn (vd các mục đang chọn ở bảng media); null = tick video chưa có phụ đề.
 */
export async function taoPhuDeNhieu(ctx, bangAi, midsGoiY = null) {
    const ds = mediaTaoPhuDeDuoc(ctx);
    if (!ds.length) { toast('Dự án chưa có video/âm thanh nào nhập xong.', 'warn'); return; }
    const c = bangAi.cai;
    const tl = ctx.store.timeline;
    const soCau = new Map(ds.map((m) => [m.id, cauCuaMedia(tl, m.id).length]));
    const tick = (m) => (midsGoiY ? midsGoiY.includes(m.id) : !soCau.get(m.id));
    const nn = c.ngon_ngu_noi || 'Chinese';
    const html = `<div class="pd-nhieu">
        <label>Ngôn ngữ nói<select data-pd="nn">${NGON_NGU.map(([v, t]) => `<option value="${v}" ${v === nn ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
        <div class="hang-nut"><button type="button" class="nut nut-nho" data-pd="het">Chọn hết</button>
            <button type="button" class="nut nut-nho" data-pd="bo">Bỏ chọn</button></div>
        <div class="pd-nhieu-ds">${ds.map((m) => `<label class="check"><input type="checkbox" value="${esc(m.id)}" ${tick(m) ? 'checked' : ''}>
            <span>${m.loai === 'video' ? '🎬' : '🎵'} ${esc(m.ten || m.file)}
            <small class="goi-y-nho">${m.thoi_luong ? fmtNgan(m.thoi_luong) : ''}${soCau.get(m.id) ? ` · đã có ${soCau.get(m.id)} câu (sẽ bị thay)` : ''}</small></span></label>`).join('')}</div>
        <p class="goi-y-nho">Dùng model + Demucs đang chọn ở bảng AI. Các video chạy lần lượt; xong video nào phụ đề tự vào timeline video đó.</p></div>`;
    const cho = hoi({ tieuDe: 'Tạo phụ đề cho nhiều video', html, nut: 'Tạo phụ đề' });
    // hoi() gắn hộp vào DOM ngay (đồng bộ) → giữ tham chiếu ô tick trước khi hộp bị gỡ lúc bấm nút.
    const hop = [...document.querySelectorAll('.pd-nhieu')].pop();
    const o = [...hop.querySelectorAll('input[type=checkbox]')];
    const chonNn = hop.querySelector('[data-pd=nn]');
    hop.addEventListener('click', (e) => {
        const b = e.target.closest('[data-pd=het],[data-pd=bo]');
        if (b) o.forEach((x) => { x.checked = b.dataset.pd === 'het'; });
    });
    if (!(await cho)) return;
    const mids = o.filter((x) => x.checked).map((x) => x.value);
    if (!mids.length) { toast('Chưa chọn video nào.', 'warn'); return; }
    if (chonNn.value !== c.ngon_ngu_noi) {
        // Đổi ngôn ngữ thì model mặc định theo ngôn ngữ mới (PhoWhisper chỉ cho tiếng Việt).
        c.ngon_ngu_noi = chonNn.value;
        c.whisper_model = layModelWhisperMacDinh(chonNn.value);
        ctx.luuUi();
    }
    let ok = 0;
    for (const mid of mids) {
        try { await bangAi.chay('phu-de', mid, null, true); ok += 1; } catch (e) {
            const m = ds.find((x) => x.id === mid);
            toast(`${m ? m.ten : mid}: ${e.message}`, 'error', 6000);
        }
    }
    if (ok) toast(`Đã xếp ${ok} video vào hàng đợi tạo phụ đề — tiến độ ở cuối bảng AI.`, 'success', 4000);
    bangAi.tai();
}
