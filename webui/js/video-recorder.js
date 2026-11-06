// Quay khung 3D thành video bằng MediaRecorder (MP4 nếu WebView2/Chrome hỗ trợ, không thì WebM).
const TYPES = ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];

export function pickVideoType() {
  const type = TYPES.find((t) => window.MediaRecorder?.isTypeSupported(t));
  return type ? { type, ext: type.startsWith('video/mp4') ? 'mp4' : 'webm' } : null;
}

/** Quay `canvas` trong lúc `play(onFrameDone)` chạy hết; trả về Blob video. */
export function recordCanvas(canvas, durationSec, { fps = 30 } = {}) {
  const picked = pickVideoType();
  if (!picked) return Promise.reject(new Error('Trình duyệt không hỗ trợ quay video.'));
  const stream = canvas.captureStream(fps);
  const recorder = new MediaRecorder(stream, { mimeType: picked.type, videoBitsPerSecond: 8_000_000 });
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  return new Promise((resolve, reject) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      resolve({ blob: new Blob(chunks, { type: picked.type }), ext: picked.ext });
    };
    recorder.onerror = (e) => reject(e.error ?? new Error('Quay video lỗi'));
    recorder.start(250);
    setTimeout(() => recorder.stop(), durationSec * 1000 + 150);
  });
}
