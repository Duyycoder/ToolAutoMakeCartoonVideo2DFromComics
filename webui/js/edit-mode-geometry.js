// Thao tác trên điểm/mặt trong chế độ "Chỉnh điểm" — hàm thuần trên geometry có index
// (đỉnh trùng vị trí đã gộp). Mỗi hàm trả về geometry MỚI -> Undo chỉ cần giữ geometry cũ.
import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { buildNeighbors, subdivide } from './mesh-subdivide-smooth.js';

export function buildGeometry(positions, colors, colorSize, index) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  if (colors) g.setAttribute('color', new THREE.Float32BufferAttribute(colors, colorSize));
  g.setIndex(new THREE.BufferAttribute(Uint32Array.from(index), 1));
  g.computeVertexNormals();
  g.computeBoundingBox();
  g.computeBoundingSphere();
  return g;
}

const parts = (g) => ({
  pos: g.attributes.position.array,
  col: g.attributes.color?.array ?? null,
  cs: g.attributes.color?.itemSize ?? 3,
  idx: g.index.array,
});

export const faceCount = (g) => g.index.count / 3;

/** Chỉ giữ các tam giác trong `tris`; bỏ đỉnh không dùng và tam giác suy biến. */
export function compact(g, tris) {
  const { pos, col, cs } = parts(g);
  const remap = new Int32Array(g.attributes.position.count).fill(-1);
  const P = [], C = [], I = [];
  for (let i = 0; i < tris.length; i += 3) {
    const t = [tris[i], tris[i + 1], tris[i + 2]];
    if (t[0] === t[1] || t[1] === t[2] || t[0] === t[2]) continue;
    for (const v of t) {
      if (remap[v] < 0) {
        remap[v] = P.length / 3;
        P.push(pos[v * 3], pos[v * 3 + 1], pos[v * 3 + 2]);
        if (col) for (let k = 0; k < cs; k++) C.push(col[v * cs + k]);
      }
      I.push(remap[v]);
    }
  }
  return buildGeometry(P, col ? C : null, cs, I);
}

const trianglesWhere = (g, keep) => {
  const idx = g.index.array, out = [];
  for (let f = 0; f < idx.length / 3; f++) if (keep(f)) out.push(idx[f * 3], idx[f * 3 + 1], idx[f * 3 + 2]);
  return out;
};

/** Mặt được chọn khi đủ 3 đỉnh đều được chọn. */
export function facesFromVerts(g, selV) {
  const idx = g.index.array;
  const selF = new Uint8Array(idx.length / 3);
  for (let f = 0; f < selF.length; f++) selF[f] = selV[idx[f * 3]] & selV[idx[f * 3 + 1]] & selV[idx[f * 3 + 2]];
  return selF;
}

export function vertsFromFaces(g, selF) {
  const idx = g.index.array;
  const selV = new Uint8Array(g.attributes.position.count);
  for (let f = 0; f < selF.length; f++) if (selF[f]) for (let k = 0; k < 3; k++) selV[idx[f * 3 + k]] = 1;
  return selV;
}

export const deleteFaces = (g, selF) => compact(g, trianglesWhere(g, (f) => !selF[f]));

export const separateFaces = (g, selF) => ({
  rest: compact(g, trianglesWhere(g, (f) => !selF[f])),
  part: compact(g, trianglesWhere(g, (f) => selF[f])),
});

/**
 * Đùn mặt: nhân đôi đỉnh của các mặt chọn, dựng tường ở cạnh biên, đẩy ra theo pháp tuyến.
 * Tường dùng cạnh u->v cùng chiều mặt gốc -> khớp chiều với mặt hàng xóm (v->u), lưới vẫn kín.
 */
