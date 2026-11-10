// Thao tác "Sửa hình" (đều Undo được): làm mượt, giảm chi tiết, đối xứng, nhân mảng,
// ghép/khoét/phần chung, gộp lưới, tách phần rời / tách nhóm.
import * as THREE from 'three';
import { simplifyGeometry, smoothGeometry, triangleCountOf } from './mesh-subdivide-smooth.js';
import {
  bakeWorldGeometry, booleanGeometry, firstMaterialOf, meshesOf, objectWorldGeometry, recenter, splitLooseParts,
} from './mesh-split-merge-operations.js';
import { addObjectCommand, batchCommand, removeObjectCommand } from './scene-edit-commands.js';
import { copyOriginalLook, rememberOriginalLook } from './material-preset-library.js';
import { toast } from './toast-notifications.js';
import { createMultiObjectTools } from './multi-object-actions.js';
import { createBlenderTools } from './blender-tools-actions.js';
import { detachParts } from './scene-object-parts.js';

const BOOLEAN_NAMES = { union: (a, b) => `${a} + ${b}`, subtract: (a) => `${a} (đã khoét)`, intersect: () => 'Phần chung' };

export function createMeshTools({ store, stack }) {
  /** Hiện "Đang ..." rồi mới chạy (thao tác nặng chặn luồng UI vài giây). */
  async function busy(label, fn) {
    const note = toast(`${label}...`, { timeout: 0 });
    await new Promise((r) => setTimeout(r, 30));
    try {
      return await fn();
    } catch (err) {
      console.warn(err);
      toast(`${label} thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      return null;
    } finally {
      note.remove();
    }
  }

  async function replaceGeometries(obj, label, transform) {
    const meshes = meshesOf(obj);
    const before = meshes.map((m) => m.geometry);
    const after = await Promise.all(meshes.map((m) => transform(m.geometry)));
    stack.execute({
      label,
      do: () => { meshes.forEach((m, i) => { m.geometry = after[i]; }); store.changed(); },
      undo: () => { meshes.forEach((m, i) => { m.geometry = before[i]; }); store.changed(); },
    });
  }

  /** Thay các vật cũ bằng vật mới trong 1 bước Undo. */
  function replaceObjects(label, removed, added) {
    stack.execute(batchCommand(label, [
      ...removed.map((o) => removeObjectCommand(store, o)),
      ...added.map((o) => addObjectCommand(store, o)),
    ]));
  }

  function makeMesh(geometry, material, name) {
    const center = recenter(geometry);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(center);
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.name = name;
    mesh.userData.kind = 'edited';
    rememberOriginalLook(mesh);
    return mesh;
  }

  const many = createMultiObjectTools({ store, busy, replaceObjects, makeMesh });

  return {
    smooth: (obj, level) => busy('Đang làm mượt', () => replaceGeometries(obj, 'Làm mượt', (g) => smoothGeometry(g, level))),

    simplify: (obj, keepRatio) => busy('Đang giảm chi tiết', async () => {
      const before = store.triangleCount(obj);
      if (before < 200) return toast('Vật này đã rất ít chi tiết rồi.', { type: 'warn' });
      await replaceGeometries(obj, 'Giảm chi tiết', (g) => (triangleCountOf(g) < 50 ? g : simplifyGeometry(g, keepRatio)));
      toast(`Đã giảm từ ${before.toLocaleString('vi-VN')} còn ${store.triangleCount(obj).toLocaleString('vi-VN')} tam giác.`, { type: 'ok' });
    }),

    /** Bản sao lật gương ở phía bên kia (trái <-> phải), vd. tai, cánh, tay. */
    mirrorCopy(obj) {
      if (Math.abs(obj.position.x) < 0.05) {
        return toast('Hãy dời vật sang trái hoặc phải trước, bản đối xứng sẽ hiện ở phía bên kia.', { type: 'warn', timeout: 6000 });
      }
      const copy = obj.clone();
      copy.name = `${obj.name} (đối xứng)`;
      copy.scale.x *= -1;
      copy.position.x = -obj.position.x;
      copy.rotation.y = -obj.rotation.y;
      copy.rotation.z = -obj.rotation.z;
      copyOriginalLook(obj, copy);
      stack.execute(addObjectCommand(store, copy));
    },

    /** N bản sao theo hàng ngang hoặc vòng tròn, gom thành 1 nhóm. */
    array(obj, count, mode) {
      const size = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3());
      const group = new THREE.Group();
      group.name = `${obj.name} ×${count}`;
      group.userData.kind = 'array';
      group.position.copy(obj.position);
      const radius = (Math.max(size.x, size.z) * 1.25 * count) / (2 * Math.PI);
      for (let i = 0; i < count; i++) {
        const c = obj.clone();
        c.name = `${obj.name} (${i + 1})`; // tách nhóm ra vẫn phân biệt được từng bản
        if (mode === 'circle') {
          const a = (i / count) * Math.PI * 2;
          c.position.set(Math.cos(a) * radius, 0, Math.sin(a) * radius);
          c.rotation.y = obj.rotation.y - a;
        } else {
          c.position.set(i * size.x * 1.15, 0, 0);
        }
        copyOriginalLook(obj, c);
        group.add(c);
      }
      replaceObjects('Nhân mảng', [obj], [group]);
    },

    boolean: (obj, other, op) => busy('Đang xử lý', () => {
      const geometry = booleanGeometry(objectWorldGeometry(obj), objectWorldGeometry(other), op);
      if (!geometry.attributes.position.count) {
        return toast('Kết quả rỗng — hai vật có chạm/chồng lên nhau không?', { type: 'warn', timeout: 6000 });
      }
      const mesh = makeMesh(geometry, firstMaterialOf(meshesOf(obj)[0]), BOOLEAN_NAMES[op](obj.name, other.name));
      replaceObjects(BOOLEAN_NAMES[op](obj.name, other.name), [obj, other], [mesh]);
    }),

    /** Gộp 2 vật (dropdown trong Sửa hình) — dùng chung logic gộp nhiều vật. */
    join: (obj, other) => many.join([obj, other]),
    many,
    blender: createBlenderTools({ store, stack }),

    /** Nhóm / model nhiều phần -> từng vật riêng (trả về các vật mới); 1 lưới có nhiều mảnh rời -> mỗi mảnh 1 vật. */
    separate: (obj) => busy('Đang tách', () => {
      const named = detachParts(obj);
      if (named.length) {
        replaceObjects('Tách nhóm', [obj], named);
        return named;
      }
      const parts = meshesOf(obj).flatMap((m) => splitLooseParts(bakeWorldGeometry(m))
        .map((g) => ({ g, material: firstMaterialOf(m) })));
      if (parts.length < 2) return toast('Vật này là 1 khối liền — không có phần rời để tách.', { type: 'warn' });
      replaceObjects('Tách phần rời', [obj], parts.map((p, i) => makeMesh(p.g, p.material, `${obj.name} - phần ${i + 1}`)));
      toast(`Đã tách thành ${parts.length} phần.`, { type: 'ok' });
    }),
  };
}
