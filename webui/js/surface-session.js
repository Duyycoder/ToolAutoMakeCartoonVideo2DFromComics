// Phiên chỉnh BỀ MẶT dùng chung cho "Tô vẽ" và "Nặn hình": kiểm tra vật, chia nhỏ lưới đủ dày,
// BVH để raycast nhanh khi kéo chuột liên tục, Undo theo từng nét (chụp 1 attribute), kết thúc = 1 bước Undo app.
import * as THREE from 'three';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { acceleratedRaycast, computeBoundsTree, disposeBoundsTree } from 'three-mesh-bvh';
import { densify, toIndexedByPosition } from './mesh-subdivide-smooth.js';
import { firstMaterialOf, meshesOf } from './mesh-split-merge-operations.js';
import { batchCommand } from './scene-edit-commands.js';
import { toast } from './toast-notifications.js';

const MAX_UNDO = 40;
const MAX_TRIANGLES_TO_EDIT = 600000; // nặng hơn -> mỗi nét cọ quá chậm

export function enableBVH(geo) {
  geo.computeBoundsTree = computeBoundsTree;
  geo.disposeBoundsTree = disposeBoundsTree;
  geo.computeBoundsTree();
}

/** Mở phiên trên vật `obj`; trả về null (kèm thông báo) nếu vật không hợp lệ. */
export function openSurfaceSession(obj, { minVertices, maxTriangles, verb }) {
  if (!obj) { toast('Hãy bấm chọn 1 vật trước.', { type: 'warn' }); return null; }
  if (obj.userData.kind === 'light') { toast(`Đèn không ${verb} được.`, { type: 'warn' }); return null; }
  const meshes = meshesOf(obj);
  if (meshes.length !== 1) {
    toast(`Vật này gồm nhiều phần — hãy "Gộp lưới" trước khi ${verb}.`, { type: 'warn', timeout: 7000 });
    return null;
  }
  const mesh = meshes[0];
  const tris = (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3;
  if (tris > MAX_TRIANGLES_TO_EDIT) {
    toast(`Vật quá nặng (${Math.round(tris).toLocaleString('vi-VN')} tam giác) — hãy "Giảm chi tiết" (mục Sửa hình) trước khi ${verb}.`,
      { type: 'warn', timeout: 8000 });
    return null;
  }
  const geo = densify(toIndexedByPosition(mesh.geometry), minVertices, maxTriangles);
  geo.computeVertexNormals();
  enableBVH(geo);
  geo.computeBoundingBox();
  return {
    obj, mesh, geo, original: firstMaterialOf(mesh),
    originalGeometry: mesh.geometry, originalMaterial: mesh.material, originalRaycast: mesh.raycast,
    size: geo.boundingBox.getSize(new THREE.Vector3()).length(), // cố định cỡ cọ dù vật phồng/xẹp
    undo: [], redo: [],
  };
}

/** Gắn geometry/material phiên vào vật. */
export function applySession(s, material) {
  s.mesh.geometry = s.geo;
  s.mesh.material = material;
  s.mesh.raycast = acceleratedRaycast;
}

/** Trả vật về như cũ; nếu có thay đổi -> ghi 1 bước Undo của app với geometry/material mới. */
export function closeSurfaceSession(s, { stack, store, label, finalMaterial }) {
  const { mesh, geo, originalGeometry, originalMaterial, originalRaycast } = s;
  mesh.geometry = originalGeometry;
  mesh.material = originalMaterial;
  mesh.raycast = originalRaycast;
  geo.disposeBoundsTree();
  if (!s.undo.length) return;
  const finalGeo = toCreasedNormals(geo, Math.PI / 6);
  finalGeo.computeBoundingBox();
  finalGeo.computeBoundingSphere();
  stack.execute(batchCommand(label, [{
    do: () => { mesh.geometry = finalGeo; mesh.material = finalMaterial; store.changed(); },
    undo: () => { mesh.geometry = originalGeometry; mesh.material = originalMaterial; store.changed(); },
  }]));
}

/** Chụp attribute (vd. 'color' khi tô, 'position' khi nặn) để Undo. Truyền `data` nếu đã chụp sẵn. */
export function pushUndo(s, name, data = s.geo.attributes[name].array.slice()) {
  s.undo.push(data);
  if (s.undo.length > MAX_UNDO) s.undo.shift();
  s.redo = [];
}

/** Undo/Redo: đổi chỗ dữ liệu attribute giữa 2 ngăn. Trả về true nếu có đổi. */
export function swapAttribute(s, name, from, to) {
  const data = from?.pop();
  if (!data) return false;
  const attr = s.geo.attributes[name];
  to.push(attr.array.slice());
  attr.array.set(data);
  attr.needsUpdate = true;
  return true;
}
