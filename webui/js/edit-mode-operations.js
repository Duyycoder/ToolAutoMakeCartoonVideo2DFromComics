// Các thao tác trên vùng chọn trong chế độ "Chỉnh điểm" (xoá, đùn, tách, tô màu, làm mượt, dồn, chia nhỏ).
import * as THREE from 'three';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import * as G from './edit-mode-geometry.js';
import { recenter } from './mesh-split-merge-operations.js';
import { rememberOriginalLook } from './material-preset-library.js';
import { toast } from './toast-notifications.js';

export function createEditOperations({ state: S, apply, pushUndo, setGeometry, exit, store, transform }) {
  const anySelectedFace = () => S().selF.some(Boolean);

  function makePartMesh(part) {
    const geo = toCreasedNormals(part, Math.PI / 6);
    const world = S().mesh.matrixWorld.clone();
    geo.applyMatrix4(world);
    const center = recenter(geo);
    const mat = S().editMaterial.clone();
    Object.assign(mat, { flatShading: false, polygonOffset: false });
    const m = new THREE.Mesh(geo, mat);
    m.position.copy(center);
    m.castShadow = m.receiveShadow = true;
    m.name = store.nextName(`${S().obj.name} - phần tách`);
    m.userData.kind = 'edited';
    rememberOriginalLook(m);
    return m;
  }

  const ops = {
    deleteSelection() {
      // Chế độ điểm: xoá điểm = xoá mọi mặt dính vào điểm đó (như Blender).
      const faces = S().mode === 'face' ? S().selF : touchingFaces(S().geo, S().selV);
      if (!faces.some(Boolean)) return toast('Hãy chọn điểm hoặc mặt cần xoá.', { type: 'warn' });
      if (faces.every(Boolean)) return toast('Không thể xoá hết — muốn xoá cả vật thì bấm Xong rồi bấm Xoá.', { type: 'warn' });
      apply(() => G.deleteFaces(S().geo, faces));
    },
    extrude() {
      if (!anySelectedFace()) return toast('Hãy chọn ít nhất 1 mặt (đủ 3 điểm của mặt) để đùn ra.', { type: 'warn' });
      const r = apply(() => G.extrudeFaces(S().geo, S().selF, S().geo.boundingBox.getSize(new THREE.Vector3()).length() * 0.08));
      if (r) { transform.setMode('translate'); toast('Đã đùn ra — kéo mũi tên để kéo dài thêm.', { type: 'ok' }); }
    },
    separate() {
      if (!anySelectedFace()) return toast('Hãy chọn các mặt muốn tách ra.', { type: 'warn' });
      if (S().selF.every(Boolean)) return toast('Đang chọn cả vật — không cần tách.', { type: 'warn' });
      const { rest, part } = G.separateFaces(S().geo, S().selF);
      pushUndo({ geo: S().geo, selV: S().selV.slice() });
      setGeometry(rest);
      const newMesh = makePartMesh(part);
      exit([newMesh]);
      toast(`Đã tách thành vật mới "${newMesh.name}".`, { type: 'ok' });
    },
    colorize(hex) {
      const c = new THREE.Color(hex);
      apply(() => G.colorizeSelected(S().geo, S().selV, [c.r, c.g, c.b], [S().baseColor.r, S().baseColor.g, S().baseColor.b]));
    },
    smoothSelection() { apply(() => G.smoothSelected(S().geo, S().selV, 3)); },
    mergeSelection() { apply(() => G.mergeSelected(S().geo, S().selV), 'Chọn ít nhất 2 điểm để dồn lại.'); },
    subdivide() {
      if (G.faceCount(S().geo) > 50000) return toast('Đã đủ nhiều điểm rồi.', { type: 'warn' });
      pushUndo({ geo: S().geo, selV: S().selV.slice() });
      setGeometry(G.subdivideAll(S().geo));
    },
  };
  return ops;
}

/** Mặt có ít nhất 1 điểm được chọn (xoá điểm = xoá các mặt dính vào nó). */
function touchingFaces(g, selV) {
  const idx = g.index.array, out = new Uint8Array(idx.length / 3);
  for (let f = 0; f < out.length; f++) out[f] = selV[idx[f * 3]] | selV[idx[f * 3 + 1]] | selV[idx[f * 3 + 2]];
  return out;
}
