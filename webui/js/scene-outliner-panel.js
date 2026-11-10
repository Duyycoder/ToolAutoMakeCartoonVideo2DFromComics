// Danh sách "Vật thể trong cảnh" dạng cây như thư mục (giống Hierarchy của Unity): ▸ mở các phần bên trong
// (model FBX nhiều phần, nhóm, nhân mảng). Bấm để chọn — chọn được cả phần con để di chuyển/đổi màu riêng
// (phần con đi theo vật cha). Con mắt để ẩn/hiện.
import { iconFor } from './primitive-shape-factory.js';

/** Phần con đáng hiện: có hình (lưới) bên trong. Bỏ xương và nút rỗng; đèn không mở ra. */
function childrenOf(obj) {
  if (obj.userData.kind === 'light') return [];
  return obj.children.filter((c) => {
    if (c.isBone) return false;
    let hasMesh = false;
    c.traverse((o) => { hasMesh ||= o.isMesh; });
    return hasMesh;
  });
}

export function createOutliner(listEl, store) {
  const expanded = new WeakSet();

  /** Vật đang chọn nằm sâu trong cây -> mở các cấp cha để thấy dòng của nó. */
  function revealSelection() {
    for (const obj of store.selection) {
      for (let p = obj.parent; p && p !== store.root; p = p.parent) expanded.add(p);
    }
  }

  function row(obj, depth) {
    const li = document.createElement('li');
    li.classList.toggle('selected', store.selection.includes(obj));
    li.classList.toggle('hidden-obj', !obj.visible);
    li.style.paddingLeft = `${8 + depth * 16}px`;
    li.title = depth ? 'Bấm để chọn phần này (đi theo vật chứa nó) · Shift + bấm để chọn nhiều'
      : 'Bấm để chọn · Shift + bấm để chọn nhiều';

    const kids = childrenOf(obj);
    const toggle = document.createElement('button');
    toggle.className = 'twisty';
    toggle.disabled = !kids.length;
    if (kids.length) {
      toggle.textContent = expanded.has(obj) ? '▾' : '▸';
      toggle.title = `Gồm ${kids.length} phần — bấm để ${expanded.has(obj) ? 'thu gọn' : 'xem'}`;
      toggle.onclick = (e) => {
        e.stopPropagation();
        if (expanded.has(obj)) expanded.delete(obj); else expanded.add(obj);
        render();
      };
    }
    const icon = document.createElement('span');
    icon.textContent = iconFor(obj);
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = obj.name || '(không tên)';
    const eye = document.createElement('button');
    eye.className = 'eye';
    eye.textContent = obj.visible ? '👁' : '🙈';
    eye.title = obj.visible ? 'Ẩn' : 'Hiện';
    eye.onclick = (e) => {
      e.stopPropagation();
      obj.visible = !obj.visible;
      if (!obj.visible && store.selection.includes(obj)) store.toggleSelect(obj);
      store.changed();
    };
    li.append(toggle, icon, name, eye);
    li.onclick = (e) => (e.shiftKey || e.ctrlKey ? store.toggleSelect(obj) : store.select(obj));
    listEl.append(li);
    if (kids.length && expanded.has(obj)) kids.forEach((c) => row(c, depth + 1));
  }

  function render() {
    listEl.replaceChildren();
    if (!store.objects.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'Chưa có vật thể nào';
      listEl.append(li);
      return;
    }
    revealSelection();
    store.objects.forEach((obj) => row(obj, 0));
  }

  store.addEventListener('changed', render);
  store.addEventListener('selection', render);
  render();
}
