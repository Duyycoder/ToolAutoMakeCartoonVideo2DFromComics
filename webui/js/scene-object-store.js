// Danh sách vật thể + vật đang chọn. Phát sự kiện để các panel tự vẽ lại:
//   'changed'   : thêm/xoá/đổi tên/đổi màu/ẩn hiện
//   'selection' : đổi vật đang chọn (Shift + bấm: chọn nhiều — `selection`; `selected` = vật chọn sau cùng)
//   'transform' : vật đang chọn vừa di chuyển/xoay/co giãn (chỉ cập nhật số liệu)
export class SceneObjectStore extends EventTarget {
  constructor(root) {
    super();
    this.root = root;
    this.selection = [];
    this.counters = {};
  }

  get objects() {
    return this.root.children;
  }

  /** "Hộp" -> "Hộp 1", "Hộp 2"... */
  nextName(base) {
    this.counters[base] = (this.counters[base] || 0) + 1;
    return `${base} ${this.counters[base]}`;
  }

  /** `parent`: vật cha khi thêm lại 1 phần con (hoàn tác xoá / nhân bản phần con); mặc định là gốc cảnh. `index`: vị trí trong danh sách. */
  add(obj, { select = true, parent = this.root, index = -1 } = {}) {
    parent.add(obj);
    if (index >= 0) parent.children.splice(index, 0, parent.children.pop());
    this.changed();
    if (select) this.select(obj);
  }

  get selected() {
    return this.selection[this.selection.length - 1] ?? null;
  }

  /** Vật còn nằm trong cảnh (kể cả phần con lồng nhiều cấp). */
  contains(obj) {
    for (let o = obj; o; o = o.parent) if (o === this.root) return true;
    return false;
  }

  remove(obj) {
    obj.parent?.remove(obj);
    const kept = this.selection.filter((o) => this.contains(o)); // bỏ cả phần con của vật vừa xoá
    if (kept.length !== this.selection.length) {
      this.selection = kept;
      this.dispatchEvent(new Event('selection'));
    }
    this.changed();
  }

  /** Chọn đúng 1 vật (null = bỏ chọn hết). */
  select(obj) {
    if (this.selection.length === (obj ? 1 : 0) && this.selected === obj) return;
    this.selection = obj ? [obj] : [];
    this.dispatchEvent(new Event('selection'));
  }

  /** Shift + bấm: thêm vào / bỏ khỏi vùng chọn. */
  toggleSelect(obj) {
    if (!obj) return;
    this.selection = this.selection.includes(obj)
      ? this.selection.filter((o) => o !== obj)
      : [...this.selection, obj];
    this.dispatchEvent(new Event('selection'));
  }

  /** Chọn nhiều vật cùng lúc (vd. sau khi tách / bỏ nhóm). */
  selectMany(objs) {
    this.selection = [...objs];
    this.dispatchEvent(new Event('selection'));
  }

  changed() {
    this.dispatchEvent(new Event('changed'));
  }

  transformed() {
    this.dispatchEvent(new Event('transform'));
  }

  triangleCount(obj = this.root) {
    let tris = 0;
    obj.traverse((m) => {
      if (!m.isMesh || !m.geometry) return;
      const g = m.geometry;
      tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
    });
    return Math.round(tris);
  }
}
