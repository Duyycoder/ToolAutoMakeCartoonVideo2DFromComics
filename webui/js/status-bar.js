// Thanh trạng thái: GPU, số vật thể/tam giác, mẹo theo ngữ cảnh. Ẩn/hiện gợi ý "cảnh trống".
import { api } from './backend-api-client.js';

export function initStatusBar(store) {
  const gpuEl = document.getElementById('status-gpu');
  const statsEl = document.getElementById('status-stats');
  const tipEl = document.getElementById('status-tip');
  const emptyHint = document.getElementById('empty-hint');

  api.gpuInfo().then((info) => {
    if (info.cuda_available) {
      const g = info.gpus[0];
      gpuEl.className = 'ok';
      gpuEl.textContent = `● GPU: ${g.name} (${Math.round(g.vram_total_mb / 1024)} GB)`;
    } else {
      gpuEl.className = 'warn';
      gpuEl.textContent = '● Không có GPU NVIDIA — AI chạy CPU (chậm)';
      gpuEl.title = `Card hình: ${info.other_adapters.join(', ') || 'không rõ'}`;
    }
  }).catch(() => {
    gpuEl.className = 'warn';
    gpuEl.textContent = '● Mất kết nối backend';
  });

  const update = () => {
    const n = store.objects.length;
    emptyHint.hidden = n > 0;
    statsEl.textContent = n ? `${n} vật thể · ${store.triangleCount().toLocaleString('vi-VN')} tam giác` : '';
    tipEl.textContent = store.selection.length > 1
      ? `Đã chọn ${store.selection.length} vật · Gộp / Nhóm ở panel bên phải`
      : store.selected
      ? 'Kéo mũi tên màu để di chuyển · Shift + bấm để chọn nhiều vật · Delete để xoá'
      : 'Bấm vào vật thể để chọn · Ctrl+Z để hoàn tác';
  };
  store.addEventListener('changed', update);
  store.addEventListener('selection', update);
  update();
}
