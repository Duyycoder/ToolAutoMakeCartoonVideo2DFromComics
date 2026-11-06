// Chọn điểm/mặt: bấm (raycast -> chỉ chọn được thứ nhìn thấy) hoặc kéo khung (chiếu lên màn hình).
import * as THREE from 'three';

const raycaster = new THREE.Raycaster();

function ndc(viewport, clientX, clientY) {
  const r = viewport.renderer.domElement.getBoundingClientRect();
  return new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
}

/** Bấm chuột: trả về { vertex, face } dưới con trỏ, hoặc null nếu bấm ra ngoài vật. */
export function pickElement(viewport, mesh, clientX, clientY) {
  raycaster.setFromCamera(ndc(viewport, clientX, clientY), viewport.camera);
  const hit = raycaster.intersectObject(mesh, false)[0];
  if (!hit?.face) return null;
  const pos = mesh.geometry.attributes.position;
  const local = mesh.worldToLocal(hit.point.clone());
  let best = hit.face.a, bestD = Infinity;
  for (const v of [hit.face.a, hit.face.b, hit.face.c]) {
    const d = local.distanceToSquared(new THREE.Vector3().fromBufferAttribute(pos, v));
    if (d < bestD) { bestD = d; best = v; }
  }
  return { vertex: best, face: hit.faceIndex };
}

/**
 * Kéo khung: chọn điểm (hoặc tâm mặt) nằm trong khung. Mặc định bỏ qua phần quay lưng về camera
 * (người mới thường không muốn chọn cả mặt sau) — `throughAll` để chọn xuyên qua.
 */
export function boxSelect(viewport, mesh, rect, mode, throughAll) {
  const { camera } = viewport;
  const canvas = viewport.renderer.domElement.getBoundingClientRect();
  const geo = mesh.geometry;
  const pos = geo.attributes.position, nor = geo.attributes.normal;
  const idx = geo.index.array;
  const m = mesh.matrixWorld, nm = new THREE.Matrix3().getNormalMatrix(m);
  const camPos = camera.getWorldPosition(new THREE.Vector3());
  const p = new THREE.Vector3(), n = new THREE.Vector3(), screen = new THREE.Vector3();

  const inside = (world) => {
    screen.copy(world).project(camera);
    if (screen.z > 1) return false;
    const x = canvas.left + (screen.x + 1) / 2 * canvas.width;
    const y = canvas.top + (1 - screen.y) / 2 * canvas.height;
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  };
  const facing = (world, normalLocal) => throughAll
    || n.copy(normalLocal).applyMatrix3(nm).dot(camPos.clone().sub(world)) > 0;

  const result = [];
  if (mode === 'vertex') {
    for (let i = 0; i < pos.count; i++) {
      p.fromBufferAttribute(pos, i).applyMatrix4(m);
      if (inside(p) && facing(p, new THREE.Vector3().fromBufferAttribute(nor, i))) result.push(i);
    }
  } else {
    const tri = new THREE.Triangle(), a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
    for (let f = 0; f < idx.length / 3; f++) {
      a.fromBufferAttribute(pos, idx[f * 3]); b.fromBufferAttribute(pos, idx[f * 3 + 1]); c.fromBufferAttribute(pos, idx[f * 3 + 2]);
      tri.set(a, b, c);
      const fn = tri.getNormal(new THREE.Vector3());
      tri.getMidpoint(p).applyMatrix4(m);
      if (inside(p) && facing(p, fn)) result.push(f);
    }
  }
  return result;
}
