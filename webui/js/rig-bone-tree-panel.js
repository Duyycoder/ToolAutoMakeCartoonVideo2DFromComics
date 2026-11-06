// Panel "Cây xương" (nổi bên phải khung 3D khi Ghép xương): đặt tên nhân vật, cây khớp cha -> con (bấm chọn,
// bấm đúp đổi tên), khớp đang chọn: tên cho game, toạ độ (cm), thêm/xoá khớp; tên chuẩn Unity, lưu mẫu xương.
import * as THREE from 'three';
import { saveRigTemplate } from './rig-template-library.js';
import { toast } from './toast-notifications.js';

const h = (tag, props = {}, kids = []) => {
  const el = Object.assign(document.createElement(tag), props);
  el.append(...kids);
  return el;
};

function depthsOf(tree) {
  const depth = (i) => (tree[i].parent < 0 ? 0 : 1 + depth(tree[i].parent));
  return tree.map((_, i) => depth(i));
}

export function createBoneTreePanel(viewportEl, rigMode, { onTemplateSaved }) {
  const panel = h('aside', { className: 'rig-tree-panel', hidden: true });
  viewportEl.append(panel);
  // Nút trong panel làm panel vẽ lại -> nút bị tách khỏi DOM; chặn click lan lên app (app sẽ tưởng bấm ngoài và thoát chế độ).
  panel.addEventListener('click', (e) => e.stopPropagation());

  function renameInline(li, i, current) {
    const input = h('input', { type: 'text', value: current, className: 'rig-rename', spellcheck: false });
    li.replaceChildren(input);
    input.focus();
    input.select();
    const done = (save) => { if (save && input.value.trim() !== current) rigMode.naming.rename(i, input.value); else update(rigMode.info()); };
    input.onkeydown = (e) => { e.stopPropagation(); if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); };
    input.onblur = () => done(true);
  }

  function treeList(info) {
    const tree = rigMode.tree(), depth = depthsOf(tree);
    return h('ul', { className: 'rig-tree' }, tree.map((b, i) => {
      const li = h('li', { title: info.stage === 'pose' ? 'Bấm: chọn · Shift + bấm: thêm/bỏ chọn · Bấm đúp: đổi tên' : 'Bấm: chọn · Bấm đúp: đổi tên' }, [
        h('span', { className: 'rig-label', textContent: b.label }),
        h('small', { textContent: b.name === b.label ? '' : b.name }),
      ]);
      li.style.paddingLeft = `${6 + depth[i] * 12}px`;
      li.classList.toggle('selected', info.selectedIndices.includes(i));
      li.onclick = (e) => rigMode.select(i, e.shiftKey);
      li.ondblclick = () => renameInline(li, i, b.name);
      return li;
    }));
  }

  function selectedSection(info) {
    const i = info.index;
    const name = h('input', { type: 'text', value: info.selectedName, spellcheck: false, title: 'Tên xương xuất ra file (Unity đọc tên này)' });
    name.onchange = () => { if (!rigMode.naming.rename(i, name.value)) name.value = info.selectedName; };
    const rows = [h('label', { className: 'rig-field' }, ['Tên cho game', name])];
    if (info.stage === 'place') {
      const world = rigMode.place.worldPosition(i);
      const inputs = ['x', 'y', 'z'].map((ax) => h('input', { type: 'number', step: '0.5', value: (world[ax] * 100).toFixed(1), title: `Toạ độ ${ax.toUpperCase()} (cm)` }));
      const apply = () => rigMode.place.setWorldPosition(i, new THREE.Vector3(...inputs.map((el) => Number(el.value) / 100)));
      inputs.forEach((el) => { el.onchange = apply; el.onkeydown = (e) => e.stopPropagation(); });
      rows.push(h('div', { className: 'rig-field' }, ['X · Y · Z (cm)', h('div', { className: 'rig-xyz' }, inputs)]));
      rows.push(h('div', { className: 'rig-actions' }, [
        h('button', { textContent: '＋ Khớp con', title: 'Thêm 1 khớp nối tiếp khớp đang chọn', onclick: () => rigMode.place.addChild() }),
        h('button', { textContent: '◎ Vào giữa', title: 'Đưa khớp này vào giữa bề dày (trước-sau)', onclick: () => rigMode.place.centerDepth(false) }),
        h('button', { textContent: '🗑 Xoá', title: 'Xoá khớp; khớp con nối vào khớp cha', onclick: () => rigMode.place.removeSelected() }),
      ]));
    }
    return h('div', { className: 'rig-selected' }, rows);
  }

  function footer(info) {
    const kids = [h('button', { textContent: '🏷 Tên chuẩn Unity', title: 'Đổi tên tiếng Việt (bản cũ) sang Hips, Spine, LeftUpperArm...', onclick: () => rigMode.naming.unityNames() })];
    if (info.stage === 'place') {
      kids.push(h('button', { textContent: '◎ Tất cả vào giữa', title: 'Đưa mọi khớp vào giữa bề dày', onclick: () => rigMode.place.centerDepth(true) }));
      const tplName = h('input', { type: 'text', placeholder: 'Tên mẫu, vd. Golem', spellcheck: false });
      tplName.onkeydown = (e) => e.stopPropagation();
      const save = async () => {
        const n = tplName.value.trim();
        if (!n) return toast('Gõ tên mẫu trước khi lưu.', { type: 'warn' });
        try {
          const res = await saveRigTemplate(rigMode.templateOf(n));
          toast(`Đã lưu mẫu xương: ${res.name} — chọn lại ở "📁 Mẫu đã lưu".`, { type: 'ok', timeout: 6000 });
          onTemplateSaved();
        } catch (err) { toast(`Lưu mẫu thất bại: ${err.message}`, { type: 'err' }); }
      };
      kids.push(h('div', { className: 'rig-save' }, [tplName, h('button', { textContent: '💾 Lưu mẫu', onclick: save })]));
    }
    return h('div', { className: 'rig-actions col' }, kids);
  }

  function update(info) {
    panel.hidden = !info;
    if (!info) return;
    const objName = h('input', { type: 'text', value: info.name, spellcheck: false, title: 'Tên nhân vật = tên file + thư mục khi xuất cho game' });
    objName.onchange = () => rigMode.naming.renameObject(objName.value);
    objName.onkeydown = (e) => e.stopPropagation();
    panel.replaceChildren(
      h('h4', { textContent: '🗂 Cây xương' }),
      h('label', { className: 'rig-field' }, ['Tên nhân vật', objName]),
      treeList(info),
      ...(info.index >= 0 ? [selectedSection(info)] : []),
      footer(info),
    );
  }

  return { update };
}
