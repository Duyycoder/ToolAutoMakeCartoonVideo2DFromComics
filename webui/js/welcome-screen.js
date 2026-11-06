// Màn hình chào: 3 lựa chọn lớn + mẹo dùng chuột. Mở lại bằng nút "? Hướng dẫn".
import { openModal } from './modal-dialog.js';

const HIDE_KEY = 'easy3d.hideWelcome';

export const shouldShowWelcome = () => localStorage.getItem(HIDE_KEY) !== '1';

export function showWelcome({ onImage, onShapes, onOpen }) {
  const dlg = openModal();
  dlg.modal.innerHTML = `
    <button class="modal-close" title="Đóng (Esc)">✕</button>
    <h2>Chào mừng tới Easy3D 👋</h2>
    <p class="sub">Làm mô hình 3D không cần biết gì về 3D. Bạn muốn bắt đầu thế nào?</p>
    <div class="welcome-cards">
      <button class="welcome-card ai" data-choice="image">
        <span class="big">🪄</span><b>Tạo từ ảnh</b>
        <small>Chọn 1 tấm ảnh đồ vật / nhân vật, AI dựng thành mô hình 3D.</small>
      </button>
      <button class="welcome-card" data-choice="shapes">
        <span class="big">🧊</span><b>Ghép từ khối có sẵn</b>
        <small>Thêm hộp, cầu, trụ... rồi kéo, xoay, tô màu như xếp đồ chơi.</small>
      </button>
      <button class="welcome-card" data-choice="open">
        <span class="big">📂</span><b>Mở file có sẵn</b>
        <small>Mở mô hình GLB, GLTF, OBJ, STL, FBX, MESHY, BLEND hoặc dự án đã lưu.</small>
      </button>
    </div>
    <div class="tips">
      <div><b>🖱 Xoay góc nhìn</b>Giữ chuột trái và kéo</div>
      <div><b>✋ Kéo khung nhìn</b>Giữ chuột phải và kéo</div>
      <div><b>🔍 Phóng to</b>Lăn bánh xe chuột</div>
      <div><b>👆 Chọn vật</b>Bấm vào vật, kéo mũi tên màu để di chuyển</div>
      <div><b>↶ Lỡ tay?</b>Ctrl+Z hoàn tác mọi thao tác</div>
      <div><b>📥 Kéo thả</b>Thả ảnh hoặc file 3D thẳng vào khung nhìn</div>
    </div>
    <div class="modal-footer">
      <label><input type="checkbox" id="hide-welcome"> Không hiện lại khi mở app</label>
      <button class="primary" data-choice="close">Vào làm luôn</button>
    </div>`;

  const hide = dlg.modal.querySelector('#hide-welcome');
  hide.checked = !shouldShowWelcome();
  hide.onchange = () => localStorage.setItem(HIDE_KEY, hide.checked ? '1' : '0');

  const handlers = { image: onImage, shapes: onShapes, open: onOpen };
  dlg.modal.querySelector('.modal-close').onclick = dlg.close;
  dlg.modal.querySelectorAll('[data-choice]').forEach((btn) => {
    btn.onclick = () => {
      dlg.close();
      handlers[btn.dataset.choice]?.();
    };
  });
}
