// Các command có thể Undo cho mọi thao tác chỉnh sửa cảnh.

export const addObjectCommand = (store, obj) => ({
  label: `Thêm "${obj.name}"`,
  do: () => store.add(obj),
  undo: () => store.remove(obj),
});

export const removeObjectCommand = (store, obj) => ({
  label: `Xoá "${obj.name}"`,
  do: () => store.remove(obj),
  undo: () => store.add(obj),
});

/** Gộp nhiều command thành 1 bước Undo (vd. "Mới" xoá hết, mở project nhiều vật). */
export const batchCommand = (label, cmds) => ({
  label,
  do: () => cmds.forEach((c) => c.do()),
  undo: () => [...cmds].reverse().forEach((c) => c.undo()),
});

export const snapshotTransform = (obj) => ({
  p: obj.position.clone(), q: obj.quaternion.clone(), s: obj.scale.clone(),
});

export const sameTransform = (a, b) => a.p.equals(b.p) && a.q.equals(b.q) && a.s.equals(b.s);

function applyTransform(obj, t) {
  obj.position.copy(t.p);
  obj.quaternion.copy(t.q);
  obj.scale.copy(t.s);
}

export const transformCommand = (store, obj, before, after, label = 'Di chuyển') => ({
  label,
  do: () => { applyTransform(obj, after); store.transformed(); },
  undo: () => { applyTransform(obj, before); store.transformed(); },
});

/** Danh sách [mesh, material] theo thứ tự duyệt — để hoàn tác đổi màu/chất liệu. */
export function snapshotMaterials(obj) {
  const list = [];
  obj.traverse((m) => { if (m.isMesh) list.push([m, m.material]); });
  return list;
}

const restoreMaterials = (snap) => snap.forEach(([mesh, mat]) => { mesh.material = mat; });

export const materialCommand = (store, before, after, label) => ({
  label,
  do: () => { restoreMaterials(after); store.changed(); },
  undo: () => { restoreMaterials(before); store.changed(); },
});

export const renameCommand = (store, obj, before, after) => ({
  label: 'Đổi tên',
  do: () => { obj.name = after; store.changed(); },
  undo: () => { obj.name = before; store.changed(); },
});
