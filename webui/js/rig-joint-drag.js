// Kéo thẳng chấm khớp trên màn hình: khớp chạy trên mặt phẳng song song màn hình; bật "Tự vào giữa bề dày"
// thì độ sâu lấy GIỮA mặt trước và mặt sau của hình dưới con trỏ (tia camera xuyên qua tay/chân).
import * as THREE from 'three';
import { acceleratedRaycast } from 'three-mesh-bvh';
import { enableBVH } from './surface-session.js';

/** Bật BVH để raycast vật nặng (vài trăm nghìn tam giác) mượt khi kéo; trả về hàm dọn. */
export function prepareRaycastMesh(mesh) {
  const geo = mesh.geometry, oldRaycast = mesh.raycast;
  enableBVH(geo);
  mesh.raycast = acceleratedRaycast;
  return () => { mesh.raycast = oldRaycast; geo.disposeBoundsTree(); };
}

/** Điểm giữa lần vào và lần ra đầu tiên của tia qua `mesh` (toạ độ thế giới), hoặc null nếu tia trượt. */
export function surfaceMidpoint(raycaster, mesh) {
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  const sides = mats.map((m) => m.side);
  mats.forEach((m) => { m.side = THREE.DoubleSide; }); // cần cả mặt sau (lần ra khỏi hình)
  let hits;
  try { hits = raycaster.intersectObject(mesh, false); } finally { mats.forEach((m, i) => { m.side = sides[i]; }); }
  if (!hits.length) return null;
  const exit = hits.find((h) => h.distance > hits[0].distance + 1e-6);
  return exit ? hits[0].point.clone().lerp(exit.point, 0.5) : hits[0].point.clone();
}

/** Mặt phẳng kéo: qua điểm `world`, vuông góc hướng nhìn của camera. */
export function dragPlane(world, camera) {
  const n = camera.getWorldDirection(new THREE.Vector3());
  return new THREE.Plane().setFromNormalAndCoplanarPoint(n, world);
}

/** Chỉ số các khớp con cháu của khớp i (không gồm i). */
export function descendantsOf(joints, i) {
  const out = [];
  const walk = (p) => joints.forEach((j, k) => { if (j.parent === p) { out.push(k); walk(k); } });
  walk(i);
  return out;
}
