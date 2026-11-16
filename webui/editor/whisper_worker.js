/* Web Worker: Whisper chạy TRONG TRÌNH DUYỆT (transformers.js + ONNX Runtime Web; WebGPU nếu có, không thì WASM).
 * Model giữ trong worker giữa các lượt → tạo phụ đề hàng loạt không nạp lại. Model tải từ Hugging Face lần đầu
 * rồi trình duyệt cache lại (Cache Storage). Nhận {id, model, audio(Float32Array 16 kHz mono), language};
 * gửi {id, tai: tiến độ tải model} / {id, giai_doan} / {id, xong: [{timestamp:[a,b], text}]} / {id, loi}. */
// transformers.min.js (KHÔNG phải .web.min.js: bản đó còn import trần 'onnxruntime-web/webgpu', trình duyệt không phân giải được).
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1/dist/transformers.min.js';

env.allowLocalModels = false;
let asr = null;
let tenModel = '';
let thietBi = '';

async function coWebGpu() {
    try { return !!(navigator.gpu && await navigator.gpu.requestAdapter()); } catch { return false; }
}

async function napModel(id, model) {
    if (asr && tenModel === model) return;
    asr = null;
    thietBi = (await coWebGpu()) ? 'webgpu' : 'wasm';
    self.postMessage({ id, giai_doan: `Nạp model ${model.split('/').pop()} (${thietBi === 'webgpu' ? 'GPU' : 'CPU'})…` });
    // WebGPU: encoder fp32 (fp16 cần shader-f16, nhiều máy không có), decoder q4 cho nhẹ; WASM: q8 cả hai.
    const dtype = thietBi === 'webgpu' ? { encoder_model: 'fp32', decoder_model_merged: 'q4' } : 'q8';
    asr = await pipeline('automatic-speech-recognition', model, {
        device: thietBi, dtype,
        progress_callback: (p) => { if (p.status === 'progress') self.postMessage({ id, tai: { file: p.file, pct: p.progress } }); },
    });
    tenModel = model;
}

self.onmessage = async ({ data }) => {
    const { id, model, audio, language } = data;
    try {
        await napModel(id, model);
        self.postMessage({ id, giai_doan: `Đang nhận giọng (${thietBi === 'webgpu' ? 'GPU' : 'CPU'})…` });
        const out = await asr(audio, {
            language, task: 'transcribe', return_timestamps: true, chunk_length_s: 30, stride_length_s: 5,
        });
        self.postMessage({ id, xong: out.chunks || [] });
    } catch (e) {
        self.postMessage({ id, loi: (e && e.message) || String(e) });
    }
};
