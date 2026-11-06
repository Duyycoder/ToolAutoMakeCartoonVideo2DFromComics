// Hộp thoại "Xuất ảnh": chọn độ phân giải, nền trong suốt, ẩn lưới — render đúng góc nhìn hiện tại.
import { openModal } from './modal-dialog.js';

const SIZES = [
  ['screen', 'Như màn hình', null],
  ['hd', 'HD 1280×720', [1280, 720]],
  ['fhd', 'Full HD 1920×1080', [1920, 1080]],
  ['4k', '4K 3840×2160', [3840, 2160]],
  ['square', 'Vuông 2048×2048 (ảnh đại diện)', [2048, 2048]],
];

/** onExport(dataUrl) được gọi sau khi render xong. */
export function openImageExportDialog({ viewport, onExport, cycles = null }) {
  const dlg = openModal();
  dlg.modal.innerHTML = `
    <button class="modal-close" title="Đóng (Esc)">✕</button>
    <h2>📸 Xuất ảnh</h2>
    <p class="sub">Chụp đúng góc nhìn đang thấy. Xoay camera trước để có góc đẹp nhất.</p>
    <div class="wizard-grid">
      <div><b>Kích thước</b><div class="quality" id="sizes" style="margin-top:8px"></div></div>
      <div><b>Tuỳ chọn</b><div class="quality" style="margin-top:8px">
        <label><input type="checkbox" id="transparent"><span><b>Nền trong suốt</b>
          <small>Để ghép vào ảnh/video khác</small></span></label>
        <label><input type="checkbox" id="hide" checked><span><b>Ẩn lưới sàn & tay cầm</b>
          <small>Ảnh sạch, chỉ còn vật thể và bóng đổ</small></span></label>
        <label id="cycles-row"><input type="checkbox" id="cycles"><span><b>🟠 Render đẹp bằng Blender (Cycles)</b>
          <small id="cycles-hint">Ánh sáng, bóng, phản chiếu thật — chậm hơn (vài chục giây tới vài phút)</small></span></label>
      </div></div>
    </div>
    <div class="modal-footer"><button id="cancel">Huỷ</button><button class="primary" id="go">Xuất ảnh</button></div>`;

  const sizes = dlg.modal.querySelector('#sizes');
  for (const [key, label] of SIZES) {
    const row = document.createElement('label');
    row.innerHTML = `<input type="radio" name="size" value="${key}"${key === 'fhd' ? ' checked' : ''}><span><b></b></span>`;
    row.querySelector('b').textContent = label;
    sizes.append(row);
  }
  if (!cycles?.ready) { // chưa cài Blender -> tắt lựa chọn, ghi cách cài
    dlg.modal.querySelector('#cycles').disabled = true;
    dlg.modal.querySelector('#cycles-row').classList.add('unavailable');
    dlg.modal.querySelector('#cycles-hint').textContent = cycles?.message ?? 'Chưa cài Blender.';
  }
  dlg.modal.querySelector('.modal-close').onclick = dlg.close;
  dlg.modal.querySelector('#cancel').onclick = dlg.close;
  dlg.modal.querySelector('#go').onclick = async () => {
    const key = dlg.modal.querySelector('input[name=size]:checked').value;
    const screen = viewport.canvasSize();
    const [width, height] = SIZES.find((s) => s[0] === key)[2] ?? [screen.x, screen.y];
    const transparent = dlg.modal.querySelector('#transparent').checked;
    if (dlg.modal.querySelector('#cycles').checked) {
      dlg.close();
      return onExport(null, `${width}×${height} (Cycles)`, () => cycles.render({ width, height, transparent }));
    }
    const dataUrl = viewport.renderImage({
      width, height, transparent,
      hideHelpers: dlg.modal.querySelector('#hide').checked,
    });
    dlg.close();
    await onExport(dataUrl, `${width}×${height}`);
  };
}
