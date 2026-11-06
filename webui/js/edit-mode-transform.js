// Gizmo di chuyển/xoay/co giãn các ĐIỂM đang chọn (không phải cả vật). "Kéo mềm": các điểm quanh
// vùng chọn đi theo, càng xa càng ít -> uốn hình mượt thay vì kéo nhọn.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

export function createEditTransform(viewport, { onBegin, onEnd }) {
  const pivot = new THREE.Object3D();
  viewport.scene.add(pivot);
  const gizmo = new TransformControls(viewport.camera, viewport.renderer.domElement);
  const helper = gizmo.getHelper();
  helper.userData.editorOnly = true;
  viewport.scene.add(helper);

  let session = null; // { mesh, affected: [{ i, w, start: Vector3 world }], startInverse }
  let pointerOnGizmo = false;
  const inv = new THREE.Matrix4(), delta = new THREE.Matrix4(), tmp = new THREE.Vector3();

  gizmo.addEventListener('mouseDown', () => { pointerOnGizmo = true; });
  gizmo.addEventListener('dragging-changed', (e) => {
    viewport.orbit.enabled = !e.value;
    if (e.value) onBegin(); else { session = null; onEnd(); }
  });
  gizmo.addEventListener('objectChange', () => {
    if (!session) return;
    pivot.updateMatrixWorld(true);
    delta.multiplyMatrices(pivot.matrixWorld, session.startInverse);
    const pos = session.mesh.geometry.attributes.position;
    inv.copy(session.mesh.matrixWorld).invert();
    for (const { i, w, start } of session.affected) {
      tmp.copy(start).applyMatrix4(delta).lerp(start, 1 - w).applyMatrix4(inv);
      pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
    }
    pos.needsUpdate = true;
  });

  return {
    /**
     * Đặt gizmo ở tâm các điểm chọn; tính trước trọng số "kéo mềm" (radius = 0 -> chỉ điểm chọn).
     * Gọi lại mỗi khi vùng chọn đổi.
     */
    attach(mesh, selV, softRadius) {
      const pos = mesh.geometry.attributes.position;
      mesh.updateWorldMatrix(true, false);
      const world = (i) => new THREE.Vector3().fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      const selected = [];
      selV.forEach((s, i) => { if (s) selected.push(i); });
      if (!selected.length) { gizmo.detach(); session = null; return; }

      const center = selected.reduce((c, i) => c.add(world(i)), new THREE.Vector3()).divideScalar(selected.length);
      pivot.position.copy(center);
      pivot.rotation.set(0, 0, 0);
      pivot.scale.set(1, 1, 1);
      pivot.updateMatrixWorld(true);

      const selWorld = selected.map(world);
      const affected = [];
      for (let i = 0; i < pos.count; i++) {
        const p = world(i);
        if (selV[i]) { affected.push({ i, w: 1, start: p }); continue; }
        if (softRadius <= 0) continue;
        // Ít điểm chọn -> khoảng cách tới điểm chọn gần nhất; nhiều -> tới tâm (đỡ chậm).
        const d = selWorld.length <= 300
          ? Math.min(...selWorld.map((s) => s.distanceTo(p)))
          : p.distanceTo(center);
        if (d < softRadius) {
          const t = 1 - d / softRadius;
          affected.push({ i, w: t * t * (3 - 2 * t), start: p });
        }
      }
      session = { mesh, affected, startInverse: pivot.matrixWorld.clone().invert() };
      gizmo.attach(pivot);
    },
    detach() { gizmo.detach(); session = null; },
    setMode(mode) { gizmo.setMode(mode); },
    consumePointer() {
      const was = pointerOnGizmo || gizmo.dragging;
      pointerOnGizmo = false;
      return was;
    },
    dispose() {
      gizmo.detach();
      gizmo.dispose();
      viewport.scene.remove(helper, pivot);
    },
  };
}
