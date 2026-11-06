// Thanh công cụ nổi khi "Nặn hình" (dùng chung style với thanh "Chỉnh điểm").
const BRUSHES = [
  ['draw', '⬆ Đắp', 'Đắp thêm đất, làm phồng lên (phím 1). Giữ Shift để lõm'],
  ['carve', '⬇ Lõm', 'Ấn lõm xuống (phím 2). Giữ Shift để đắp'],
  ['grab', '✋ Kéo', 'Kéo cả vùng theo chuột — kéo dài mũi, tai, tay (phím 3)'],
  ['smooth', '〰 Làm mượt', 'Xoá gồ ghề (phím 4)'],
  ['flatten', '▭ Làm phẳng', 'Mài phẳng bề mặt (phím 5)'],
];

export function createSculptToolbar(viewportEl, sculptMode) {
  const bar = Object.assign(document.createElement('div'), { className: 'edit-toolbar sculpt-toolbar', hidden: true });
  bar.innerHTML = `
    <div class="edit-row">
      <b class="edit-title">🗿 Nặn hình: <span id="sculpt-name"></span></b>
      <div class="seg" id="sculpt-brushes"></div>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button class="primary" data-op="exit" title="Xong (Enter)">✔ Xong</button>
    </div>
    <div class="edit-row">
      <label class="edit-soft" title="Phím [ và ]">Cỡ cọ <input type="range" id="sculpt-size" min="0" max="1" step="0.01"></label>
      <label class="edit-soft">Độ mạnh <input type="range" id="sculpt-strength" min="0.05" max="1" step="0.05"></label>
      <label class="edit-check" title="Nặn một bên, bên kia tự nặn giống hệt (phím X)">
        <input type="checkbox" id="sculpt-symmetry"> Đối xứng trái ↔ phải</label>
    </div>
    <div class="edit-hint">Kéo trên vật để nặn · bắt đầu kéo ngoài vật để xoay góc nhìn · lăn chuột để phóng to</div>`;
  viewportEl.append(bar);
  const $ = (sel) => bar.querySelector(sel);

  $('#sculpt-brushes').append(...BRUSHES.map(([key, label, title]) => {
    const b = Object.assign(document.createElement('button'), { textContent: label, title });
    b.dataset.sculpt = key;
    b.onclick = () => sculptMode.setBrush({ mode: key });
    return b;
  }));

  const ops = { undo: () => sculptMode.undo(), redo: () => sculptMode.redo(), exit: () => sculptMode.exit() };
  bar.addEventListener('click', (e) => {
    const op = e.target.closest('button')?.dataset.op;
    if (op) ops[op]();
  });
  $('#sculpt-size').oninput = (e) => sculptMode.setBrush({ size: Number(e.target.value) });
  $('#sculpt-strength').oninput = (e) => sculptMode.setBrush({ strength: Number(e.target.value) });
  $('#sculpt-symmetry').onchange = (e) => sculptMode.setBrush({ symmetry: e.target.checked });

  return {
    update(info) {
      bar.hidden = !info;
      if (!info) return;
      $('#sculpt-name').textContent = info.name;
      bar.querySelectorAll('[data-sculpt]').forEach((b) => b.classList.toggle('active', b.dataset.sculpt === info.mode));
      $('#sculpt-size').value = info.size;
      $('#sculpt-strength').value = info.strength;
      $('#sculpt-symmetry').checked = info.symmetry;
      $('[data-op="undo"]').disabled = !info.canUndo;
      $('[data-op="redo"]').disabled = !info.canRedo;
    },
  };
}
