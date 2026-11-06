// Đưa lưới về toạ độ thế giới, tách phần rời, gộp nhiều lưới, ghép/khoét (CSG).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { ADDITION, Brush, Evaluator, INTERSECTION, SUBTRACTION } from 'three-bvh-csg';
import { finish, toFloatAttribute, toIndexedByPosition } from './mesh-subdivide-smooth.js';

export const meshesOf = (obj) => {
  const list = [];
  obj.traverse((m) => { if (m.isMesh) list.push(m); });
  return list;
};

export const firstMaterialOf = (mesh) => (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material);

/** Copy geometry của mesh sang toạ độ thế giới; tỉ lệ âm (lật gương) -> đảo chiều tam giác. */
export function bakeWorldGeometry(mesh) {
  mesh.updateWorldMatrix(true, false);
  const g = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(mesh.geometry.attributes)) g.setAttribute(name, toFloatAttribute(attr));
  const count = g.attributes.position.count;
  g.setIndex(mesh.geometry.index ? Array.from(mesh.geometry.index.array) : [...Array(count).keys()]);
  g.applyMatrix4(mesh.matrixWorld);
  if (mesh.matrixWorld.determinant() < 0) {
    const idx = g.index.array;
    for (let i = 0; i < idx.length; i += 3) [idx[i + 1], idx[i + 2]] = [idx[i + 2], idx[i + 1]];
  }
  return g;
}

/** Cùng bộ attribute cho mọi geometry (bắt buộc để gộp/CSG): position, normal, uv (+ color nếu có). */
export function unifyAttributes(geos) {
  const withColor = geos.some((g) => g.attributes.color);
  return geos.map((src) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', src.attributes.position);
    g.setIndex(src.index);
    if (src.attributes.normal) g.setAttribute('normal', src.attributes.normal); else g.computeVertexNormals();
    const n = src.attributes.position.count;
    g.setAttribute('uv', src.attributes.uv ?? new THREE.Float32BufferAttribute(new Float32Array(n * 2), 2));
    if (withColor) g.setAttribute('color', rgbColor(src.attributes.color, n));
    return g;
  });
}

/** Màu đỉnh RGB: model AI (trimesh) lưu RGBA -> bỏ alpha; thiếu màu -> trắng. */
function rgbColor(attr, count) {
  const out = new Float32Array(count * 3).fill(1);
  if (attr) {
    for (let i = 0; i < count; i++) {
      out[i * 3] = attr.getX(i); out[i * 3 + 1] = attr.getY(i); out[i * 3 + 2] = attr.getZ(i);
    }
  }
  return new THREE.Float32BufferAttribute(out, 3);
}

/** Cả vật (có thể nhiều mesh con) -> 1 geometry toạ độ thế giới. */
export function objectWorldGeometry(obj) {
  return mergeGeometries(unifyAttributes(meshesOf(obj).map(bakeWorldGeometry)), false);
}

/** Dời gốc toạ độ về tâm lưới để gizmo nằm giữa vật. Trả về tâm cũ. */
export function recenter(geometry) {
  geometry.computeBoundingBox();
  const center = geometry.boundingBox.getCenter(new THREE.Vector3());
  geometry.translate(-center.x, -center.y, -center.z);
  return center;
}

/** Tách các mảnh không dính nhau. Trả về danh sách geometry (mảnh lớn trước), tối đa `maxParts`. */
export function splitLooseParts(geometry, maxParts = 30) {
  const g = toIndexedByPosition(geometry);
  const idx = g.index.array;
  const parent = Uint32Array.from({ length: g.attributes.position.count }, (_, i) => i);
  const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  const unite = (a, b) => { parent[find(a)] = find(b); };
  for (let i = 0; i < idx.length; i += 3) { unite(idx[i], idx[i + 1]); unite(idx[i], idx[i + 2]); }

  const groups = new Map();
  for (let i = 0; i < idx.length; i += 3) {
    const root = find(idx[i]);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(idx[i], idx[i + 1], idx[i + 2]);
  }
  let parts = [...groups.values()].sort((a, b) => b.length - a.length);
  if (parts.length > maxParts) parts = [...parts.slice(0, maxParts - 1), parts.slice(maxParts - 1).flat()];
  return parts.map((tris) => finish(compact(g, tris)));
}

/** Geometry mới chỉ gồm các tam giác `tris` (đánh lại số đỉnh). */
function compact(g, tris) {
  const remap = new Map();
  const out = new THREE.BufferGeometry();
  const newIndex = tris.map((v) => { if (!remap.has(v)) remap.set(v, remap.size); return remap.get(v); });
  for (const [name, attr] of Object.entries(g.attributes)) {
    const size = attr.itemSize;
    const data = new Float32Array(remap.size * size);
    for (const [oldV, newV] of remap) for (let k = 0; k < size; k++) data[newV * size + k] = attr.array[oldV * size + k];
    out.setAttribute(name, new THREE.Float32BufferAttribute(data, size));
  }
  out.setIndex(newIndex);
  return out;
}

export const BOOLEAN_OPS = { union: ADDITION, subtract: SUBTRACTION, intersect: INTERSECTION };

/** Ghép / khoét / lấy phần chung của 2 geometry (toạ độ thế giới). */
export function booleanGeometry(geoA, geoB, op) {
  const [a, b] = unifyAttributes([geoA, geoB]);
  const evaluator = new Evaluator();
  evaluator.useGroups = false;
  evaluator.attributes = a.attributes.color ? ['position', 'uv', 'normal', 'color'] : ['position', 'uv', 'normal'];
  const result = evaluator.evaluate(new Brush(a), new Brush(b), BOOLEAN_OPS[op]);
  return result.geometry;
}
