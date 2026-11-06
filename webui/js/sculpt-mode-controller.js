// Chế độ "Nặn hình": cọ Đắp / Lõm / Kéo / Làm mượt / Làm phẳng, đối xứng trái↔phải — như nặn đất sét.
// Trong chế độ: Undo riêng từng nét. "Xong": cả lượt = 1 bước Undo của app.
import * as THREE from 'three';
import { buildNeighbors } from './mesh-subdivide-smooth.js';
import { applyGrab, beginGrab, drawBrush, flattenBrush, smoothBrush } from './sculpt-brush-engine.js';
import { applySession, closeSurfaceSession, openSurfaceSession, pushUndo, swapAttribute } from './surface-session.js';
import { brushKeys } from './surface-input.js';
import { toast } from './toast-notifications.js';
import { createGhosting } from './scene-ghosting.js';

// Nặn cần lưới dày hơn tô màu: chi tiết nhỏ cần nhiều điểm.
const DENSITY = { minVertices: 40000, maxTriangles: 250000 };
export const SCULPT_BRUSHES = ['draw', 'carve', 'grab', 'smooth', 'flatten'];

export function createSculptMode({ viewport, store, stack, gizmo, onChange }) {
  let s = null;
  const ghosting = createGhosting(store); // vật khác mờ đi, không che chỗ đang sửa

  /** Sau khi đổi vị trí đỉnh: cập nhật pháp tuyến (cho ánh sáng + hướng cọ) và BVH (cho raycast). */
  function refreshGeometry() {
    const g = s.geo;
    g.attributes.position.needsUpdate = true;
    g.computeVertexNormals();
    g.boundsTree.refit();
    g.computeBoundingSphere();
  }

  const mirror = (p) => new THREE.Vector3(2 * s.symX - p.x, p.y, p.z);

  function dabAt(local, e) {
    const { mode, strength } = s.brush;
    const r = api.brushRadius();
    const points = s.brush.symmetry ? [local, mirror(local)] : [local];
    for (const p of points) {
      if (mode === 'smooth') smoothBrush(s.geo, s.neighbors, p, r, strength);
      else if (mode === 'flatten') flattenBrush(s.geo, p, r, strength);
      else drawBrush(s.geo, p, r, strength, (mode === 'carve' ? -1 : 1) * (e.shiftKey ? -1 : 1));
    }
  }

  const api = {
    get active() { return !!s; },
    get state() { return s; },

    enter(obj) {
      if (s) return;
      const session = openSurfaceSession(obj, { ...DENSITY, verb: 'nặn hình' });
      if (!session) return;
      const material = session.original.clone();
      material.vertexColors = !!(session.original.vertexColors && session.geo.attributes.color);
      const box = session.geo.boundingBox;
      s = {
        ...session, material, neighbors: buildNeighbors(session.geo), grab: null,
        symX: (box.min.x + box.max.x) / 2, // mặt phẳng đối xứng = giữa vật (model AI có gốc lệch tâm)
        brush: { mode: 'draw', size: 0.2, strength: 0.5, symmetry: false },
      };
      applySession(s, material);
      gizmo.setEnabled(false);
      ghosting.on(obj);
      document.body.classList.add('sculpt-mode');
      onChange(api.info());
      toast('Kéo trên vật để nặn. Giữ Shift khi Đắp/Lõm để đảo chiều. Kéo ra ngoài vật để xoay góc nhìn.', { timeout: 8000 });
    },

    exit() {
      if (!s) return;
      closeSurfaceSession(s, { stack, store, label: 'Nặn hình', finalMaterial: s.material.clone() });
      s = null;
      gizmo.setEnabled(true);
      ghosting.off();
      document.body.classList.remove('sculpt-mode');
      store.changed();
      onChange(null);
    },

    undo() { if (s && swapAttribute(s, 'position', s.undo, s.redo)) { refreshGeometry(); onChange(api.info()); } },
    redo() { if (s && swapAttribute(s, 'position', s.redo, s.undo)) { refreshGeometry(); onChange(api.info()); } },

    brushRadius() { return s.size * (0.01 + s.brush.size * 0.25); },
    setBrush(patch) { Object.assign(s.brush, patch); onChange(api.info()); },

    inputAdapter() {
      return {
        get active() { return !!s; },
        get mesh() { return s.mesh; },
        radius: () => api.brushRadius(),
        start(hit) {
          pushUndo(s, 'position');
          onChange(api.info());
          if (s.brush.mode !== 'grab') return 'dab';
          // Kéo: dời vùng theo mặt phẳng song song màn hình đi qua điểm chạm.
          const local = s.mesh.worldToLocal(hit.point.clone());
          const r = api.brushRadius();
          s.grab = {
            plane: new THREE.Plane().setFromNormalAndCoplanarPoint(
              viewport.camera.getWorldDirection(new THREE.Vector3()), hit.point),
            startLocal: local,
            sets: [beginGrab(s.geo, local, r), ...(s.brush.symmetry ? [beginGrab(s.geo, mirror(local), r)] : [])],
          };
          return 'drag';
        },
        dab: dabAt,
        drag(ray) {
          const p = ray.intersectPlane(s.grab.plane, new THREE.Vector3());
          if (!p) return;
          const delta = s.mesh.worldToLocal(p).sub(s.grab.startLocal);
          applyGrab(s.geo, s.grab.sets[0], delta);
          if (s.grab.sets[1]) applyGrab(s.geo, s.grab.sets[1], delta.clone().setX(-delta.x));
        },
        flush: refreshGeometry,
        end() { s.grab = null; },
        keyMap: (e) => ({
          ...brushKeys(e, api),
          ...Object.fromEntries(SCULPT_BRUSHES.map((b, i) => [String(i + 1), () => api.setBrush({ mode: b })])),
          x: () => api.setBrush({ symmetry: !s.brush.symmetry }),
        }),
      };
    },

    info() {
      if (!s) return null;
      return { name: s.obj.name, ...s.brush, canUndo: s.undo.length > 0, canRedo: s.redo.length > 0 };
    },
  };
  return api;
}
