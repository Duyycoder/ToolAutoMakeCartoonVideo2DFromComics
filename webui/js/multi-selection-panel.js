// Panel khi chọn NHIỀU vật (Shift + bấm): gộp, ghép liền, nhóm lại, tô cùng màu, nhân bản, xoá.
const COLORS = ['#f5f5f5', '#2b2d33', '#ff5c5c', '#ff9f43', '#f2c94c', '#5fd08a', '#56ccf2', '#5b8cff', '#8a5bff', '#e056fd'];

const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};

export function multiSelectionSection(objs, { actions, meshTools }) {
  const bigButton = (icon, title, hint, onClick, cls = '') => Object.assign(
    el('button', { className: `big-action ${cls}` }, [
      el('span', { className: 'ico', textContent: icon }),
      el('span', {}, [el('b', { textContent: title }), el('small', { textContent: hint })]),
    ]), { onclick: onClick });

  const swatches = el('div', { className: 'swatches' }, COLORS.map((hex) => {
    const sw = el('button', { className: 'swatch', title: hex });
    sw.style.background = hex;
    sw.onclick = () => actions.setColorMany(objs, hex);
    return sw;
  }));

  return el('div', {}, [
    el('div', { className: 'multi-head' }, [
      el('b', { textContent: `Đã chọn ${objs.length} vật` }),
      el('small', { textContent: objs.map((o) => o.name).join(', ') }),
    ]),
    bigButton('🔗', 'Gộp thành 1 vật', 'Dính lại thành 1, mỗi phần giữ màu riêng', () => meshTools.many.join(objs), 'primary-soft'),
    bigButton('➕', 'Ghép liền thành 1 khối', 'Nối liền chỗ chồng nhau, bỏ phần thừa bên trong (hợp để in 3D)',
      () => meshTools.many.union(objs)),
    bigButton('📦', 'Nhóm lại (Ctrl+G)', 'Vẫn là các vật riêng nhưng chọn & di chuyển cùng nhau', () => meshTools.many.group(objs)),
    el('div', { className: 'field', style: 'margin-top:14px' }, [el('label', { textContent: 'Tô tất cả cùng 1 màu' }), swatches]),
    el('div', { className: 'field btn-grid' }, [
      Object.assign(el('button', { textContent: '⧉ Nhân bản tất cả', title: 'Ctrl+D' }), { onclick: () => actions.duplicateMany(objs) }),
      Object.assign(el('button', { textContent: '🗑 Xoá tất cả', className: 'danger', title: 'Delete' }), { onclick: () => actions.removeMany(objs) }),
    ]),
    el('div', { className: 'info-line', textContent: 'Kéo mũi tên để di chuyển cả nhóm · Shift + bấm để thêm/bỏ vật · Ctrl+A chọn hết' }),
  ]);
}
