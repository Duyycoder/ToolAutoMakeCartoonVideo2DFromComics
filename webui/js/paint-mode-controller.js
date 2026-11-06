// Chế độ "Tô vẽ": tô màu trực tiếp lên bề mặt bằng cọ, làm nhoè, hút màu, dán ảnh.
// Trong chế độ: Undo riêng từng nét. "Xong": cả lượt = 1 bước Undo của app.
import * as THREE from 'three';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { acceleratedRaycast, computeBoundsTree, disposeBoundsTree } from 'three-mesh-bvh';
import { densify, toIndexedByPosition } from './mesh-subdivide-smooth.js';
import { ensureColorAttribute, fillAll, paintSphere } from './paint-brush-engine.js';
import { firstMaterialOf, meshesOf } from './mesh-split-merge-operations.js';
import { batchCommand } from './scene-edit-commands.js';
import { toast } from './toast-notifications.js';

// Tô màu đỉnh nên cần đủ điểm: khối có sẵn chỉ vài chục điểm -> tự chia nhỏ khi vào chế độ.
const MIN_VERTICES = 30000, MAX_TRIANGLES = 200000;

export function createPaintMode({ viewport, store, stack, gizmo, onChange }) {
  let s = null;

  const api = {
    get active() { return !!s; },
    get state() { return s; },

    enter(obj) {
      if (s) return;
      if (!obj) return toast('Hãy bấm chọn 1 vật trước.', { type: 'warn' });
      if (obj.userData.kind === 'light') return toast('Đèn không tô màu được.', { type: 'warn' });
      const meshes = meshesOf(obj);
      if (meshes.length !== 1) {
        return toast('Vật này gồm nhiều phần — hãy "Gộp lưới" trước khi tô vẽ.', { type: 'warn', timeout: 7000 });
      }
      const mesh = meshes[0];
      const original = firstMaterialOf(mesh);
      const geo = densify(toIndexedByPosition(mesh.geometry), MIN_VERTICES, MAX_TRIANGLES);
      // Vật chưa có màu đỉnh (hoặc vật liệu không dùng) -> bắt đầu từ màu vật liệu hiện tại.
      if (!original.vertexColors) geo.deleteAttribute('color');
      ensureColorAttribute(geo, original.color ?? new THREE.Color(1, 1, 1));
      geo.computeVertexNormals();
      geo.computeBoundsTree = computeBoundsTree;
      geo.disposeBoundsTree = disposeBoundsTree;
      geo.computeBoundsTree(); // raycast nhanh trên lưới dày (vẽ liên tục mỗi lần di chuột)
      if (original.map) toast('Vân bề mặt sẽ được thay bằng màu tô.', { timeout: 5000 });

      const paintMaterial = original.clone();
      Object.assign(paintMaterial, { vertexColors: true, map: null });
      paintMaterial.color.set(1, 1, 1);
      s = {
        obj, mesh, geo, paintMaterial, originalGeometry: mesh.geometry, originalMaterial: mesh.material,
        originalRaycast: mesh.raycast, undo: [], redo: [],
        brush: { mode: 'paint', color: '#ff5c5c', size: 0.3, strength: 0.6 },
      };
      mesh.geometry = geo;
      mesh.material = paintMaterial;
      mesh.raycast = acceleratedRaycast;
      gizmo.setEnabled(false);
      document.body.classList.add('paint-mode');
      onChange(api.info());
      toast('Kéo chuột trái trên vật để tô. Kéo ra ngoài vật để xoay góc nhìn.', { timeout: 7000 });
    },

    exit() {
      if (!s) return;
      const { mesh, geo, paintMaterial, originalGeometry, originalMaterial, originalRaycast, undo } = s;
      mesh.geometry = originalGeometry;
      mesh.material = originalMaterial;
      mesh.raycast = originalRaycast;
      geo.disposeBoundsTree();
      if (undo.length) {
        const finalGeo = toCreasedNormals(geo, Math.PI / 6);
        finalGeo.computeBoundingBox(); finalGeo.computeBoundingSphere();
        const finalMat = paintMaterial.clone();
        stack.execute(batchCommand('Tô vẽ', [{
          do: () => { mesh.geometry = finalGeo; mesh.material = finalMat; store.changed(); },
          undo: () => { mesh.geometry = originalGeometry; mesh.material = originalMaterial; store.changed(); },
        }]));
      }
      s = null;
      gizmo.setEnabled(true);
      document.body.classList.remove('paint-mode');
      store.changed();
      onChange(null);
    },

    /** Lưu màu để Undo: gọi TRƯỚC nét cọ / tô hết, hoặc truyền màu cũ đã chụp sẵn (dán ảnh). */
    snapshot(colors = s.geo.attributes.color.array.slice()) {
      s.undo.push(colors);
      if (s.undo.length > 40) s.undo.shift();
      s.redo = [];
      onChange(api.info());
    },
    undo() { swap(s?.undo, s?.redo); },
    redo() { swap(s?.redo, s?.undo); },

    /** Bán kính cọ theo toạ độ local (size 0..1 tính theo cỡ vật). */
    brushRadius() {
      s.geo.computeBoundingBox();
      return s.geo.boundingBox.getSize(new THREE.Vector3()).length() * (0.01 + s.brush.size * 0.25);
    },
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

    info() {
      if (!s) return null;
      return { name: s.obj.name, ...s.brush, canUndo: s.undo.length > 0, canRedo: s.redo.length > 0 };
    },
  };

  function swap(from, to) {
    const colors = from?.pop();
    if (!colors) return;
    to.push(s.geo.attributes.color.array.slice());
    s.geo.attributes.color.array.set(colors);
    s.geo.attributes.color.needsUpdate = true;
    onChange(api.info());
  }

  return api;
}
