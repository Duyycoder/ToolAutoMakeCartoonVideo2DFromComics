// Thanh công cụ nổi phía trên khung 3D khi đang "Chỉnh điểm".
export function createEditToolbar(viewportEl, editMode, input) {
  const bar = document.createElement('div');
  bar.className = 'edit-toolbar';
  bar.hidden = true;
  bar.innerHTML = `
    <div class="edit-row">
      <b class="edit-title">✏ Chỉnh điểm: <span id="edit-name"></span></b>
      <div class="seg"><button data-sel="vertex" title="Chọn từng điểm (phím 1)">• Điểm</button>
        <button data-sel="face" title="Chọn từng mặt (phím 2)">▲ Mặt</button></div>
      <div class="seg"><button data-tool="click" title="Bấm vào điểm/mặt để chọn. Shift: chọn thêm">👆 Bấm chọn</button>
        <button data-tool="box" title="Kéo chuột vẽ khung để chọn nhiều. Chuột phải vẫn kéo khung nhìn">⬚ Kéo khung</button></div>
      <label class="edit-check" title="Chọn cả điểm bị che ở mặt sau"><input type="checkbox" id="edit-through"> Xuyên qua</label>
      <span class="edit-count" id="edit-count"></span>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button class="primary" data-op="exit" title="Xong (Tab)">✔ Xong</button>
    </div>
    <div class="edit-row">
      <button data-op="selectAll" title="Chọn / bỏ chọn tất cả (phím A)">Chọn hết</button>
      <button data-op="grow" title="Chọn thêm 1 vòng điểm xung quanh">Chọn rộng thêm</button>
      <label class="edit-soft" title="Các điểm quanh vùng chọn đi theo, càng xa càng ít">Kéo mềm
        <input type="range" id="edit-soft" min="0" max="1" step="0.05" value="0"></label>
      <span class="sep"></span>
      <button data-op="extrude" title="Đùn các mặt chọn ra ngoài (như kéo ống, mọc tay chân)">⬆ Đùn ra</button>
      <button data-op="smoothSelection" title="Làm mượt vùng chọn">〰 Làm mượt</button>
      <button data-op="mergeSelection" title="Dồn các điểm chọn về 1 điểm (vuốt nhọn, khép lỗ)">⊙ Dồn vào giữa</button>
      <label class="edit-color" title="Tô màu vùng chọn">🎨 Tô màu<input type="color" id="edit-color" value="#ff5c5c"></label>
      <button data-op="separate" title="Tách các mặt chọn thành vật riêng">✂ Tách ra</button>
      <button data-op="deleteSelection" class="danger" title="Xoá điểm/mặt chọn (Delete)">🗑 Xoá</button>
      <button data-op="subdivide" title="Chia nhỏ lưới để có thêm điểm chỉnh chi tiết">➕ Thêm điểm</button>
    </div>
    <div class="edit-hint">Bấm vào điểm để chọn · Shift + bấm: chọn thêm · Kéo mũi tên để di chuyển · W/E/R: di chuyển/xoay/co giãn</div>`;
  viewportEl.append(bar);

  bar.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.sel) editMode.setSelectMode(btn.dataset.sel);
    if (btn.dataset.tool) editMode.setTool(btn.dataset.tool);
    if (btn.dataset.op) editMode[btn.dataset.op]();
  });
  bar.querySelector('#edit-soft').oninput = (e) => editMode.setSoft(Number(e.target.value));
  bar.querySelector('#edit-color').onchange = (e) => editMode.colorize(e.target.value);
  bar.querySelector('#edit-through').onchange = (e) => input.setThroughAll(e.target.checked);

  return {
    update(info) {
      bar.hidden = !info;
      if (!info) return;
      bar.querySelector('#edit-name').textContent = info.name;
      bar.querySelectorAll('[data-sel]').forEach((b) => b.classList.toggle('active', b.dataset.sel === info.mode));
      bar.querySelectorAll('[data-tool]').forEach((b) => b.classList.toggle('active', b.dataset.tool === info.tool));
      bar.querySelector('#edit-count').textContent = info.mode === 'vertex'
        ? `Đã chọn ${info.vertices} điểm` : `Đã chọn ${info.faces} mặt`;
      bar.querySelector('[data-op="undo"]').disabled = !info.canUndo;
      bar.querySelector('[data-op="redo"]').disabled = !info.canRedo;
      bar.querySelector('#edit-soft').value = info.soft;
    },
  };
}
