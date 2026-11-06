// Cọ nặn hình — hàm thuần trên position của geometry có index (toạ độ local của mesh).
// Mỗi hàm thay đổi trực tiếp vị trí đỉnh trong bán kính cọ, giảm dần ra mép (smoothstep).
import * as THREE from 'three';

const falloff = (d, r) => { const t = 1 - d / r; return t * t * (3 - 2 * t); };

/** Các đỉnh trong hình cầu: mảng phẳng [chỉ số, trọng số, ...]. */
export function verticesInSphere(pos, center, radius) {
  const out = [];
  const r2 = radius * radius;
  for (let v = 0; v < pos.length / 3; v++) {
    const dx = pos[v * 3] - center.x, dy = pos[v * 3 + 1] - center.y, dz = pos[v * 3 + 2] - center.z;
    const d2 = dx * dx + dy * dy + dz * dz;
    if (d2 <= r2) out.push(v, falloff(Math.sqrt(d2), radius));
  }
  return out;
}

/** Pháp tuyến trung bình của vùng cọ (từ vertex normal) — đắp/làm phẳng theo hướng bề mặt chung. */
function areaNormal(geo, hits) {
  const nor = geo.attributes.normal.array;
  const n = new THREE.Vector3();
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i];
    n.x += nor[v * 3] * hits[i + 1]; n.y += nor[v * 3 + 1] * hits[i + 1]; n.z += nor[v * 3 + 2] * hits[i + 1];
  }
  return n.lengthSq() ? n.normalize() : null;
}

/** Đắp (sign = +1) hoặc lõm (sign = -1) theo pháp tuyến vùng cọ. */
export function drawBrush(geo, center, radius, strength, sign) {
  const pos = geo.attributes.position.array;
  const hits = verticesInSphere(pos, center, radius);
  const n = areaNormal(geo, hits);
  if (!n) return false;
  const amount = radius * 0.12 * strength * sign; // đủ mạnh để thấy ngay sau vài nét
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i], w = hits[i + 1] * amount;
    pos[v * 3] += n.x * w; pos[v * 3 + 1] += n.y * w; pos[v * 3 + 2] += n.z * w;
  }
  return true;
}

/** Làm mượt: kéo mỗi đỉnh về trung bình các đỉnh kề (neighbors từ buildNeighbors). */
export function smoothBrush(geo, neighbors, center, radius, strength) {
  const pos = geo.attributes.position.array;
  const hits = verticesInSphere(pos, center, radius);
  const prev = new Float32Array(hits.length / 2 * 3);
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i], nb = neighbors[v];
    for (let k = 0; k < 3; k++) {
      let sum = 0;
      for (let j = 0; j < nb.length; j++) sum += pos[nb[j] * 3 + k];
      prev[i / 2 * 3 + k] = nb.length ? sum / nb.length : pos[v * 3 + k];
    }
  }
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i], w = hits[i + 1] * strength * 0.5;
    for (let k = 0; k < 3; k++) pos[v * 3 + k] += (prev[i / 2 * 3 + k] - pos[v * 3 + k]) * w;
  }
  return hits.length > 0;
}

/** Làm phẳng: ép các đỉnh về mặt phẳng trung bình của vùng cọ. */
export function flattenBrush(geo, center, radius, strength) {
  const pos = geo.attributes.position.array;
  const hits = verticesInSphere(pos, center, radius);
  const n = areaNormal(geo, hits);
  if (!n) return false;
  const c = new THREE.Vector3();
  let wsum = 0;
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i], w = hits[i + 1];
    c.x += pos[v * 3] * w; c.y += pos[v * 3 + 1] * w; c.z += pos[v * 3 + 2] * w; wsum += w;
  }
  c.divideScalar(wsum);
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i];
    const d = (pos[v * 3] - c.x) * n.x + (pos[v * 3 + 1] - c.y) * n.y + (pos[v * 3 + 2] - c.z) * n.z;
    const w = d * hits[i + 1] * strength * 0.5;
    pos[v * 3] -= n.x * w; pos[v * 3 + 1] -= n.y * w; pos[v * 3 + 2] -= n.z * w;
  }
  return true;
}

/** Kéo: chụp vùng lúc bắt đầu; mỗi lần di chuột dời vùng theo `delta` (local) nhân trọng số. */
export function beginGrab(geo, center, radius) {
  const pos = geo.attributes.position.array;
  const hits = verticesInSphere(pos, center, radius);
  const start = new Float32Array(hits.length / 2 * 3);
  for (let i = 0; i < hits.length; i += 2) for (let k = 0; k < 3; k++) start[i / 2 * 3 + k] = pos[hits[i] * 3 + k];
  return { hits, start };
}

export function applyGrab(geo, grab, delta) {
  const pos = geo.attributes.position.array;
  const { hits, start } = grab;
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i], w = hits[i + 1];
    pos[v * 3] = start[i / 2 * 3] + delta.x * w;
    pos[v * 3 + 1] = start[i / 2 * 3 + 1] + delta.y * w;
    pos[v * 3 + 2] = start[i / 2 * 3 + 2] + delta.z * w;
  }
}
