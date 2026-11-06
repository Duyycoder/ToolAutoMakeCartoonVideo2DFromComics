// Chế độ "Chỉnh điểm" (như Edit Mode của Blender, bản dễ dùng): chọn điểm/mặt rồi kéo, đùn, xoá...
// Trong chế độ: Undo riêng từng bước. Bấm "Xong": cả lượt chỉnh = 1 bước Undo của app.
import * as THREE from 'three';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { toIndexedByPosition } from './mesh-subdivide-smooth.js';
import * as G from './edit-mode-geometry.js';
import { createEditOverlays } from './edit-mode-overlays.js';
import { createEditTransform } from './edit-mode-transform.js';
import { boxSelect, pickElement } from './edit-mode-selection.js';
import { firstMaterialOf, meshesOf } from './mesh-split-merge-operations.js';
import { addObjectCommand, batchCommand } from './scene-edit-commands.js';
import { toast } from './toast-notifications.js';
import { createEditOperations } from './edit-mode-operations.js';

const MAX_VERTICES = 100000;
const WHITE = new THREE.Color(1, 1, 1);

export function createEditMode({ viewport, store, stack, gizmo, onChange }) {
  let s = null;
  const overlays = createEditOverlays(viewport.scene);
  const transform = createEditTransform(viewport, {
    onBegin: () => { s.dragBefore = { geo: s.geo.clone(), selV: s.selV.slice() }; },
    onEnd: () => {
      pushUndo(s.dragBefore);
      s.geo.computeVertexNormals(); s.geo.computeBoundingSphere(); s.geo.computeBoundingBox();
      refresh();
    },
  });

  const toIndexed = (geometry) => {
    const g = toIndexedByPosition(geometry);
    return G.buildGeometry(Array.from(g.attributes.position.array), g.attributes.color ? Array.from(g.attributes.color.array) : null,
      g.attributes.color?.itemSize ?? 3, Array.from(g.index.array));
  };

  function setGeometry(geo, selV = null) {
    s.geo = geo;
    s.mesh.geometry = geo;
    s.selV = selV ?? new Uint8Array(geo.attributes.position.count);
    // Có màu đỉnh (vd. vừa tô màu) -> bật vertexColors; vật vốn không có màu đỉnh thì màu nền trắng.
    const hasColor = !!geo.attributes.color;
    s.editMaterial.vertexColors = hasColor;
    s.editMaterial.color.copy(hasColor && !s.hadColors ? WHITE : s.baseColor);
    s.editMaterial.needsUpdate = true;
    overlays.rebuild(s.mesh, geo);
    refresh();
  }

  function refresh() {
    s.selF = G.facesFromVerts(s.geo, s.selV);
    overlays.showSelection(s.geo, s.selV, s.selF, s.mode);
    s.geo.computeBoundingBox();
    const size = s.geo.boundingBox.getSize(new THREE.Vector3()).length();
    const worldScale = Math.abs(s.mesh.getWorldScale(new THREE.Vector3()).x); // âm nếu vật đã lật gương
    transform.attach(s.mesh, s.selV, s.soft * size * 0.5 * worldScale);
    onChange(api.info());
  }

  function pushUndo(entry) {
    s.undo.push(entry);
    if (s.undo.length > 50) s.undo.shift();
    s.redo = [];
  }

  /** Áp dụng thao tác trả về geometry mới (hoặc null nếu không làm được). */
  function apply(fn, emptyMsg) {
    if (!s.selV.some(Boolean)) return toast(emptyMsg ?? 'Hãy chọn vài điểm trước.', { type: 'warn' });
    const result = fn();
    if (!result) return null;
    pushUndo({ geo: s.geo, selV: s.selV.slice() });
    const geo = result.geo ?? result;
    // Tô màu/làm mượt không đổi số điểm -> giữ vùng chọn để làm tiếp (không bắt chọn lại).
    const keep = geo.attributes.position.count === s.selV.length ? s.selV.slice() : null;
    setGeometry(geo, result.selV ?? keep);
    return result;
  }

  const unlock = (on) => document.body.classList.toggle('edit-mode', on);

  const api = {
    get active() { return !!s; },
    get tool() { return s?.tool; },

    enter(obj) {
      if (s) return;
      if (!obj) return toast('Hãy bấm chọn 1 vật trước.', { type: 'warn' });
      if (obj.userData.kind === 'light') return toast('Đèn không có điểm để chỉnh.', { type: 'warn' });
      const meshes = meshesOf(obj);
      if (meshes.length !== 1) {
        return toast('Vật này gồm nhiều phần — hãy "Gộp lưới" hoặc "Tách phần rời" (mục Sửa hình) trước.', { type: 'warn', timeout: 7000 });
      }
      const mesh = meshes[0];
      if (mesh.geometry.attributes.position.count > MAX_VERTICES) {
        return toast('Vật quá nhiều điểm để chỉnh từng điểm — hãy "Giảm chi tiết" trước.', { type: 'warn', timeout: 7000 });
      }
      const original = firstMaterialOf(mesh);
      if (Array.isArray(mesh.material)) toast('Vật gộp nhiều chất liệu sẽ dùng chung 1 chất liệu sau khi chỉnh.', { timeout: 6000 });
      const editMaterial = original.clone();
      Object.assign(editMaterial, { flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
      s = {
        obj, mesh, editMaterial, originalGeometry: mesh.geometry, originalMaterial: mesh.material,
        baseColor: original.color?.clone() ?? WHITE.clone(),
        hadColors: !!(original.vertexColors && mesh.geometry.attributes.color),
        mode: 'vertex', tool: 'click', soft: 0, undo: [], redo: [],
      };
      mesh.material = editMaterial;
      gizmo.setEnabled(false);
      unlock(true);
      setGeometry(toIndexed(mesh.geometry));
      toast('Đang chỉnh điểm: bấm vào điểm để chọn, kéo mũi tên để di chuyển. Xong thì bấm "Xong" hoặc Tab.', { timeout: 7000 });
    },

    /** Kết thúc: ghi cả lượt chỉnh thành 1 bước Undo. `extra`: vật mới sinh ra (vd. "Tách ra"). */
    exit(extra = []) {
      if (!s) return;
      const { mesh, originalGeometry, originalMaterial, editMaterial, undo } = s;
      transform.detach();
      overlays.dispose();
      mesh.geometry = originalGeometry;
      mesh.material = originalMaterial;
      if (undo.length || extra.length) {
        const finalGeo = toCreasedNormals(s.geo, Math.PI / 6); // cạnh sắc vẫn sắc, mặt cong vẫn mượt
        finalGeo.computeBoundingBox(); finalGeo.computeBoundingSphere();
        const finalMat = (Array.isArray(originalMaterial) ? originalMaterial[0] : originalMaterial).clone();
        finalMat.vertexColors = editMaterial.vertexColors;
        finalMat.color.copy(editMaterial.color);
        stack.execute(batchCommand('Chỉnh điểm', [
          { do: () => { mesh.geometry = finalGeo; mesh.material = finalMat; store.changed(); },
            undo: () => { mesh.geometry = originalGeometry; mesh.material = originalMaterial; store.changed(); } },
          ...extra.map((o) => addObjectCommand(store, o)),
        ]));
      }
      s = null;
      gizmo.setEnabled(true);
      unlock(false);
      store.changed();
      onChange(null);
    },

    undo() {
      const entry = s?.undo.pop();
      if (!entry) return;
      s.redo.push({ geo: s.geo, selV: s.selV.slice() });
      setGeometry(entry.geo, entry.selV);
    },
    redo() {
      const entry = s?.redo.pop();
      if (!entry) return;
      s.undo.push({ geo: s.geo, selV: s.selV.slice() });
      setGeometry(entry.geo, entry.selV);
    },

    setSelectMode(mode) { s.mode = mode; refresh(); },
    setTool(tool) { s.tool = tool; onChange(api.info()); },
    setSoft(value) { s.soft = value; refresh(); },
    setGizmoMode(mode) { transform.setMode(mode); },
    consumeGizmoPointer: () => transform.consumePointer(),

    clickSelect(clientX, clientY, additive) {
      const hit = pickElement(viewport, s.mesh, clientX, clientY);
      if (!additive) s.selV.fill(0);
      if (hit) {
        const verts = s.mode === 'vertex' ? [hit.vertex] : Array.from(s.geo.index.array.slice(hit.face * 3, hit.face * 3 + 3));
        const on = !(additive && verts.every((v) => s.selV[v])); // Shift bấm lại = bỏ chọn
        verts.forEach((v) => { s.selV[v] = on ? 1 : 0; });
      }
      refresh();
    },
    selectBox(rect, additive, throughAll) {
      if (!additive) s.selV.fill(0);
      const found = boxSelect(viewport, s.mesh, rect, s.mode, throughAll);
      const idx = s.geo.index.array;
      for (const i of found) {
        if (s.mode === 'vertex') s.selV[i] = 1;
        else for (let k = 0; k < 3; k++) s.selV[idx[i * 3 + k]] = 1;
      }
      refresh();
    },
    selectAll() { s.selV.fill(s.selV.every(Boolean) ? 0 : 1); refresh(); },
    grow() { s.selV = G.growSelection(s.geo, s.selV); refresh(); },

    info() {
      if (!s) return null;
      return {
        name: s.obj.name, mode: s.mode, tool: s.tool, soft: s.soft,
        vertices: s.selV.reduce((a, b) => a + b, 0), faces: s.selF.reduce((a, b) => a + b, 0),
        canUndo: s.undo.length > 0, canRedo: s.redo.length > 0,
      };
    },
  };

  Object.assign(api, createEditOperations({
    state: () => s, apply, pushUndo, setGeometry, exit: (extra) => api.exit(extra), store, transform,
  }));
  return api;
}
