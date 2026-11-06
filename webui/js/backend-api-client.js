// Gọi backend FastAPI. Mọi request ghi (POST) phải có header X-Easy3D (chống CSRF, xem backend/main.py).
const WRITE_HEADERS = { 'X-Easy3D': '1' };

async function errorText(res) {
  try {
    const body = await res.json();
    return typeof body.detail === 'string' ? body.detail : `Lỗi ${res.status}`;
  } catch {
    return `Lỗi ${res.status}`;
  }
}

async function request(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error('Không kết nối được phần mềm nền (backend). Hãy mở lại Easy3D.');
  }
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

const post = (path, params, body) =>
  request(`${path}?${new URLSearchParams(params)}`, { method: 'POST', headers: WRITE_HEADERS, body });

export const api = {
  gpuInfo: () => request('/api/system/gpu-info'),
  aiStatus: () => request('/api/system/ai-status'),
  saveFile: (kind, name, data, folder = null) => post('/api/files/save', folder ? { kind, name, folder } : { kind, name }, data),
  openFolder: (kind, folder = null) => post('/api/files/open-folder', folder ? { kind, folder } : { kind }),
  listFiles: (kind) => request(`/api/files/list?${new URLSearchParams({ kind })}`).then((r) => r.files),
  readJson: (kind, name) => request(`/api/files/read?${new URLSearchParams({ kind, name })}`),
  startImageTo3D: (file, quality, model = 'triposr') => post('/api/image-to-3d', { filename: file.name, quality, model }, file),
  cancelJob: (id) => post(`/api/jobs/${id}/cancel`, {}),
  resultUrl: (id) => `/api/jobs/${id}/result.glb`,
  resultImageUrl: (id) => `/api/jobs/${id}/result.png`,
  skinWeightsUrl: (id) => `/api/jobs/${id}/skin-weights.bin`,
  blenderStatus: () => request('/api/blender/status'),
  runBlender: (op, params, blob) => post(`/api/blender/${op}`, { params: JSON.stringify(params) }, blob),

  /** Theo dõi tiến độ job qua SSE. Trả về hàm huỷ theo dõi. */
  watchJob(id, onEvent) {
    const source = new EventSource(`/api/jobs/${id}/events`);
    source.onmessage = (e) => {
      const event = JSON.parse(e.data);
      onEvent(event);
      if (event.type === 'status' && ['done', 'error', 'cancelled'].includes(event.status)) source.close();
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return;
      source.close();
      onEvent({ type: 'status', status: 'error', msg: 'Mất kết nối tới backend khi đang tạo mô hình.' });
    };
    return () => source.close();
  },
};
