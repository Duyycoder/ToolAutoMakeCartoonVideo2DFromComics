// "Dán ảnh": ảnh hiện nổi trên khung 3D (kéo để dời, thanh trượt để đổi cỡ/độ đậm), bấm Dán thì
// ảnh được chiếu lên mặt vật đang quay về phía camera. Xoay camera trước để chọn mặt cần dán.
import * as THREE from 'three';
import { projectImage } from './paint-brush-engine.js';
import { toast } from './toast-notifications.js';

const MAX_SIDE = 1024;

export function createImagePlacement(viewport, paintMode, viewportEl, onChange) {
  const overlay = Object.assign(document.createElement('div'), { className: 'image-placement', hidden: true });
  const img = document.createElement('img');
  overlay.append(img);
  viewportEl.append(overlay);
  let st = null; // { imageData, cx, cy, baseW, baseH, scale, opacity, url }

  function layout() {
    const w = st.baseW * st.scale, h = st.baseH * st.scale;
    Object.assign(overlay.style, { left: `${st.cx - w / 2}px`, top: `${st.cy - h / 2}px`, width: `${w}px`, height: `${h}px` });
    img.style.opacity = st.opacity;
  }

  /** Khung màn hình (toạ độ trong viewportEl) bao quanh vật đang tô. */
  function objectScreenBox() {
    const box = new THREE.Box3().setFromObject(paintMode.state.mesh);
    const v = viewportEl.getBoundingClientRect(), c = viewport.renderer.domElement.getBoundingClientRect();
    const xs = [], ys = [];
    for (let i = 0; i < 8; i++) {
      const p = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z)
        .project(viewport.camera);
      xs.push(c.left - v.left + (p.x + 1) / 2 * c.width);
      ys.push(c.top - v.top + (1 - p.y) / 2 * c.height);
    }
    return { cx: (Math.min(...xs) + Math.max(...xs)) / 2, cy: (Math.min(...ys) + Math.max(...ys)) / 2,
      w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  }

  let drag = null;
  overlay.addEventListener('pointerdown', (e) => {
    drag = { x: e.clientX, y: e.clientY, cx: st.cx, cy: st.cy };
    overlay.setPointerCapture(e.pointerId);
    e.stopPropagation();
  });
  overlay.addEventListener('pointermove', (e) => {
    if (!drag) return;
    st.cx = drag.cx + e.clientX - drag.x;
    st.cy = drag.cy + e.clientY - drag.y;
    layout();
  });
  overlay.addEventListener('pointerup', () => { drag = null; });

  const api = {
    get active() { return !!st; },
    async open(file) {
      let bitmap;
      try { bitmap = await createImageBitmap(file); } catch { return toast(`Không đọc được ảnh "${file.name}".`, { type: 'err' }); }
      const k = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
      const canvas = Object.assign(document.createElement('canvas'), { width: Math.round(bitmap.width * k), height: Math.round(bitmap.height * k) });
      const g = canvas.getContext('2d');
      g.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      const box = objectScreenBox();
      const fit = Math.min(box.w / canvas.width, box.h / canvas.height) * 0.8; // vừa trong vật
      if (st?.url) URL.revokeObjectURL(st.url);
      st = { imageData: g.getImageData(0, 0, canvas.width, canvas.height), cx: box.cx, cy: box.cy,
        baseW: canvas.width * fit, baseH: canvas.height * fit, scale: 1, opacity: 1, url: URL.createObjectURL(file) };
      img.src = st.url;
      overlay.hidden = false;
      layout();
      onChange();
    },
    setScale(v) { st.scale = v; layout(); },
    setOpacity(v) { st.opacity = v; layout(); },
    get values() { return st ? { scale: st.scale, opacity: st.opacity } : null; },

    apply() {
      const before = paintMode.state.geo.attributes.color.array.slice();
      const n = projectImage(paintMode.state.mesh, viewport.camera, viewport.renderer.domElement.getBoundingClientRect(),
        overlay.getBoundingClientRect(), st.imageData, st.opacity);
      api.cancel();
      if (n) {
        paintMode.snapshot(before);
        toast(`Đã dán ảnh lên ${n.toLocaleString('vi-VN')} điểm. Xoay vật rồi dán tiếp mặt khác nếu cần.`, { type: 'ok', timeout: 6000 });
      } else { toast('Ảnh không nằm trên mặt nào của vật — kéo ảnh vào vật rồi dán lại.', { type: 'warn' }); }
    },
    cancel() {
      if (st?.url) URL.revokeObjectURL(st.url);
      st = null;
      overlay.hidden = true;
      onChange();
    },
  };
  return api;
}
