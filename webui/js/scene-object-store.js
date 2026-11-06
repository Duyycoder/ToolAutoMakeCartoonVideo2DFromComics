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

  add(obj, { select = true } = {}) {
    this.root.add(obj);
    this.changed();
    if (select) this.select(obj);
  }

  get selected() {
    return this.selection[this.selection.length - 1] ?? null;
  }

  remove(obj) {
    if (this.selection.includes(obj)) {
      this.selection = this.selection.filter((o) => o !== obj);
      this.dispatchEvent(new Event('selection'));
    }
    this.root.remove(obj);
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
