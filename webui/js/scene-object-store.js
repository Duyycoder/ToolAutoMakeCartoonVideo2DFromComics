// Danh sách vật thể + vật đang chọn. Phát sự kiện để các panel tự vẽ lại:
//   'changed'   : thêm/xoá/đổi tên/đổi màu/ẩn hiện
//   'selection' : đổi vật đang chọn
//   'transform' : vật đang chọn vừa di chuyển/xoay/co giãn (chỉ cập nhật số liệu)
export class SceneObjectStore extends EventTarget {
  constructor(root) {
    super();
    this.root = root;
    this.selected = null;
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

  remove(obj) {
    if (this.selected === obj) this.select(null);
    this.root.remove(obj);
    this.changed();
  }

  select(obj) {
    if (this.selected === obj) return;
    this.selected = obj;
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
