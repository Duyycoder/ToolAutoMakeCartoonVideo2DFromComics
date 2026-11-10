// Chế độ "Tô vẽ": tô màu trực tiếp lên bề mặt bằng cọ, làm nhoè, hút màu, dán ảnh.
// Trong chế độ: Undo riêng từng nét. "Xong": cả lượt = 1 bước Undo của app.
import * as THREE from 'three';
import { colorAtFace, colorsFromTexture, ensureColorAttribute, fillAll, paintSphere } from './paint-brush-engine.js';
import { brushKeys } from './surface-input.js';
import { applySession, closeSurfaceSession, openSurfaceSession, pushUndo, swapAttribute } from './surface-session.js';
import { toast } from './toast-notifications.js';
import { createGhosting } from './scene-ghosting.js';

// Tô màu đỉnh nên cần đủ điểm: khối có sẵn chỉ vài chục điểm -> tự chia nhỏ khi vào chế độ.
const DENSITY = { minVertices: 30000, maxTriangles: 200000 };

export function createPaintMode({ store, stack, gizmo, onChange }) {
  let s = null;
  const ghosting = createGhosting(store); // vật khác mờ đi, không che chỗ đang sửa

  const api = {
    get active() { return !!s; },
    get state() { return s; },

    enter(obj) {
      if (s) return;
      const session = openSurfaceSession(obj, { ...DENSITY, verb: 'tô vẽ', keepUv: true });
      if (!session) return;
      const { geo, original } = session;
      const tint = original.color ?? new THREE.Color(1, 1, 1);
      // Vật chưa có màu đỉnh (hoặc vật liệu không dùng) -> bắt đầu từ vân texture, không có thì màu vật liệu.
      if (!original.vertexColors) geo.deleteAttribute('color');
      const fromTexture = !original.vertexColors && original.map && colorsFromTexture(geo, original.map, tint);
      ensureColorAttribute(geo, tint);
      if (original.map && !fromTexture) toast('Vân bề mặt sẽ được thay bằng màu tô.', { timeout: 5000 });
      const paintMaterial = Object.assign(original.clone(), { vertexColors: true, map: null });
      paintMaterial.color.set(1, 1, 1);
      s = { ...session, paintMaterial, brush: { mode: 'paint', color: '#ff5c5c', size: 0.3, strength: 0.6 } };
      applySession(s, paintMaterial);
      gizmo.setEnabled(false);
      ghosting.on(obj);
      document.body.classList.add('paint-mode');
      onChange(api.info());
      toast('Kéo chuột trái trên vật để tô. Kéo ra ngoài vật để xoay góc nhìn.', { timeout: 7000 });
    },

    exit() {
      if (!s) return;
      closeSurfaceSession(s, { stack, store, label: 'Tô vẽ', finalMaterial: s.paintMaterial.clone() });
      s = null;
      gizmo.setEnabled(true);
      ghosting.off();
      document.body.classList.remove('paint-mode');
      store.changed();
      onChange(null);
    },

    /** Lưu màu để Undo: gọi TRƯỚC nét cọ / tô hết, hoặc truyền màu cũ đã chụp sẵn (dán ảnh). */
    snapshot(colors) {
      pushUndo(s, 'color', colors);
      onChange(api.info());
    },
    undo() { if (s && swapAttribute(s, 'color', s.undo, s.redo)) onChange(api.info()); },
    redo() { if (s && swapAttribute(s, 'color', s.redo, s.undo)) onChange(api.info()); },

    /** Bán kính cọ theo toạ độ local (size 0..1 tính theo cỡ vật). */
    brushRadius() { return s.size * (0.01 + s.brush.size * 0.25); },
    paintAt(localPoint) {
      const c = new THREE.Color(s.brush.color); // tuyến tính
      return paintSphere(s.geo, localPoint, api.brushRadius(), [c.r, c.g, c.b], s.brush.strength, s.brush.mode);
    },
    fill() {
      api.snapshot();
      const c = new THREE.Color(s.brush.color);
      fillAll(s.geo, [c.r, c.g, c.b]);
    },
    setBrush(patch) { Object.assign(s.brush, patch); onChange(api.info()); },

    /** Cách dùng chuột/phím cho surface-input.js. */
    inputAdapter(onPickColor) {
      return {
        get active() { return !!s; },
        get mesh() { return s.mesh; },
        radius: () => api.brushRadius(),
        start(hit) {
          if (s.brush.mode === 'pick') {
            onPickColor(colorAtFace(s.geo, hit.face, s.mesh.worldToLocal(hit.point.clone())));
            return null;
          }
          api.snapshot();
          return 'dab';
        },
        dab: (local) => api.paintAt(local),
        keyMap: (e) => brushKeys(e, api),
      };
    },

    info() {
      if (!s) return null;
      return { name: s.obj.name, ...s.brush, canUndo: s.undo.length > 0, canRedo: s.redo.length > 0 };
    },
  };
  return api;
}
