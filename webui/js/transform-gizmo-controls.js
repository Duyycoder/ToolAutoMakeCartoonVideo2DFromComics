// Gizmo di chuyển/xoay/co giãn. 1 vật: gắn thẳng vào vật. Nhiều vật (Shift + bấm): gắn vào "tâm nhóm",
// kéo là cả nhóm đi theo. Mỗi lần kéo xong = 1 bước Undo.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { batchCommand, sameTransform, snapshotTransform, transformCommand } from './scene-edit-commands.js';

const MODE_LABELS = { translate: 'Di chuyển', rotate: 'Xoay', scale: 'Co giãn' };

export function createGizmo(viewport, store, stack) {
  const gizmo = new TransformControls(viewport.camera, viewport.renderer.domElement);
  // Bật bắt dính mặc định: người mới dễ đặt vật thẳng hàng.
  gizmo.setTranslationSnap(0.05);
  gizmo.setRotationSnap(THREE.MathUtils.degToRad(15));
  gizmo.setScaleSnap(0.05);
  const helper = gizmo.getHelper();
  helper.userData.editorOnly = true; // ẩn khi xuất ảnh
  viewport.scene.add(helper);
  const pivot = new THREE.Object3D(); // tâm nhóm khi chọn nhiều vật
  viewport.scene.add(pivot);

  let drag = null; // { targets: [{ obj, before, start: Matrix4 }], pivotInverse }
  let enabled = true; // tắt khi đang "Chỉnh điểm" (gizmo riêng cho điểm)
  let pointerOnGizmo = false; // để click vào tay cầm không bị hiểu là "bỏ chọn"
  const delta = new THREE.Matrix4(), m = new THREE.Matrix4();

  const targets = () => store.selection.filter((o) => o.visible && o.parent);

  gizmo.addEventListener('mouseDown', () => { pointerOnGizmo = true; });
  gizmo.addEventListener('dragging-changed', (e) => {
    viewport.orbit.enabled = !e.value;
    if (!gizmo.object) return;
    if (e.value) {
      pivot.updateMatrixWorld(true);
      drag = {
        targets: targets().map((obj) => {
          obj.updateMatrix(); // vừa Undo xong có thể chưa render -> ma trận cũ
          return { obj, before: snapshotTransform(obj), start: obj.matrix.clone() };
        }),
        pivotInverse: pivot.matrixWorld.clone().invert(),
      };
      return;
    }
    const cmds = drag.targets
      .map(({ obj, before }) => ({ obj, before, after: snapshotTransform(obj) }))
      .filter((t) => !sameTransform(t.before, t.after))
      .map((t) => transformCommand(store, t.obj, t.before, t.after, MODE_LABELS[gizmo.mode]));
    if (cmds.length === 1) stack.push(cmds[0]);
    else if (cmds.length) stack.push(batchCommand(`${MODE_LABELS[gizmo.mode]} ${cmds.length} vật`, cmds));
    drag = null;
  });
  gizmo.addEventListener('objectChange', () => {
    if (drag && gizmo.object === pivot) {
      // Vật nằm thẳng trong objectsRoot (ma trận đơn vị) -> ma trận local = world.
      pivot.updateMatrixWorld(true);
      delta.multiplyMatrices(pivot.matrixWorld, drag.pivotInverse);
      for (const { obj, start } of drag.targets) {
        m.multiplyMatrices(delta, start).decompose(obj.position, obj.quaternion, obj.scale);
      }
    }
    store.transformed();
  });

  const sync = () => {
    if (drag) return; // đang kéo thì không đổi chỗ gắn
    const list = enabled ? targets() : [];
    if (!list.length) return gizmo.detach();
    if (list.length === 1) return gizmo.attach(list[0]);
    const box = new THREE.Box3();
    list.forEach((o) => box.expandByObject(o));
    box.getCenter(pivot.position);
    pivot.rotation.set(0, 0, 0);
    pivot.scale.set(1, 1, 1);
    gizmo.attach(pivot);
  };
  store.addEventListener('selection', sync);
  store.addEventListener('changed', sync);
  // Undo/Redo dời vật -> dời luôn tâm nhóm cho khớp.
  store.addEventListener('transform', () => { if (!drag && gizmo.object === pivot) sync(); });

  return {
    setMode(mode) { gizmo.setMode(mode); },
    setEnabled(value) { enabled = value; sync(); },
    get mode() { return gizmo.mode; },
    /** true nếu lần nhấn chuột vừa rồi rơi vào tay cầm gizmo (rồi reset cờ). */
    consumePointer() {
      const was = pointerOnGizmo || gizmo.dragging;
      pointerOnGizmo = false;
      return was;
    },
  };
}
