// Thao tác trên NHIỀU vật (Shift + bấm để chọn): gộp thành 1 lưới, ghép liền (hợp khối), nhóm lại.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { bakeWorldGeometry, booleanGeometry, firstMaterialOf, meshesOf, objectWorldGeometry, unifyAttributes } from './mesh-split-merge-operations.js';
import { copyOriginalLook } from './material-preset-library.js';
import { fixLightCopy, isLightObject } from './scene-light-objects.js';
import { toast } from './toast-notifications.js';
import { cloneObject, isRigged, RIGGED_WARNING } from './rig-builder.js';

/**
 * Lưới toạ độ thế giới + chất liệu của từng phần. Vật đã gộp trước đó (nhiều chất liệu, có `groups`)
 * được tách theo nhóm -> gộp tiếp lần nữa vẫn giữ đúng màu từng phần.
 */
function meshParts(mesh) {
  const g = bakeWorldGeometry(mesh);
  if (!Array.isArray(mesh.material) || !mesh.geometry.groups.length) return [{ g, mat: firstMaterialOf(mesh) }];
  const idx = g.index.array;
  return mesh.geometry.groups.map((gr) => {
    const sub = new THREE.BufferGeometry();
    for (const [name, attr] of Object.entries(g.attributes)) sub.setAttribute(name, attr);
    sub.setIndex(Array.from(idx.slice(gr.start, gr.start + gr.count)));
    return { g: sub, mat: mesh.material[gr.materialIndex] ?? mesh.material[0] };
  });
}

export function createMultiObjectTools({ store, busy, replaceObjects, makeMesh }) {
  /** Bỏ đèn ra (đèn không có hình để gộp); cần ít nhất 2 vật. */
  function shapesOnly(objs) {
    if (objs.some(isRigged)) { toast(RIGGED_WARNING, { type: 'warn', timeout: 7000 }); return null; }
    const shapes = objs.filter((o) => !isLightObject(o));
    if (shapes.length < objs.length) toast('Đèn không gộp được — đã bỏ qua đèn.', { type: 'warn' });
    if (shapes.length < 2) { toast('Hãy chọn ít nhất 2 vật (giữ Shift + bấm).', { type: 'warn' }); return null; }
    return shapes;
  }

  const nameOf = (objs) => (objs.length === 2 ? `${objs[0].name} + ${objs[1].name}` : `${objs[0].name} + ${objs.length - 1} vật`);

  return {
    /** Gộp thành 1 vật, mỗi phần giữ chất liệu riêng (không cắt gọt hình). */
    join(objs) {
      const shapes = shapesOnly(objs);
      if (!shapes) return;
      const parts = shapes.flatMap((o) => meshesOf(o).flatMap(meshParts));
      const merged = mergeGeometries(unifyAttributes(parts.map((p) => p.g)), true);
      replaceObjects('Gộp vật', shapes, [makeMesh(merged, parts.map((p) => p.mat), nameOf(shapes))]);
    },

    /** Hợp thành 1 khối liền: phần chồng lên nhau được nối liền, bỏ mặt thừa bên trong. */
    union: (objs) => busy('Đang ghép liền', () => {
      const shapes = shapesOnly(objs);
      if (!shapes) return;
      const geometry = shapes.slice(1).reduce(
        (acc, o) => booleanGeometry(acc, objectWorldGeometry(o), 'union'), objectWorldGeometry(shapes[0]));
      replaceObjects('Ghép liền', shapes, [makeMesh(geometry, firstMaterialOf(meshesOf(shapes[0])[0]), nameOf(shapes))]);
    }),

    /** Nhóm lại: các vật vẫn riêng (giữ nguyên hình/màu), nhưng chọn/di chuyển cùng nhau. */
    group(objs) {
      if (objs.length < 2) return toast('Hãy chọn ít nhất 2 vật (giữ Shift + bấm).', { type: 'warn' });
      const box = new THREE.Box3();
      objs.forEach((o) => box.expandByObject(o));
      const center = box.getCenter(new THREE.Vector3()).setY(0);
      const group = new THREE.Group();
      group.name = store.nextName('Nhóm');
      group.userData.kind = 'group';
      group.position.copy(center);
      for (const o of objs) {
        const c = cloneObject(o);
        o.updateWorldMatrix(true, false); // phần con lồng trong vật khác: lấy vị trí/hướng/cỡ thật
        o.matrixWorld.decompose(c.position, c.quaternion, c.scale);
        c.position.sub(center); // nhóm không xoay/co giãn -> chỉ cần trừ tâm
        copyOriginalLook(o, c);
        fixLightCopy(c);
        group.add(c);
      }
      replaceObjects('Nhóm lại', objs, [group]);
      toast('Đã nhóm lại — muốn tách ra thì bấm "Tách phần rời" trong mục Sửa hình.', { type: 'ok', timeout: 6000 });
    },
  };
}
