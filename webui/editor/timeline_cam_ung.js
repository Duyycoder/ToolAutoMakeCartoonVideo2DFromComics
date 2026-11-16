/* Thao tác cảm ứng trên timeline (điện thoại/máy tính bảng) — kiểu CapCut:
   - 1 ngón vuốt: cuộn timeline (có quán tính). Chạm clip: chọn. Chạm chỗ trống: đặt đầu phát.
   - Giữ ~0,35 s trên clip: nhấc clip lên để dời (rung nhẹ báo hiệu).
   - Kéo mép clip ĐANG CHỌN: tỉa (vùng nắm mép rộng hơn — xem MEP_CHAM ở timeline.js).
   - 2 ngón: pinch-zoom — thời điểm nằm dưới điểm giữa hai ngón lúc bắt đầu luôn bám theo điểm giữa hiện tại
     (vừa zoom vừa kéo được), chặn Safari tự phóng to cả trang.
   Chuột/bút vẫn đi đường cũ của timeline.js. */
import { ZOOM_MU } from './timeline.js';
const GIU_LAU = 350;    // ms
const NGUONG_DI = 8;    // px — quá mức này là vuốt, không còn là chạm/giữ

export function ganCamUng(tl, MEP_CHAM) {
    const cuon = tl.cuon;
    const ngon = new Map();      // pointerId → {x, y}
    let viec = null;             // {loai: 'cho' | 'cuon' | 'pinch', ...}
    let quanTinh = 0;

    const huyGiu = () => { if (viec && viec.hGiu) { clearTimeout(viec.hGiu); viec.hGiu = 0; } };
    const zTuPx = (px) => Math.max(0, Math.min(1, Math.log2(px / 5) / ZOOM_MU));

    cuon.addEventListener('pointerdown', (e) => {
        if (e.pointerType !== 'touch') return;
        cancelAnimationFrame(quanTinh);
        ngon.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (ngon.size === 2) {
            huyGiu();
            const [a, b] = [...ngon.values()];
            const r = cuon.getBoundingClientRect();
            const x = (a.x + b.x) / 2 - r.left;
            viec = { loai: 'pinch', d0: Math.hypot(a.x - b.x, a.y - b.y) || 1, px0: tl.px, t: (cuon.scrollLeft + x) / tl.px, x };
            e.stopPropagation();
            return;
        }
        if (ngon.size > 2) { e.stopPropagation(); return; }
        // Thước / đầu phát: để timeline.js tua như cũ.
        if (e.target.closest('.thuoc, .dau-phat, .cc-diem')) return;
        const clip = e.target.closest('.clip');
        if (clip && !clip.classList.contains('neo') && (tl.ui.dang_chon || []).includes(clip.dataset.id)) {
            const r = clip.getBoundingClientRect();
            if (e.clientX - r.left < MEP_CHAM || r.right - e.clientX < MEP_CHAM) return;   // tỉa: timeline.js lo
        }
        e.stopPropagation();
        viec = { loai: 'cho', e, clip, x0: e.clientX, y0: e.clientY, sl: cuon.scrollLeft, st: cuon.scrollTop, vet: [] };
        if (clip && !clip.classList.contains('neo')) {
            viec.hGiu = setTimeout(() => {
                const v = viec;
                viec = null;
                navigator.vibrate?.(15);
                tl._batDauKeoClip(v.e, v.clip);   // từ đây timeline.js giữ con trỏ và dời clip
            }, GIU_LAU);
        }
    }, true);

    cuon.addEventListener('pointermove', (e) => {
        if (e.pointerType !== 'touch' || !ngon.has(e.pointerId)) return;
        ngon.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (!viec) return;
        if (viec.loai === 'pinch' && ngon.size >= 2) {
            const [a, b] = [...ngon.values()];
            viec.z = zTuPx(viec.px0 * Math.hypot(a.x - b.x, a.y - b.y) / viec.d0);
            viec.xHien = (a.x + b.x) / 2 - cuon.getBoundingClientRect().left;
            if (!viec.raf) {
                viec.raf = requestAnimationFrame(() => {
                    const v = viec;
                    if (!v || v.loai !== 'pinch') return;
                    v.raf = 0;
                    tl.datZoom(v.z, { t: v.t, x: v.xHien });
                });
            }
            return;
        }
        const dx = e.clientX - viec.x0, dy = e.clientY - viec.y0;
        if (viec.loai === 'cho' && Math.hypot(dx, dy) > NGUONG_DI) { huyGiu(); viec.loai = 'cuon'; }
        if (viec.loai === 'cuon') {
            cuon.scrollLeft = viec.sl - dx;
            cuon.scrollTop = viec.st - dy;
            viec.vet.push({ x: e.clientX, y: e.clientY, t: performance.now() });
            if (viec.vet.length > 5) viec.vet.shift();
        }
    }, true);

    const tha = (e) => {
        if (e.pointerType !== 'touch' || !ngon.has(e.pointerId)) return;
        ngon.delete(e.pointerId);
        if (!viec) return;
        huyGiu();
        const v = viec;
        if (v.loai === 'pinch') { if (!ngon.size) { viec = null; tl.ctx.luuUi(); } return; }
        viec = null;
        if (e.type === 'pointercancel') return;
        if (v.loai === 'cho') {
            // Chạm: chọn clip / đặt đầu phát ở chỗ trống.
            if (v.clip) tl.chonClip(v.clip.dataset.id);
            else if (v.e.target.closest('.tl-track, .tl-noi')) { tl.chonClip(null); tl.datDauPhat(tl._t(v.x0)); }
            return;
        }
        // Vuốt xong: trôi tiếp theo vận tốc cuối rồi chậm dần.
        const a = v.vet[0], b = v.vet[v.vet.length - 1];
        if (!a || b.t - a.t < 10) return;
        let vx = (b.x - a.x) / (b.t - a.t) * 16, vy = (b.y - a.y) / (b.t - a.t) * 16;
        const troi = () => {
            cuon.scrollLeft -= vx;
            cuon.scrollTop -= vy;
            vx *= 0.92; vy *= 0.92;
            if (Math.abs(vx) > 0.5 || Math.abs(vy) > 0.5) quanTinh = requestAnimationFrame(troi);
        };
        quanTinh = requestAnimationFrame(troi);
    };
    cuon.addEventListener('pointerup', tha, true);
    cuon.addEventListener('pointercancel', tha, true);
    // Safari iOS: pinch trên timeline không được phóng to cả trang (bỏ qua touch-action).
    for (const ten of ['gesturestart', 'gesturechange', 'gestureend']) cuon.addEventListener(ten, (e) => e.preventDefault(), { passive: false });
    cuon.addEventListener('touchmove', (e) => { if (e.touches.length > 1) e.preventDefault(); }, { passive: false });
}
