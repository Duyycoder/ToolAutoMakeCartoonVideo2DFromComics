/* Tạo phụ đề bằng Whisper chạy TRÊN MÁY người dùng (trình duyệt) — không cần server/laptop có Whisper.
 * Server chỉ trả tiếng mono 16 kHz (`/media/{mid}/tieng-16k`, vài MB) thay vì cả video gốc; worker
 * (whisper_worker.js) nhận giọng, kết quả áp vào timeline như việc AI của server (BangAi.apDung). */
import { toast } from './chung.js';

// Model chọn ở bảng AI → model ONNX cho trình duyệt. Trình duyệt chỉ chạy nổi tới small;
// PhoWhisper/medium/large → small (đa ngôn ngữ).
const MODEL = { tiny: 'onnx-community/whisper-tiny', base: 'onnx-community/whisper-base' };
const MA_NGON_NGU = { English: 'en', Chinese: 'zh', Japanese: 'ja', Korean: 'ko', Vietnamese: 'vi',
    Thai: 'th', Indonesian: 'id', Spanish: 'es' };

let worker = null;
let soLuot = 0;

export function modelTrinhDuyet(ten) { return MODEL[ten] || 'onnx-community/whisper-small'; }

/** Chuyển kết quả transformers.js thành câu {t_vao, t_ra, text}; bỏ câu rỗng, đoạn cuối thiếu giờ ra lấy `dai`. */
export function thanhCau(chunks, dai) {
    return (chunks || []).map((c) => {
        const [a, b] = c.timestamp || [];
        return { t_vao: Math.max(0, Number(a) || 0), t_ra: Number(b ?? dai) || dai, text: String(c.text || '').trim() };
    }).filter((c) => c.text && c.t_ra > c.t_vao);
}

async function docTieng(url) {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(`Không lấy được tiếng của video (${r.status}).`);
    const buf = await r.arrayBuffer();
    const ac = new OfflineAudioContext(1, 1, 16000);   // giải mã + đưa về 16 kHz
    const a = await ac.decodeAudioData(buf);
    if (a.numberOfChannels === 1) return a.getChannelData(0);
    const tron = new Float32Array(a.length);
    for (let k = 0; k < a.numberOfChannels; k += 1) a.getChannelData(k).forEach((v, i) => { tron[i] += v / a.numberOfChannels; });
    return tron;
}

function chayWorker(model, audio, language, bao) {
    if (!worker) worker = new Worker(new URL('./whisper_worker.js', import.meta.url), { type: 'module' });
    const id = ++soLuot;
    return new Promise((ok, loi) => {
        const thoi = () => { worker.removeEventListener('message', nghe); worker.removeEventListener('error', hong); };
        const nghe = ({ data }) => {
            if (data.id !== id) return;
            if (data.tai) bao(`Tải model lần đầu: ${Math.round(data.tai.pct || 0)}% (${data.tai.file || ''})`);
            else if (data.giai_doan) bao(data.giai_doan);
            else {
                thoi();
                if (data.loi) loi(new Error(data.loi)); else ok(data.xong);
            }
        };
        // Worker không nạp được (mất mạng tới CDN, trình duyệt cũ không có module worker) → báo lỗi, không treo.
        const hong = (e) => {
            thoi();
            worker = null;
            loi(new Error(`Không chạy được Whisper trong trình duyệt: ${e.message || 'không nạp được thư viện (cần mạng)'}`));
        };
        worker.addEventListener('message', nghe);
        worker.addEventListener('error', hong);
        worker.postMessage({ id, model, audio, language }, [audio.buffer]);
    });
}

/** Tạo phụ đề cho media `mid` trên máy này rồi áp vào timeline. `ts` = tham số phu-de của bảng AI. */
export async function taoPhuDeTrenMay(bangAi, mid, ts) {
    const ctx = bangAi.ctx;
    const m = ctx.media.find((x) => x.id === mid);
    const nhan = `Tạo phụ đề trên máy — ${m ? m.ten : mid}`;
    const o = toast(`${nhan}: lấy tiếng…`, 'info', 24 * 3600 * 1000);
    const bao = (t) => { o.textContent = `${nhan}: ${t}`; };
    try {
        const audio = await docTieng(`/api/du-an/${encodeURIComponent(ctx.id)}/media/${encodeURIComponent(mid)}/tieng-16k`);
        const dai = audio.length / 16000;
        const t0 = performance.now();
        const chunks = await chayWorker(modelTrinhDuyet(ts.whisper_model), audio, MA_NGON_NGU[ts.source_lang], bao);
        const cau = thanhCau(chunks, dai);
        if (!cau.length) throw new Error('Không nhận ra câu nào (video không có lời, hoặc sai ngôn ngữ nói).');
        o.remove();
        await bangAi.apDung({ id: `tb-${Date.now()}`, tren_may: true, loai: 'phu-de', media: mid,
            nhan: `${nhan} (${Math.round((performance.now() - t0) / 1000)} s)`, ket_qua: { cau } }, true);
    } catch (e) {
        o.remove();
        throw e;
    }
}