export function extrudeFaces(g, selF, distance) {
  const { pos, col, cs, idx } = parts(g);
  const key = (a, b) => (a < b ? a * 16777216 + b : b * 16777216 + a);
  const edgeUse = new Map();
  const normal = new THREE.Vector3(), tmp = new THREE.Triangle(), n = new THREE.Vector3();
  const v = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  for (let f = 0; f < selF.length; f++) {
    if (!selF[f]) continue;
    for (let k = 0; k < 3; k++) {
      const e = key(idx[f * 3 + k], idx[f * 3 + (k + 1) % 3]);
      edgeUse.set(e, (edgeUse.get(e) ?? 0) + 1);
      v[k].fromArray(pos, idx[f * 3 + k] * 3);
    }
    tmp.set(v[0], v[1], v[2]).getNormal(n);
    normal.addScaledVector(n, tmp.getArea());
  }
  normal.normalize();

  const P = Array.from(pos), C = col ? Array.from(col) : null, I = Array.from(idx);
  const copyOf = new Map();
  const dup = (vi) => {
    if (!copyOf.has(vi)) {
      copyOf.set(vi, P.length / 3);
      P.push(pos[vi * 3], pos[vi * 3 + 1], pos[vi * 3 + 2]);
      if (C) for (let k = 0; k < cs; k++) C.push(col[vi * cs + k]);
    }
    return copyOf.get(vi);
  };
  const walls = [];
  for (let f = 0; f < selF.length; f++) {
    if (!selF[f]) continue;
    for (let k = 0; k < 3; k++) {
      const a = idx[f * 3 + k], b = idx[f * 3 + (k + 1) % 3];
      if (edgeUse.get(key(a, b)) === 1) walls.push(a, b, dup(b), a, dup(b), dup(a));
    }
    for (let k = 0; k < 3; k++) I[f * 3 + k] = dup(idx[f * 3 + k]);
  }
  for (const nv of copyOf.values()) {
    P[nv * 3] += normal.x * distance; P[nv * 3 + 1] += normal.y * distance; P[nv * 3 + 2] += normal.z * distance;
  }
  const geo = buildGeometry(P, C, cs, I.concat(walls));
  const selV = new Uint8Array(geo.attributes.position.count);
  for (const nv of copyOf.values()) selV[nv] = 1;
  return { geo, selV };
}

/** Chọn rộng thêm 1 vòng điểm kề. */
export function growSelection(g, selV) {
  const out = selV.slice();
  const idx = g.index.array;
  for (let f = 0; f < idx.length / 3; f++) {
    const t = [idx[f * 3], idx[f * 3 + 1], idx[f * 3 + 2]];
    if (t.some((x) => selV[x])) t.forEach((x) => { out[x] = 1; });
  }
  return out;
}

/** Làm mượt chỉ các điểm đang chọn (Taubin). */
export function smoothSelected(g, selV, iterations = 2) {
  const out = g.clone();
  const pos = out.attributes.position.array;
  const neighbors = buildNeighbors(out);
  for (let it = 0; it < iterations * 2; it++) {
    const factor = it % 2 === 0 ? 0.5 : -0.53;
    const prev = pos.slice();
    for (let vi = 0; vi < neighbors.length; vi++) {
      const nb = neighbors[vi];
      if (!selV[vi] || !nb.length) continue;
      for (let k = 0; k < 3; k++) {
        let sum = 0;
        for (let j = 0; j < nb.length; j++) sum += prev[nb[j] * 3 + k];
        pos[vi * 3 + k] = prev[vi * 3 + k] + factor * (sum / nb.length - prev[vi * 3 + k]);
      }
    }
  }
  out.computeVertexNormals();
  return out;
}

/** Tô màu đỉnh đang chọn. Chưa có màu đỉnh -> khởi tạo bằng màu vật liệu hiện tại. */
export function colorizeSelected(g, selV, rgb, baseRgb) {
  const { pos, col, cs, idx } = parts(g);
  const count = g.attributes.position.count;
  const C = col ? Array.from(col) : Array.from({ length: count * 3 }, (_, i) => baseRgb[i % 3]);
  const size = col ? cs : 3;
  for (let vi = 0; vi < count; vi++) {
    if (!selV[vi]) continue;
    for (let k = 0; k < 3; k++) C[vi * size + k] = rgb[k];
    if (size === 4) C[vi * 4 + 3] = 1;
  }
  return buildGeometry(Array.from(pos), C, size, Array.from(idx));
}

/** Dồn các điểm chọn về 1 điểm (tâm) rồi gộp — dùng để khép lỗ, vuốt nhọn. */
export function mergeSelected(g, selV) {
  const out = g.clone();
  out.deleteAttribute('normal');
  const pos = out.attributes.position.array;
  const c = [0, 0, 0];
  let n = 0;
  selV.forEach((s, vi) => { if (s) { for (let k = 0; k < 3; k++) c[k] += pos[vi * 3 + k]; n++; } });
  if (n < 2) return null;
  selV.forEach((s, vi) => { if (s) for (let k = 0; k < 3; k++) pos[vi * 3 + k] = c[k] / n; });
  const merged = mergeVertices(out, 1e-6);
  return compact(merged, merged.index.array);
}

/** Chia mỗi tam giác thành 4 -> có thêm điểm để chỉnh chi tiết. */
export function subdivideAll(g) {
  const src = g.clone();
  src.deleteAttribute('normal');
  const s = subdivide(src);
  return buildGeometry(Array.from(s.attributes.position.array), s.attributes.color ? Array.from(s.attributes.color.array) : null,
    s.attributes.color?.itemSize ?? 3, Array.from(s.index.array));
}
