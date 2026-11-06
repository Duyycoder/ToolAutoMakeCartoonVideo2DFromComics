// Danh sách "Vật thể trong cảnh": bấm để chọn, con mắt để ẩn/hiện.
import { iconFor } from './primitive-shape-factory.js';

export function createOutliner(listEl, store) {
  function render() {
    listEl.replaceChildren();
    if (!store.objects.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'Chưa có vật thể nào';
      listEl.append(li);
      return;
    }
    for (const obj of store.objects) {
      const li = document.createElement('li');
      li.classList.toggle('selected', obj === store.selected);
      li.classList.toggle('hidden-obj', !obj.visible);
      li.title = 'Bấm để chọn';

      const icon = document.createElement('span');
      icon.textContent = iconFor(obj);
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = obj.name || '(không tên)';
      const eye = document.createElement('button');
      eye.className = 'eye';
      eye.textContent = obj.visible ? '👁' : '🙈';
      eye.title = obj.visible ? 'Ẩn vật thể' : 'Hiện vật thể';
      eye.onclick = (e) => {
        e.stopPropagation();
        obj.visible = !obj.visible;
        if (!obj.visible && store.selected === obj) store.select(null);
        store.changed();
      };

      li.append(icon, name, eye);
      li.onclick = () => store.select(obj);
      listEl.append(li);
    }
  }

  store.addEventListener('changed', render);
  store.addEventListener('selection', render);
  render();
}
