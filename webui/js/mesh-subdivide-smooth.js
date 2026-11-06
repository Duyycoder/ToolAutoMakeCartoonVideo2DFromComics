// Chia nhỏ lưới, làm mượt (Taubin), giảm chi tiết — hàm thuần trên BufferGeometry.
import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { SimplifyModifier } from 'three/addons/modifiers/SimplifyModifier.js';

const GETTERS = ['getX', 'getY', 'getZ', 'getW'];

/** Copy attribute ra Float32 thường (bỏ interleaved/normalized — getX tự giải chuẩn hoá). */
export function toFloatAttribute(attr) {
  const size = attr.itemSize;
  const out = new Float32Array(attr.count * size);
  for (let i = 0; i < attr.count; i++) {
    for (let k = 0; k < size; k++) out[i * size + k] = attr[GETTERS[k]](i);
  }
  return new THREE.Float32BufferAttribute(out, size);
}

/**
 * Geometry có index, gộp các đỉnh trùng vị trí. Bỏ normal/uv: chúng làm đỉnh ở cạnh sắc bị tách
 * (hộp có 24 đỉnh thay vì 8) -> làm mượt/nặn sẽ xé rách bề mặt.
 */
export function toIndexedByPosition(geometry, keep = ['position', 'color']) {
  const g = new THREE.BufferGeometry();
  for (const name of keep) {
    if (geometry.attributes[name]) g.setAttribute(name, toFloatAttribute(geometry.attributes[name]));
  }
  if (geometry.index) g.setIndex(Array.from(geometry.index.array));
  return mergeVertices(g, 1e-4);
}

/** Mỗi tam giác -> 4 tam giác (điểm giữa cạnh dùng chung). Nội suy mọi attribute. */
export function subdivide(geometry) {
  const index = geometry.index.array;
  const arrays = Object.entries(geometry.attributes)
    .map(([name, a]) => ({ name, size: a.itemSize, data: Array.from(a.array) }));
  let next = geometry.attributes.position.count;
  const mids = new Map();
  const midpoint = (a, b) => {
    const key = Math.min(a, b) * 16777216 + Math.max(a, b);
    let m = mids.get(key);
    if (m === undefined) {
      m = next++;
      for (const arr of arrays) {
        for (let k = 0; k < arr.size; k++) arr.data.push((arr.data[a * arr.size + k] + arr.data[b * arr.size + k]) / 2);
      }
      mids.set(key, m);
    }
    return m;
  };
  const out = [];
  for (let i = 0; i < index.length; i += 3) {
    const [a, b, c] = [index[i], index[i + 1], index[i + 2]];
    const ab = midpoint(a, b), bc = midpoint(b, c), ca = midpoint(c, a);
    out.push(a, ab, ca, ab, b, bc, ca, bc, c, ab, bc, ca);
  }
  const g = new THREE.BufferGeometry();
  for (const arr of arrays) g.setAttribute(arr.name, new THREE.Float32BufferAttribute(arr.data, arr.size));
  g.setIndex(out);
  return g;
}

/** Chia nhỏ tới khi đủ đỉnh để làm mượt/nặn đẹp (khối có sẵn chỉ vài chục đỉnh). */
export function densify(geometry, minVertices = 3000, maxTriangles = 60000) {
  let g = geometry;
  for (let i = 0; i < 5 && g.attributes.position.count < minVertices && g.index.count / 3 * 4 <= maxTriangles; i++) {
    g = subdivide(g);
  }
  return g;
}

/** Danh sách đỉnh kề của từng đỉnh (từ index). */
export function buildNeighbors(geometry) {
  const n = geometry.attributes.position.count;
  const sets = Array.from({ length: n }, () => new Set());
  const idx = geometry.index.array;
  for (let i = 0; i < idx.length; i += 3) {
    const [a, b, c] = [idx[i], idx[i + 1], idx[i + 2]];
    sets[a].add(b).add(c); sets[b].add(a).add(c); sets[c].add(a).add(b);
  }
  return sets.map((s) => Uint32Array.from(s));
}

/** Làm mượt Taubin (λ/μ xen kẽ) — mượt mà không teo nhỏ như Laplacian thường. */
export function smoothGeometry(geometry, level = 3) {
  const g = densify(toIndexedByPosition(geometry));
  const neighbors = buildNeighbors(g);
  const pos = g.attributes.position.array;
  const next = new Float32Array(pos.length);
  for (let it = 0; it < level * 2; it++) {
    const factor = it % 2 === 0 ? 0.5 : -0.53;
    for (let v = 0; v < neighbors.length; v++) {
      const nb = neighbors[v];
      for (let k = 0; k < 3; k++) {
        if (!nb.length) { next[v * 3 + k] = pos[v * 3 + k]; continue; }
        let sum = 0;
        for (let j = 0; j < nb.length; j++) sum += pos[nb[j] * 3 + k];
        next[v * 3 + k] = pos[v * 3 + k] + factor * (sum / nb.length - pos[v * 3 + k]);
      }
    }
    pos.set(next);
  }
  return finish(g);
}

/** Giảm số tam giác, giữ lại `keepRatio` (0.1..0.9) số đỉnh. */
export function simplifyGeometry(geometry, keepRatio) {
  const g = toIndexedByPosition(geometry);
  const remove = Math.floor(g.attributes.position.count * (1 - keepRatio));
  return finish(new SimplifyModifier().modify(g, remove));
}

export function finish(g) {
  g.attributes.position.needsUpdate = true;
  g.computeVertexNormals();
  g.computeBoundingBox();
  g.computeBoundingSphere();
  return g;
}

export const triangleCountOf = (g) => (g.index ? g.index.count : g.attributes.position.count) / 3;
