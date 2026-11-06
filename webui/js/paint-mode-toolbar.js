// Thanh công cụ nổi khi "Tô vẽ" (dùng chung style với thanh "Chỉnh điểm").
const SWATCHES = ['#f5f5f5', '#2b2d33', '#ff5c5c', '#ff9f43', '#f2c94c', '#5fd08a', '#56ccf2', '#5b8cff', '#8a5bff', '#e056fd', '#b07a4f', '#f7c6a3'];

export function createPaintToolbar(viewportEl, paintMode, placement) {
  const bar = Object.assign(document.createElement('div'), { className: 'edit-toolbar paint-toolbar', hidden: true });
  bar.innerHTML = `
    <div class="edit-row">
      <b class="edit-title">🖌 Tô vẽ: <span id="paint-name"></span></b>
      <div class="seg"><button data-brush="paint" title="Kéo trên vật để tô màu">🖌 Tô</button>
        <button data-brush="blur" title="Làm nhoè chỗ giáp ranh 2 màu">💧 Làm nhoè</button>
        <button data-brush="pick" title="Bấm lên vật để lấy màu ở chỗ đó">🎯 Hút màu</button></div>
      <label class="edit-color" title="Màu cọ">Màu<input type="color" id="paint-color"></label>
      <div class="paint-swatches" id="paint-swatches"></div>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button class="primary" data-op="exit" title="Xong (Enter)">✔ Xong</button>
    </div>
    <div class="edit-row">
      <label class="edit-soft" title="Phím [ và ]">Cỡ cọ <input type="range" id="paint-size" min="0" max="1" step="0.01"></label>
      <label class="edit-soft">Độ đậm <input type="range" id="paint-strength" min="0.05" max="1" step="0.05"></label>
      <span class="sep"></span>
      <button data-op="image" title="Chọn ảnh để dán lên vật (logo, hoa văn, mặt nhân vật...)">🖼 Dán ảnh…</button>
      <button data-op="fill" title="Tô cả vật bằng màu đang chọn">🪣 Tô hết 1 màu</button>
      <input type="file" id="paint-file" accept="image/png,image/jpeg,image/webp" hidden>
    </div>
    <div class="edit-row" id="paint-image-row" hidden>
      <b>🖼 Kéo ảnh để đặt chỗ</b>
      <label class="edit-soft">Cỡ ảnh <input type="range" id="paint-img-scale" min="0.2" max="3" step="0.05"></label>
      <label class="edit-soft">Độ đậm <input type="range" id="paint-img-opacity" min="0.1" max="1" step="0.05"></label>
      <button class="primary" data-op="apply-image">✔ Dán vào vật</button><button data-op="cancel-image">✕ Bỏ</button>
    </div>
    <div class="edit-hint">Kéo chuột trái trên vật để tô · bắt đầu kéo ngoài vật để xoay góc nhìn · lăn chuột để phóng to</div>`;
  viewportEl.append(bar);
  const $ = (sel) => bar.querySelector(sel);

  $('#paint-swatches').append(...SWATCHES.map((hex) => {
    const b = Object.assign(document.createElement('button'), { className: 'swatch', title: hex });
    b.style.background = hex;
    b.onclick = () => paintMode.setBrush({ color: hex, mode: paintMode.state.brush.mode === 'pick' ? 'paint' : paintMode.state.brush.mode });
    return b;
  }));
  const ops = {
    undo: () => paintMode.undo(), redo: () => paintMode.redo(), exit: () => paintMode.exit(),
    fill: () => paintMode.fill(), image: () => $('#paint-file').click(),
    'apply-image': () => placement.apply(), 'cancel-image': () => placement.cancel(),
  };
  bar.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (btn?.dataset.brush) paintMode.setBrush({ mode: btn.dataset.brush });
    if (btn?.dataset.op) ops[btn.dataset.op]();
  });
  $('#paint-color').oninput = (e) => paintMode.setBrush({ color: e.target.value });
  $('#paint-size').oninput = (e) => paintMode.setBrush({ size: Number(e.target.value) });
  $('#paint-strength').oninput = (e) => paintMode.setBrush({ strength: Number(e.target.value) });
  $('#paint-file').onchange = (e) => { if (e.target.files[0]) placement.open(e.target.files[0]); e.target.value = ''; };
  $('#paint-img-scale').oninput = (e) => placement.setScale(Number(e.target.value));
  $('#paint-img-opacity').oninput = (e) => placement.setOpacity(Number(e.target.value));

  return {
    update(info) {
      bar.hidden = !info;
      if (!info) { if (placement.active) placement.cancel(); return; } // thoát chế độ -> bỏ ảnh đang đặt
      $('#paint-name').textContent = info.name;
      bar.querySelectorAll('[data-brush]').forEach((b) => b.classList.toggle('active', b.dataset.brush === info.mode));
      $('#paint-color').value = info.color;
      $('#paint-size').value = info.size;
      $('#paint-strength').value = info.strength;
      $('[data-op="undo"]').disabled = !info.canUndo;
      $('[data-op="redo"]').disabled = !info.canRedo;
      const img = placement.values;
      $('#paint-image-row').hidden = !img;
      if (img) { $('#paint-img-scale').value = img.scale; $('#paint-img-opacity').value = img.opacity; }
    },
  };
}
