/* Chuyển cảnh trên thiết bị — ghép khung A (clip trước) và B (clip sau) theo tiến độ p ∈ [0, 1], cùng hướng với
   xfade của ffmpeg (đã đo bằng khung màu: wipeleft → B hiện từ mép PHẢI, wiperight → từ mép TRÁI, wipeup → từ DƯỚI,
   wipedown → từ TRÊN; slide* cùng hướng nhưng đẩy A ra; squeezeh/v ép A về giữa).
   KIEU_CHINH_XAC vẽ khớp; kiểu khác vẽ gần giống (phan_loai.js báo trước). */
export const KIEU_CHINH_XAC = new Set(['fade', 'dissolve', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
    'slideleft', 'slideright', 'slideup', 'slidedown']);

const em = (x) => x * x * (3 - 2 * x);     // smoothstep cho kiểu "smooth*"

/* Vẽ lên ctx (W×H) từ hai canvas khung đầy đủ A, B. */
export function veChuyenCanh(ctx, A, B, loai, p, W, H) {
    p = Math.max(0, Math.min(1, p));
    ctx.save();
    const ve = (src, x = 0, y = 0, w = W, h = H) => ctx.drawImage(src, x, y, w, h);
    const vung = (x, y, w, h, src = B) => { ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); ve(src); ctx.restore(); };
    switch (loai) {
        case 'wipeleft': case 'smoothleft': { const q = loai[0] === 's' ? em(p) : p; ve(A); vung(W * (1 - q), 0, W * q, H); break; }
        case 'wiperight': case 'smoothright': { const q = loai[0] === 's' ? em(p) : p; ve(A); vung(0, 0, W * q, H); break; }
        case 'wipeup': case 'smoothup': { const q = loai[0] === 's' ? em(p) : p; ve(A); vung(0, H * (1 - q), W, H * q); break; }
        case 'wipedown': case 'smoothdown': { const q = loai[0] === 's' ? em(p) : p; ve(A); vung(0, 0, W, H * q); break; }
        case 'slideleft': ve(A, -W * p); ve(B, W * (1 - p)); break;
        case 'slideright': ve(A, W * p); ve(B, -W * (1 - p)); break;
        case 'slideup': ve(A, 0, -H * p); ve(B, 0, H * (1 - p)); break;
        case 'slidedown': ve(A, 0, H * p); ve(B, 0, -H * (1 - p)); break;
        case 'squeezeh': ve(B); ve(A, 0, H * p / 2, W, H * (1 - p)); break;
        case 'squeezev': ve(B); ve(A, W * p / 2, 0, W * (1 - p), H); break;
        case 'fadeblack': case 'fadewhite': {
            ctx.fillStyle = loai === 'fadeblack' ? '#000' : '#fff';
            ctx.fillRect(0, 0, W, H);
            ctx.globalAlpha = p < 0.5 ? 1 - em(Math.min(1, p / 0.2)) : em(Math.max(0, (p - 0.8) / 0.2));
            ve(p < 0.5 ? A : B);
            break;
        }
        case 'circleopen': case 'circleclose': case 'circlecrop': {
            const r = Math.hypot(W, H) / 2 * (loai === 'circleclose' ? 1 - p : p);
            ve(loai === 'circleclose' ? B : A);
            ctx.beginPath(); ctx.arc(W / 2, H / 2, Math.max(0, r), 0, Math.PI * 2); ctx.clip();
            ve(loai === 'circleclose' ? A : B);
            break;
        }
        case 'diagtl': case 'diagtr': case 'diagbl': case 'diagbr': {
            const dx = loai.endsWith('l') ? 0 : W, dy = loai[4] === 't' ? 0 : H, s = 2 * p;
            ve(A);
            ctx.beginPath(); ctx.moveTo(dx, dy); ctx.lineTo(dx + (dx ? -1 : 1) * W * s, dy); ctx.lineTo(dx, dy + (dy ? -1 : 1) * H * s); ctx.clip();
            ve(B);
            break;
        }
        case 'zoomin': {
            const k = 1 + p;
            ve(A, W * (1 - k) / 2, H * (1 - k) / 2, W * k, H * k);
            ctx.globalAlpha = em(Math.max(0, (p - 0.5) * 2));
            ve(B);
            break;
        }
        default:            // fade, dissolve, pixelize, radial, *slice, distance… → hoà tan
            ve(A);
            ctx.globalAlpha = p;
            ve(B);
    }
    ctx.restore();
}
