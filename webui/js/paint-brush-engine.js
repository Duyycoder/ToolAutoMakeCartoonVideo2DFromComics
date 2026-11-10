// Tô màu đỉnh (vertex color) — hàm thuần. Màu trong geometry là màu TUYẾN TÍNH (như three.js dùng).
import * as THREE from 'three';

const smooth = (t) => t * t * (3 - 2 * t);

/**
 * Tô trong hình cầu bán kính `radius` quanh `center` (toạ độ local của mesh).
 * mode 'paint': pha về `rgb`; 'blur': pha về màu trung bình của vùng (làm nhoè ranh giới).
 */
export function paintSphere(geo, center, radius, rgb, strength, mode = 'paint') {
  const pos = geo.attributes.position.array;
  const colorAttr = geo.attributes.color;
  const c = colorAttr.array, cs = colorAttr.itemSize;
  const r2 = radius * radius;
  const hits = [];
  for (let v = 0; v < pos.length / 3; v++) {
    const dx = pos[v * 3] - center.x, dy = pos[v * 3 + 1] - center.y, dz = pos[v * 3 + 2] - center.z;
    const d2 = dx * dx + dy * dy + dz * dz;
    if (d2 <= r2) hits.push(v, Math.sqrt(d2));
  }
  if (!hits.length) return false;
  let target = rgb;
  if (mode === 'blur') {
    target = [0, 0, 0];
    for (let i = 0; i < hits.length; i += 2) for (let k = 0; k < 3; k++) target[k] += c[hits[i] * cs + k];
    target = target.map((x) => x / (hits.length / 2));
  }
  for (let i = 0; i < hits.length; i += 2) {
    const v = hits[i];
    const w = strength * smooth(1 - hits[i + 1] / radius);
    for (let k = 0; k < 3; k++) c[v * cs + k] += (target[k] - c[v * cs + k]) * w;
  }
  colorAttr.needsUpdate = true;
  return true;
}

/** Tô cả vật 1 màu. */
export function fillAll(geo, rgb) {
  const attr = geo.attributes.color;
  for (let v = 0; v < attr.count; v++) attr.setXYZ(v, rgb[0], rgb[1], rgb[2]);
  attr.needsUpdate = true;
}

/** Màu (hex sRGB) của đỉnh gần điểm chạm nhất — cho "Hút màu". */
export function colorAtFace(geo, face, localPoint) {
  const pos = geo.attributes.position;
  let best = face.a, bestD = Infinity;
  for (const v of [face.a, face.b, face.c]) {
    const d = localPoint.distanceToSquared(new THREE.Vector3().fromBufferAttribute(pos, v));
    if (d < bestD) { bestD = d; best = v; }
  }
  const col = geo.attributes.color;
  return `#${new THREE.Color(col.getX(best), col.getY(best), col.getZ(best)).getHexString()}`;
}

/** Màu đỉnh ban đầu khi vật chưa có: lấy màu vật liệu (đã là tuyến tính). */
export function ensureColorAttribute(geo, baseColor) {
  if (geo.attributes.color) return;
  const n = geo.attributes.position.count;
  const data = new Float32Array(n * 3);
  for (let v = 0; v < n; v++) { data[v * 3] = baseColor.r; data[v * 3 + 1] = baseColor.g; data[v * 3 + 2] = baseColor.b; }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(data, 3));
}

/** Điểm ảnh RGBA của texture (ảnh thường hoặc DataTexture như TGA). Null nếu ảnh chưa tải xong. */
function texturePixels(texture) {
  const img = texture.image;
  if (img?.data && img.width) return { data: img.data, width: img.width, height: img.height };
  if (!img?.width) return null;
  const ctx = Object.assign(document.createElement('canvas'), { width: img.width, height: img.height }).getContext('2d');
  ctx.drawImage(img, 0, 0);
  return ctx.getImageData(0, 0, img.width, img.height);
}

/**
 * Màu đỉnh = màu texture tại UV của đỉnh (x màu vật liệu) -> tô vẽ tiếp trên vân sẵn có thay vì nền trắng.
 * Trả về false nếu không lấy được (không UV / ảnh chưa tải).
 */
export function colorsFromTexture(geo, texture, tint) {
  const uv = geo.attributes.uv;
  const px = uv && texturePixels(texture);
  if (!px) return false;
  const n = geo.attributes.position.count;
  const data = new Float32Array(n * 3);
  const c = new THREE.Color();
  const wrap = (t) => t - Math.floor(t);
  for (let v = 0; v < n; v++) {
    // Hàng 0 của ảnh là đỉnh trên khi flipY (ảnh thường), đáy khi không (glTF) -> cùng 1 công thức.
    const x = Math.min(px.width - 1, Math.floor(wrap(uv.getX(v)) * px.width));
    const yv = wrap(uv.getY(v));
    const y = Math.min(px.height - 1, Math.floor((texture.flipY ? 1 - yv : yv) * px.height));
    const i = (y * px.width + x) * 4;
    c.setRGB(px.data[i] / 255, px.data[i + 1] / 255, px.data[i + 2] / 255, THREE.SRGBColorSpace).multiply(tint);
    data[v * 3] = c.r; data[v * 3 + 1] = c.g; data[v * 3 + 2] = c.b;
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(data, 3));
  return true;
}

/**
 * Dán ảnh: chiếu ảnh (đặt trong khung `imageRect` trên màn hình) lên các điểm QUAY VỀ camera.
 * Điểm bị che ở mặt sau không bị tô. Màu ảnh là sRGB -> đổi sang tuyến tính trước khi pha.
 */
export function projectImage(mesh, camera, canvasRect, imageRect, imageData, opacity = 1) {
  const geo = mesh.geometry;
  const pos = geo.attributes.position, nor = geo.attributes.normal, col = geo.attributes.color;
  mesh.updateWorldMatrix(true, false);
  const m = mesh.matrixWorld, nm = new THREE.Matrix3().getNormalMatrix(m);
  const camPos = camera.getWorldPosition(new THREE.Vector3());
  const p = new THREE.Vector3(), n = new THREE.Vector3(), s = new THREE.Vector3(), tmp = new THREE.Color();
  let painted = 0;
  for (let v = 0; v < pos.count; v++) {
    p.fromBufferAttribute(pos, v).applyMatrix4(m);
    n.fromBufferAttribute(nor, v).applyMatrix3(nm);
    if (n.dot(camPos.clone().sub(p)) <= 0) continue;
    s.copy(p).project(camera);
    if (s.z > 1 || s.z < -1) continue;
    const x = canvasRect.left + (s.x + 1) / 2 * canvasRect.width;
    const y = canvasRect.top + (1 - s.y) / 2 * canvasRect.height;
    const u = (x - imageRect.left) / imageRect.width, w = (y - imageRect.top) / imageRect.height;
    if (u < 0 || u >= 1 || w < 0 || w >= 1) continue;
    const i = (Math.floor(w * imageData.height) * imageData.width + Math.floor(u * imageData.width)) * 4;
    const a = (imageData.data[i + 3] / 255) * opacity;
    if (a <= 0) continue;
    tmp.setRGB(imageData.data[i] / 255, imageData.data[i + 1] / 255, imageData.data[i + 2] / 255, THREE.SRGBColorSpace);
    col.setXYZ(v, col.getX(v) + (tmp.r - col.getX(v)) * a, col.getY(v) + (tmp.g - col.getY(v)) * a,
      col.getZ(v) + (tmp.b - col.getZ(v)) * a);
    painted++;
  }
  col.needsUpdate = true;
  return painted;
}
