/* 🪄 Bảng AI: Whisper, OCR sub cứng (kéo vùng trên xem trước), Dịch, Lồng tiếng.
 *
 * Tác vụ chạy ở hàng đợi GPU của server (mỗi lúc một việc nặng) và trả FILE RỜI. Kết quả
 * chỉ vào timeline khi bấm [Áp dụng] — là một lệnh hoàn tác được. Đóng app giữa chừng thì
 * mở lại thấy tác vụ "bị ngắt" với nút Chạy lại. */
import { api, esc, toast, hoi } from './chung.js';
import { veDieuKhien, bindDieuKhien } from './chon_giong.js';
import {
    tao, cauCuaMedia, opsThemCau, opsXoaNhieu, clipTai, idClipMoi, idMoiNhieu, clipChuaMedia, idTrackMoi, choTrong, opsThemTrack
} from './store.js';

const NGON_NGU = [['English', 'Tiếng Anh'], ['Chinese', 'Tiếng Trung'], ['Japanese', 'Tiếng Nhật'], ['Korean', 'Tiếng Hàn'],
    ['Vietnamese', 'Tiếng Việt'], ['Thai', 'Tiếng Thái'], ['Indonesian', 'Tiếng Indonesia'], ['Spanish', 'Tiếng Tây Ban Nha']];
const TTS = [['edge', 'Edge TTS (online, nhanh)'], ['piper', 'Piper (offline)'], ['kokoro', 'Kokoro (offline)'],
    ['vieneu', 'VieNeu (tiếng Việt)'], ['clone', 'Clone giọng gốc']];
/* Tên việc cho thông báo (mã `phu-de`… chỉ dùng trong API). */
export const TEN_VIEC = { 'phu-de': 'Tạo phụ đề', ocr: 'Nhận diện sub cứng (OCR)', dich: 'Dịch phụ đề', 'long-tieng': 'Lồng tiếng',
    'tach-giong': 'Tách giọng', 'lam-net': 'Làm nét video', 'can-gio': 'Tự căn giờ phụ đề', 'tao-anh': 'Tạo ảnh AI' };
/* Việc AI tự vào timeline khi xong. Làm nét thay media gốc (file lớn, đổi hình) nên vẫn để người dùng bấm Áp dụng. */
export const TU_AP_DUNG = new Set(['phu-de', 'ocr', 'dich', 'long-tieng', 'tach-giong', 'can-gio', 'tao-anh', 'doc-van-ban']);
const TT = { cho: 'Đang chờ lượt', dang_chay: 'Đang chạy', xong: 'Xong', loi: 'Lỗi', bi_ngat: 'Bị ngắt', da_huy: 'Đã huỷ' };

export function layModelWhisperMacDinh(ngonNgu) {
    return ngonNgu === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium';
}

export function moTaUpscale(kieu, rongGoc, caoGoc, dich) {
    let canhBao = '';
    if (dich && dich !== 'Gốc' && rongGoc && caoGoc) {
        let caoDich = parseInt(dich) || 0;
        if (caoDich > 0 && Math.min(rongGoc, caoGoc) >= caoDich) {   // cạnh ngắn — video dọc cũng đúng
            canhBao = '<div style="color:red; margin-bottom: 5px;">⚠️ Video đã đủ lớn, phóng to không có ích.</div>';
        }
    }
    let html = canhBao + '<b>Tác dụng:</b> tăng số điểm ảnh → hình to, rõ hơn khi xem trên màn lớn; ';
    if (kieu === 'ai') {
        html += 'AI (RealESRGAN anime) vẽ lại nét viền, khử nhiễu/khối nén — hợp video hoạt hình/truyện tranh độ phân giải thấp (≤ 480p).';
    } else if (kieu === 'ai_video') {
        html += 'AI vẽ lại nét viền, khử nhiễu/khối nén.';
    } else {
        html += 'co giãn thường chỉ phóng to, KHÔNG thêm chi tiết.';
    }
    html += '<br><b>Tác động:</b> ';
    if (kieu === 'ai' || kieu === 'ai_video') {
        html += 'thời gian (ước lượng: số khung = thời lượng × fps; AI ≈ 1–3 s/khung trên GPU 6 GB → khoảng vài phút đến hàng giờ); dùng GPU (chặn các việc AI khác trong hàng đợi); ';
    } else {
        html += 'nhanh; ';
    }
    html += 'file lớn hơn nhiều lần; độ phân giải media mới KHÁC khung dự án (preview/xuất sẽ co lại theo khung dự án — lợi ích chỉ thấy nếu khung dự án/xuất cũng lớn); ';
    if (kieu === 'ai') {
        html += 'model anime có thể làm da/mặt người thật bị bệt, mất chi tiết nhỏ (không hợp video quay thật); ';
    }
    html += 'không phục hồi được chi tiết đã mất hẳn (chữ quá mờ).';
    return html;
}


/* Nhãn sau tên model tạo ảnh: " ✓ có sẵn" nếu server báo đã có trong cache, " — cần tải" nếu chưa (chưa biết → không ghi gì). */
export function nhanModelAnh(models, repo) {
    const ds = models && models.anh_co_san;
    if (!Array.isArray(ds)) return '';
    return ds.includes(repo) ? ' ✓ có sẵn' : ' — cần tải';
}

export function tinhCoAnhMacDinh(rongGoc, caoGoc) {
    let r = rongGoc || 1024;
    let c = caoGoc || 1024;
    let maxKich = Math.max(r, c);
    if (maxKich > 1024) {
        let tiLe = 1024 / maxKich;
        r = r * tiLe;
        c = c * tiLe;
    }
    return {
        r: Math.max(8, Math.round(r / 8) * 8),
        c: Math.max(8, Math.round(c / 8) * 8)
    };
}

export function opsChenAnhAi(tl, trId, mediaId, dauPhat, thoiLuong = 3.0) {
    const start = choTrong(tl, trId, dauPhat, thoiLuong);
    return [tao.them(tl, ['clips'], {
        id: idClipMoi(tl), track: trId, media: mediaId, bat_dau: start,
        vao: 0, ra: thoiLuong
    })];
}

export class BangAi {
    constructor(ctx) {
        this.ctx = ctx;
        this.tacVu = [];
        this._dangAp = new Set();   // id việc đang tự áp dụng — tai() chạy lại mỗi 1,5 s, tránh áp hai lần
        this._h = null;
        this._models = { realesr_animevideov3: true };
        fetch('/api/ai/models').then(r => r.json()).then(d => { this._models = d; this.tai(); }).catch(() => {});
        this.el = document.createElement('div');
        this.el.style.cssText = 'display:flex;flex-direction:column;min-height:0;height:100%';
        this.el.innerHTML = `<div class="bang-dau"><h2>AI</h2></div><div class="bang-noi" data-khu="noi"></div>`;
        this.noi = this.el.querySelector('[data-khu=noi]');
        this.noi.addEventListener('click', (e) => this._bam(e));
        this.noi.addEventListener('change', (e) => this._doi(e));
        ctx.bus.on('media', () => { if (this.el.isConnected) this.ve(); });
        this.tai();
    }

    get tl() { return this.ctx.store.timeline; }
    get cai() {
        if (!this.ctx.ui.ai) this.ctx.ui.ai = {};
        return this.ctx.ui.ai;
    }

    /* Video nguồn mặc định: clip dưới đầu phát → media đó; không thì video đầu tiên trên timeline. */
    mediaNguon() {
        const trenTl = [...new Set(this.tl.clips.filter((c) => c.media).map((c) => c.media))]
            .map((id) => this.ctx.media.find((m) => m.id === id)).filter((m) => m && ['video', 'audio'].includes(m.loai));
        let mid = this.cai.media;
        if (!trenTl.some((m) => m.id === mid)) {
            const duoi = this.tl.tracks.filter((t) => t.loai === 'video').map((t) => clipTai(this.tl, t.id, this.ctx.ui.dau_phat)).find(Boolean);
            mid = (duoi && duoi.media) || (trenTl[0] && trenTl[0].id) || '';
        }
        return { mid, ds: trenTl };
    }

    // ------------------------------------------------------------ vẽ
    ve() {
        const { mid, ds } = this.mediaNguon();
        const m = ds.find(x => x.id === mid);
        const c = this.cai;
        const soCau = mid ? cauCuaMedia(this.tl, mid).length : 0;
        const coDich = mid && cauCuaMedia(this.tl, mid).some((x) => x.text_goc && x.text_goc !== x.text);
        const chonNN = (k, md) => NGON_NGU.map(([v, t]) => `<option value="${v}" ${(c[k] || md) === v ? 'selected' : ''}>${t}</option>`).join('');
        if (!ds.length) {
            this.noi.innerHTML = `<div class="vung-tha"><b>Chưa có video trên timeline</b>
                Kéo một video từ bảng 🎞 Tệp phương tiện xuống timeline rồi quay lại đây để tạo phụ đề, dịch, lồng tiếng.</div>${this._veTacVu()}`;
            return;
        }
        const v = c.vung;
        this.noi.innerHTML = `
            <label class="ai-nguon">Video nguồn
                <select data-o="media">${ds.map((m) => `<option value="${esc(m.id)}" ${m.id === mid ? 'selected' : ''}>${m.loai === 'video' ? '🎬' : '🎵'} ${esc(m.ten)}</option>`).join('')}</select>
                <span class="goi-y-nho">${soCau} câu phụ đề đang neo vào video này</span></label>

            <section class="the-ai"><h4>🎙 Tạo phụ đề từ lời nói <small>Whisper</small></h4>
                <label>Ngôn ngữ nói<select data-o="ngon_ngu_noi">${chonNN('ngon_ngu_noi', 'Chinese')}</select></label>
                <label>Model nhận giọng<select data-o="whisper_model">
                    <option value="base" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'base' ? 'selected' : ''}>base (nhanh)</option>
                    <option value="medium" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'medium' ? 'selected' : ''}>medium (chính xác hơn, chậm hơn)</option>
                    ${c.ngon_ngu_noi === 'Vietnamese' ? `<option value="qbsmlabs/PhoWhisper-small" ${(c.whisper_model || 'qbsmlabs/PhoWhisper-small') === 'qbsmlabs/PhoWhisper-small' ? 'selected' : ''}>PhoWhisper small (tiếng Việt)</option>` : ''}
                    <option value="large-v3" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'large-v3' ? 'selected' : ''}>large-v3 (tải ~3 GB lần đầu)</option>
                </select></label>
                <label class="check"><input type="checkbox" data-o="demucs" ${c.demucs ? 'checked' : ''}> Tách giọng trước (Demucs) — nhạc nền to thì bật</label>
                <button class="nut nut-chinh" data-l="phu-de">Tạo phụ đề</button></section>

            <section class="the-ai"><h4>🔤 Nhận diện sub cứng <small>OCR</small></h4>
                <label>Ngôn ngữ chữ trên hình<select data-o="ngon_ngu_chu">${chonNN('ngon_ngu_chu', 'Chinese')}</select></label>
                <div class="hang-nut"><button class="nut" data-l="ve-vung">▭ Kéo khung vùng phụ đề</button>
                    <span class="goi-y-nho">${v ? `vùng ${Math.round(v.w * 100)}×${Math.round(v.h * 100)}% ở ${Math.round(v.x * 100)},${Math.round(v.y * 100)}%` : 'chưa có vùng'}</span></div>
                <label class="check"><input type="checkbox" data-o="tao_che" ${c.tao_che !== false ? 'checked' : ''}> Tự tạo vùng che sub gốc đúng khung này</label>
                <button class="nut nut-chinh" data-l="ocr" ${v ? '' : 'disabled title="Kéo khung trước"'}>Nhận diện</button></section>

            <section class="the-ai"><h4>🌐 Dịch phụ đề</h4>
                <label>Dịch từ<select data-o="dich_tu">${chonNN('dich_tu', [...this.tacVu].reverse().find(x => ['phu-de', 'ocr'].includes(x.loai) && x.media === mid)?.tham_so?.source_lang || c.ngon_ngu_noi || 'English')}</select></label>
                <label>Dịch sang<select data-o="dich_sang">${chonNN('dich_sang', 'Vietnamese')}</select></label>
                <label class="check"><input type="checkbox" data-o="dich_lai_tat_ca"> Dịch lại tất cả (cả câu đã sửa tay)</label>
                <label class="check"><input type="checkbox" data-o="ngu_canh" ${c.ngu_canh ? 'checked' : ''}> Dùng câu trước làm ngữ cảnh (thử nghiệm)</label>
                <div class="hang-nut"><button class="nut nut-chinh" data-l="dich" ${soCau ? '' : 'disabled title="Chưa có câu phụ đề"'}>Dịch ${soCau} câu</button>
                <button class="nut" data-l="mo-thuat-ngu">📖 Thuật ngữ</button></div></section>

            <section class="the-ai"><h4>🗣 Lồng tiếng</h4>
                <label>Giọng đọc<select data-o="tts">${TTS.map(([k, t]) => {
                    const thieu = k === 'clone' && this._models.clone === false;   // máy thiếu torchcodec/coqui-tts
                    return `<option value="${k}" ${(c.tts || 'edge') === k ? 'selected' : ''}${thieu ? ' disabled' : ''}>${t}${thieu ? ' — thiếu gói torchcodec' : ''}</option>`;
                }).join('')}</select></label>
                <div id="aiChonGiong">${veDieuKhien(c.tts || 'edge', c.giong, 'cg', c.tts_speed || 1.0, c.tts_pitch || 0)}</div>
                <label>Giảm nhạc nền khi có lời <span class="gt">${c.giam ?? 90}%</span><input type="range" data-o="giam" min="0" max="100" value="${c.giam ?? 90}"></label>
                <button class="nut nut-chinh" data-l="long-tieng" ${soCau ? '' : 'disabled'}>Lồng tiếng ${coDich ? 'bản dịch' : ''}</button></section>
            
            <section class="the-ai"><h4>🎶 Tách giọng</h4>
                <div class="goi-y-nho" style="margin-bottom:10px">Demucs: xuất giọng nói và nhạc nền ra 2 track riêng (tốn GPU/thời gian).</div>
                <button class="nut nut-chinh" data-l="tach-giong">Tách giọng</button></section>
            
            <section class="the-ai"><h4>⏱ Tự căn giờ phụ đề</h4>
                <div class="goi-y-nho" style="margin-bottom:10px">Dùng Whisper khớp từng từ để lấy giờ. Sửa thẳng giờ của câu trên timeline.</div>
                <label>Model nhận giọng<select data-o="whisper_model">
                    <option value="base" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'base' ? 'selected' : ''}>base (nhanh)</option>
                    <option value="medium" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'medium' ? 'selected' : ''}>medium (chính xác hơn, chậm hơn)</option>
                    ${c.ngon_ngu_noi === 'Vietnamese' ? `<option value="qbsmlabs/PhoWhisper-small" ${(c.whisper_model || 'qbsmlabs/PhoWhisper-small') === 'qbsmlabs/PhoWhisper-small' ? 'selected' : ''}>PhoWhisper small (tiếng Việt)</option>` : ''}
                    <option value="large-v3" ${(c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium')) === 'large-v3' ? 'selected' : ''}>large-v3 (tải ~3 GB lần đầu)</option>
                </select></label>
                <button class="nut nut-chinh" data-l="can-gio" ${soCau ? '' : 'disabled'}>Căn giờ ${soCau} câu</button></section>

            <section class="the-ai"><h4>✨ Làm nét video</h4>
                <div class="goi-y-nho" style="margin-bottom:10px">Làm nét (FFmpeg CAS): giữ nguyên độ phân giải, chỉ tăng độ sắc nét cạnh.</div>
                <label class="check"><input type="checkbox" data-o="lam_net_phong_to" ${c.lam_net_phong_to ? 'checked' : ''}> Phóng to (upscale)</label>
                ${c.lam_net_phong_to ? `
                <div style="margin-left: 20px; padding-left: 10px; border-left: 2px solid #555;">
                    <label>Thuật toán<select data-o="lam_net_kieu">
                        <option value="nhanh" ${(!c.lam_net_kieu || c.lam_net_kieu === 'nhanh') ? 'selected' : ''}>Thường — co giãn FFmpeg</option>
                        <option value="ai" ${c.lam_net_kieu === 'ai' ? 'selected' : ''}>AI RealESRGAN anime</option>
                        <option value="ai_video" ${c.lam_net_kieu === 'ai_video' ? 'selected' : ''}${this._models.realesr_animevideov3 ? '' : ' hidden'}>AI video</option>
                    </select></label>
                    <label>Độ phân giải đích<select data-o="lam_net_dpg">
                        ${['720p (HD)', '1080p (Full HD)', '1440p (2K)', '2160p (4K)'].filter(dpg => {
                            const cd = parseInt(dpg);
                            return !(m && Math.min(m.rong || 0, m.cao || 0) >= cd);
                        }).map(dpg => `<option value="${dpg}" ${c.lam_net_dpg === dpg ? 'selected' : ''}>${dpg}</option>`).join('')}
                        <option value="Gốc" ${(!c.lam_net_dpg || c.lam_net_dpg === 'Gốc') ? 'selected' : ''}>Gốc</option>
                    </select></label>
                    <div class="goi-y-nho" style="margin-top: 5px">${moTaUpscale(c.lam_net_kieu || 'nhanh', m?.rong, m?.cao, c.lam_net_dpg || 'Gốc')}</div>
                </div>` : ''}
                <button class="nut nut-chinh" data-l="lam-net">Làm nét</button></section>
            
            <section class="the-ai"><h4>🎨 Tạo ảnh AI</h4>
                <div class="goi-y-nho" style="margin-bottom:10px">Model "✓ có sẵn" chạy ngay; model "cần tải" lần đầu sẽ tải ~4 GB (một lần).</div>
                <label>Mô hình<select data-o="anh_model">
                    <option value="stablediffusionapi/anything-v5" ${(!c.anh_model || c.anh_model === 'stablediffusionapi/anything-v5') ? 'selected' : ''}>Anything V5 (Anime)${nhanModelAnh(this._models, 'stablediffusionapi/anything-v5')}</option>
                    <option value="lykon/dreamshaper-8" ${c.anh_model === 'lykon/dreamshaper-8' ? 'selected' : ''}>DreamShaper 8 (Đa năng)${nhanModelAnh(this._models, 'lykon/dreamshaper-8')}</option>
                    <option value="nyz3/Realistic_Vision_V6.0_B1_VAE" ${c.anh_model === 'nyz3/Realistic_Vision_V6.0_B1_VAE' ? 'selected' : ''}>Realistic Vision 6 (Chân thực)${nhanModelAnh(this._models, 'nyz3/Realistic_Vision_V6.0_B1_VAE')}</option>
                    <option value="cyberdelia/CyberRealistic" ${c.anh_model === 'cyberdelia/CyberRealistic' ? 'selected' : ''}>CyberRealistic (Chân thực + Sáng)${nhanModelAnh(this._models, 'cyberdelia/CyberRealistic')}</option>
                    <option value="custom" ${c.anh_model === 'custom' ? 'selected' : ''}>Tùy chỉnh...</option>
                </select></label>
                ${c.anh_model === 'custom' ? `<label>Đường dẫn / Repo<input type="text" data-o="anh_model_custom" value="${esc(c.anh_model_custom || '')}" placeholder="VD: lykon/dreamshaper-8"></label>` : ''}
                <label>Prompt<textarea data-o="anh_prompt" rows="3" placeholder="Miêu tả ảnh muốn tạo...">${esc(c.anh_prompt || '')}</textarea></label>
                <label>Negative Prompt<textarea data-o="anh_negative" rows="2" placeholder="Những gì không muốn có...">${esc(c.anh_negative || 'worst quality, normal quality, low quality, low res, blurry, text, watermark, logo, banner, extra digits, cropped, jpeg artifacts, signature, username, error, sketch ,duplicate, ugly, monochrome, horror, geometry, mutation, disgusting')}</textarea></label>
                <div style="display:flex; gap:10px">
                    <label style="flex:1">Rộng (px)<input type="number" data-o="anh_rong" value="${c.anh_rong || tinhCoAnhMacDinh((this.ctx.du.thong_so || {}).rong, (this.ctx.du.thong_so || {}).cao).r}"></label>
                    <label style="flex:1">Cao (px)<input type="number" data-o="anh_cao" value="${c.anh_cao || tinhCoAnhMacDinh((this.ctx.du.thong_so || {}).rong, (this.ctx.du.thong_so || {}).cao).c}"></label>
                </div>
                <div style="display:flex; gap:10px">
                    <label style="flex:1">Số ảnh<input type="number" data-o="anh_so" value="${c.anh_so || 1}" min="1" max="4"></label>
                    <label style="flex:1">Steps<input type="number" data-o="anh_steps" value="${c.anh_steps || 20}"></label>
                </div>
                <div style="display:flex; gap:10px">
                    <label style="flex:1">Guidance<input type="number" data-o="anh_guidance" value="${c.anh_guidance || 7.0}" step="0.1"></label>
                    <label style="flex:1">Seed<input type="number" data-o="anh_seed" value="${c.anh_seed ?? -1}" placeholder="-1 = ngẫu nhiên"></label>
                </div>
                <button class="nut nut-chinh" data-l="tao-anh" ${!c.anh_prompt ? 'disabled' : ''}>Tạo ảnh</button></section>
            <section class="the-ai"><h4>🗣 Đọc văn bản</h4>
                <div class="goi-y-nho" style="margin-bottom:10px">Tạo clip giọng nói từ văn bản (không cần chọn video).</div>
                <label>Văn bản<textarea data-o="van_ban" rows="3" placeholder="Nhập văn bản cần đọc...">${esc(c.van_ban || '')}</textarea></label>
                <div class="hang-nut">
                    <button class="nut" data-l="lay-chu-clip">Lấy chữ từ clip đang chọn</button>
                </div>
                <label>Giọng đọc<select data-o="tts_van_ban">${TTS.map(([k, t]) => {
                    const thieu = k === 'clone' && this._models.clone === false;
                    return `<option value="${k}" ${(c.tts_van_ban || 'edge') === k ? 'selected' : ''}${thieu ? ' disabled' : ''}>${t}${thieu ? ' — thiếu gói torchcodec' : ''}</option>`;
                }).join('')}</select></label>
                <div id="aiChonGiongVanBan">${veDieuKhien(c.tts_van_ban || 'edge', c.giong_van_ban, 'cg_vb', c.tts_speed_vb || 1.0, c.tts_pitch_vb || 0)}</div>
                <button class="nut nut-chinh" data-l="doc-van-ban" ${!c.van_ban ? 'disabled' : ''}>Tạo giọng đọc</button></section>
            
            <section class="the-ai"><h4>🎞 Video minh hoạ</h4>
                <div id="aiThieuKeyMinhHoa" class="goi-y-nho" style="color:#d9534f; margin-bottom:10px; display:none;">Cần API key Pexels/Pixabay/Coverr (miễn phí) trong ⚙ Cấu hình</div>
                <div class="goi-y-nho" style="margin-bottom:10px">LLM rút từ khoá từ phụ đề & tìm tải video stock. Tự gộp câu ngắn ≥ 3s.</div>
                <label>Nguồn<select data-o="minh_hoa_nguon">
                    <option value="pexels" ${(c.minh_hoa_nguon === 'pexels') ? 'selected' : ''}>Pexels</option>
                    <option value="pixabay" ${(c.minh_hoa_nguon === 'pixabay') ? 'selected' : ''}>Pixabay</option>
                    <option value="coverr" ${(c.minh_hoa_nguon === 'coverr') ? 'selected' : ''}>Coverr</option>
                </select></label>
                <label>Tỉ lệ<select data-o="minh_hoa_ti_le">
                    <option value="9:16" ${(c.minh_hoa_ti_le === '9:16') ? 'selected' : ''}>Dọc (9:16)</option>
                    <option value="16:9" ${(c.minh_hoa_ti_le === '16:9') ? 'selected' : ''}>Ngang (16:9)</option>
                    <option value="1:1" ${(c.minh_hoa_ti_le === '1:1') ? 'selected' : ''}>Vuông (1:1)</option>
                </select></label>
                <label>Hành động<select data-o="minh_hoa_hanh_dong">
                    <option value="track" ${(c.minh_hoa_hanh_dong === 'track' || !c.minh_hoa_hanh_dong) ? 'selected' : ''}>Đặt lên track trên</option>
                    <option value="kho" ${(c.minh_hoa_hanh_dong === 'kho') ? 'selected' : ''}>Chỉ tải vào kho</option>
                </select></label>
                <button class="nut nut-chinh" data-l="minh-hoa" ${!coDich && !soCau ? 'disabled' : ''}>Tìm & Tải B-roll</button></section>
            
            <label class="check" style="margin:8px 0" title="Phụ đề, OCR, dịch, lồng tiếng, tách giọng, đọc văn bản, minh hoạ: xong là vào timeline ngay (Ctrl+Z để bỏ). Làm nét luôn hỏi trước.">
                <input type="checkbox" data-o="tu_ap_dung" ${(c.tu_ap_dung ?? true) ? 'checked' : ''}> Tự đưa kết quả AI vào timeline khi xong</label>
            ${this._veTacVu()}`;
            
        api('/api/config').then(cfg => {
            const keys = cfg.api_keys || {};
            if (!keys.pexels && !keys.pixabay && !keys.coverr) {
                const warn = this.noi.querySelector('#aiThieuKeyMinhHoa');
                if (warn) warn.style.display = 'block';
            }
        }).catch(() => {});
        
        const aiChonGiong = this.noi.querySelector('#aiChonGiong');
        if (aiChonGiong) {
            const eng = c.tts || 'edge';
            const curVal = c[`giong_${eng}`] || c.giong;
            bindDieuKhien(aiChonGiong, eng, c.dich_sang || 'Vietnamese', curVal, (val) => {
                c.giong = val;
                c[`giong_${eng}`] = val;
                this.ctx.luuUi();
            }, (speed) => {
                c.tts_speed = speed;
                this.ctx.luuUi();
            }, (pitch) => {
                c.tts_pitch = pitch;
                this.ctx.luuUi();
            });
        }
        
        const aiChonGiongVanBan = this.noi.querySelector('#aiChonGiongVanBan');
        if (aiChonGiongVanBan) {
            const eng = c.tts_van_ban || 'edge';
            const curVal = c[`giong_van_ban_${eng}`] || c.giong_van_ban;
            bindDieuKhien(aiChonGiongVanBan, eng, 'Vietnamese', curVal, (val) => {
                c.giong_van_ban = val;
                c[`giong_van_ban_${eng}`] = val;
                this.ctx.luuUi();
            }, (speed) => {
                c.tts_speed_vb = speed;
                this.ctx.luuUi();
            }, (pitch) => {
                c.tts_pitch_vb = pitch;
                this.ctx.luuUi();
            });
        }
    }

    _veTacVu() {
        if (!this.tacVu.length) return '';
        return `<h4 class="tv-tieu-de">Tác vụ</h4>` + this.tacVu.map((v) => {
            const dang = ['cho', 'dang_chay'].includes(v.trang_thai);
            const kq = v.ket_qua || {};
            let moTaKq = v.trang_thai === 'xong' ? (kq.so_cau != null ? `${kq.so_cau} câu` : kq.file ? kq.file : '') : '';
            if (v.loai === 'dich' && kq.bao_cao && v.trang_thai === 'xong') {
                moTaKq += ` (lọt ${Math.round((kq.bao_cao.ti_le_lot_cuoi || 0) * 100)}%, sửa ${kq.bao_cao.so_cau_sua} câu)`;
            }
            // Dịch bị huỷ giữa chừng vẫn giữ các câu đã dịch: áp dụng phần đó rồi dịch tiếp phần còn lại.
            const dangDo = v.loai === 'dich' && v.trang_thai === 'da_huy' && kq.dang_do && (kq.cau || []).length;
            if (dangDo) moTaKq = `${kq.cau.length}/${kq.tong_cau} câu đã dịch trước khi huỷ`;
            return `<div class="the-tv ${v.trang_thai}" data-id="${esc(v.id)}">
                <div class="tv-dau"><b>${esc(v.nhan || v.loai)}</b><span class="tv-tt">${TT[v.trang_thai] || v.trang_thai}${v.vi_tri && v.trang_thai === 'cho' ? ` (thứ ${v.vi_tri})` : ''}</span></div>
                ${dang ? `<div class="thanh-tien-do" style="width:100%"><i style="width:${v.tien_do || 0}%"></i></div>` : ''}
                ${v.thong_diep && dang ? `<div class="tv-tin">${esc(v.thong_diep)}</div>` : ''}
                ${v.loi ? `<div class="tv-loi">${esc(v.loi)}</div>` : ''}
                ${v.loai === 'dich' && kq.bao_cao && kq.bao_cao.loi_lot && kq.bao_cao.loi_lot.length ? 
                    `<div class="tv-loi-lot" style="margin-top:5px; font-size:12px">${kq.bao_cao.loi_lot.map((c) => `<div data-l="nhay-cau-lot" data-cid="${esc(c.id)}" style="color:var(--do); cursor:pointer" title="${esc(c.nguon)} -> ${esc(c.ban_dich)}">[Lọt: ${esc((c.lot || []).join(', '))}] Câu bị lọt/thiếu thuật ngữ</div>`).join('')}</div>`
                : ''}
                ${v.loai === 'tao-anh' && kq.media_moi && kq.media_moi.length ? 
                    `<div class="tv-tin" style="display:flex;gap:5px;margin-top:5px;flex-wrap:wrap">` + 
                    kq.media_moi.map(mid => `<img src="/api/du-an/${encodeURIComponent(this.ctx.id)}/media/${esc(mid)}/thumb" style="height:60px;object-fit:cover;border-radius:4px" />`).join('') + 
                    `</div>`
                : ''}
                ${moTaKq ? `<div class="tv-tin">Kết quả: ${esc(moTaKq)}${kq.lech_so_cau ? ' — số câu dịch khác bản gốc' : ''}</div>` : ''}
                <div class="the-tai-nut">
                    ${dang ? '<button class="nut nut-nho" data-l="huy-tv">Huỷ</button>' : ''}
                    ${v.loai === 'xuat' && v.trang_thai === 'xong' ? '<button class="nut nut-nho" data-l="mo-xuat">📂 Mở thư mục</button>' : ''}
                    ${v.loai !== 'xuat' && v.trang_thai === 'xong' && !v.da_ap_dung ? '<button class="nut nut-chinh nut-nho" data-l="ap-dung">Áp dụng</button>' : ''}
                    ${v.loai !== 'xuat' && v.trang_thai === 'xong' && v.da_ap_dung ? '<span class="goi-y-nho">đã áp dụng</span>' : ''}
                    ${dangDo && !v.da_ap_dung ? `<button class="nut nut-chinh nut-nho" data-l="ap-dung">Áp dụng ${kq.cau.length} câu đã dịch</button>` : ''}
                    ${dangDo && v.da_ap_dung ? '<button class="nut nut-chinh nut-nho" data-l="dich-tiep">↻ Dịch tiếp phần còn lại</button>' : ''}
                    ${v.loai !== 'xuat' && ['loi', 'bi_ngat', 'da_huy'].includes(v.trang_thai) && !(dangDo && v.da_ap_dung) ? '<button class="nut nut-nho" data-l="chay-lai">↻ Chạy lại</button>' : ''}
                    ${!dang ? '<button class="nut nut-nho" data-l="an-tv">Ẩn</button>' : ''}
                </div></div>`;
        }).join('');
    }

    // ------------------------------------------------------------ sự kiện
    _doi(e) {
        const o = e.target.closest('[data-o]');
        if (!o) return;
        const k = o.dataset.o;
        this.cai[k === 'media' ? 'media' : k] = o.type === 'checkbox' ? o.checked : o.type === 'range' ? Number(o.value) : o.value;
        this.ctx.luuUi();
        // Thẻ Làm nét: bật/tắt Phóng to và đổi kiểu/độ phân giải phải vẽ lại khối giải thích tác dụng/tác động.
        // `change` của select/checkbox chỉ bắn khi đã chọn xong nên vẽ lại không cắt ngang thao tác.
        if (k === 'media' || k.startsWith('lam_net_') || k === 'anh_model' || k === 'anh_prompt' || k === 'ngon_ngu_noi') this.ve();
        if (k === 'tts' || k === 'dich_sang') {
            const aiChonGiong = this.noi.querySelector('#aiChonGiong');
            if (aiChonGiong) {
                const eng = this.cai.tts || 'edge';
                const lang = this.cai.dich_sang || 'Vietnamese';
                const curVal = this.cai[`giong_${eng}`] || this.cai.giong || '';
                aiChonGiong.innerHTML = veDieuKhien(eng, curVal, 'cg', this.cai.tts_speed || 1.0, this.cai.tts_pitch || 0);
                bindDieuKhien(aiChonGiong, eng, lang, curVal, (val) => {
                    this.cai.giong = val;
                    this.cai[`giong_${eng}`] = val;
                    this.ctx.luuUi();
                }, (speed) => {
                    this.cai.tts_speed = speed;
                    this.ctx.luuUi();
                }, (pitch) => {
                    this.cai.tts_pitch = pitch;
                    this.ctx.luuUi();
                });
            }
        }
        if (o.type === 'range') o.closest('label').querySelector('.gt').textContent = `${o.value}%`;
    }

    async _bam(e) {
        const b = e.target.closest('[data-l]');
        if (!b) return;
        const l = b.dataset.l;
        const the = b.closest('.the-tv');
        const v = the && this.tacVu.find((x) => x.id === the.dataset.id);
        try {
            if (l === 've-vung') await this.veVung();
            else if (['phu-de', 'ocr', 'dich', 'long-tieng', 'tach-giong', 'lam-net', 'can-gio', 'tao-anh', 'doc-van-ban'].includes(l)) await this.chay(l);
            else if (l === 'lay-chu-clip') {
                const cIds = this.ctx.ui.chon || [];
                const clipChon = cIds.map(id => this.tl.clips.find(x => x.id === id)).filter(Boolean);
                const chuChon = clipChon.find(x => x.loai === 'chu' || (x.track && this.tl.tracks.find(t => t.id === x.track && t.loai === 'chu')));
                if (chuChon && chuChon.text) {
                    this.cai.van_ban = chuChon.text;
                    this.cai._nguon_doc_van_ban = chuChon.id;
                    this.ctx.luuUi();
                    this.ve();
                } else {
                    toast('Hãy chọn một clip CHỮ trên timeline trước.', 'info');
                }
            }
            else if (l === 'huy-tv' && v) await api(`/api/hang-doi/${v.id}/huy`, { method: 'POST' });
            else if (l === 'an-tv' && v) await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/tac-vu/${v.id}/an`, { method: 'POST', body: { phien: this.ctx.boLuu.phien } });
            else if (l === 'chay-lai' && v) await this.chay(v.loai, v.media, v.tham_so || {});
            // Câu đã áp dụng có text ≠ text_goc → dich_lai_tat_ca=false để server bỏ qua, chỉ dịch câu chưa dịch.
            else if (l === 'dich-tiep' && v) await this.chay('dich', v.media, { ...(v.tham_so || {}), dich_lai_tat_ca: false });
            else if (l === 'ap-dung' && v) await this.apDung(v);
            else if (l === 'mo-xuat') await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/mo-thu-muc-con?ten=xuat`, { method: 'POST' });
                                    else if (l === 'mo-thuat-ngu') {
                let data = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/thuat-ngu`);
                let hienTai = data.text;
                while (true) {
                    const moi = await hoi({
                        tieuDe: 'Thuật ngữ (nguồn = đích)',
                        o: { nhieuDong: 10, giaTri: hienTai, goiY: 'ví dụ:\nLâm Phàm = Lâm Phàm\n筑基期 = Trúc Cơ kỳ' },
                        nut: 'Lưu',
                        noiDung: 'Mỗi dòng một thuật ngữ, phân cách bằng dấu =.',
                        themNut: '<button class="nut" data-kq="nhap">Nhập từ truyện…</button>'
                    });
                    
                    if (moi === null) break;
                    
                    if (moi === 'nhap') {
                        const nguonData = await api('/api/thuat-ngu/nguon');
                        if (!nguonData.nguon || !nguonData.nguon.length) {
                            toast('Không tìm thấy nguồn thuật ngữ nào.', 'info');
                            continue;
                        }
                        window.__tn_ids = [];
                        const html = '<div id="tn_nguon_list" style="max-height:300px;overflow-y:auto;text-align:left;margin-bottom:10px;border:1px solid #ccc;padding:10px">' + 
                            nguonData.nguon.map(n => `<label style="display:block;margin-bottom:5px;cursor:pointer"><input type="checkbox" onchange="window.__tn_ids = Array.from(document.querySelectorAll('#tn_nguon_list input:checked')).map(x=>x.value)" value="${esc(n.id)}"> ${esc(n.ten)} (${n.so_muc} mục)</label>`).join('') +
                            '</div>';
                        const chon = await hoi({
                            tieuDe: 'Chọn nguồn thuật ngữ',
                            html: html,
                            nut: 'Nhập',
                            noiDung: 'Các thuật ngữ mới sẽ được gộp vào bảng hiện tại (không ghi đè).'
                        });
                        if (chon === true) {
                            const ids = window.__tn_ids || [];
                            if (ids.length) {
                                let count = 0;
                                let parsedHienTai = {};
                                hienTai.split('\n').forEach(line => {
                                    if(line.includes('=')) {
                                        let [k,...v] = line.split('=');
                                        parsedHienTai[k.trim()] = v.join('=').trim();
                                    }
                                });
                                for (let nid of ids) {
                                    let source = nguonData.nguon.find(x => x.id === nid);
                                    if (source && source.data) {
                                        for (let k in source.data) {
                                            if (!(k in parsedHienTai)) {
                                                parsedHienTai[k] = source.data[k];
                                                count++;
                                            }
                                        }
                                    }
                                }
                                hienTai = Object.entries(parsedHienTai).map(([k,v]) => k + ' = ' + v).join('\n');
                                toast(`Đã thêm ${count} thuật ngữ mới.`, 'success');
                            }
                        }
                        continue;
                    }
                    
                    let lines = typeof moi === 'string' ? moi.split('\n') : [];
                    let valid = true;
                    for (let i = 0; i < lines.length; i++) {
                        let line = lines[i].trim();
                        if (!line) continue;
                        if (!line.includes('=')) {
                            toast(`Lỗi dòng ${i+1}: Thiếu dấu '=' (dòng: "${line}")`, 'error', 5000);
                            valid = false;
                            break;
                        }
                        let parts = line.split('=');
                        if (!parts[0].trim() || !parts[1].trim()) {
                            toast(`Lỗi dòng ${i+1}: Trống nguồn hoặc đích (dòng: "${line}")`, 'error', 5000);
                            valid = false;
                            break;
                        }
                    }
                    if (!valid) {
                        hienTai = moi;
                        continue;
                    }
                    
                    await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/thuat-ngu`, { method: 'PUT', body: { text: moi } });
                    toast('Đã lưu bảng thuật ngữ riêng cho dự án.', 'success');
                    break;
                }
            }
            else if (l === 'nhay-cau-lot') {
                const cid = b.dataset.cid;
                const clip = this.tl.clips.find(c => c.id === cid);
                if (clip) {
                    this.ctx.timeline.datDauPhat(clip.bat_dau);
                    this.ctx.moBang('phu_de');
                }
            }
            this.tai();
        } catch (err) { toast(err.message, 'error'); }
    }

    async veVung() {
        const { mid } = this.mediaNguon();
        const tr = this.tl.tracks.find((t) => t.loai === 'video');
        const c = mid && this.tl.clips.find((x) => x.media === mid && tr && x.track === tr.id);
        if (c && !(this.ctx.ui.dau_phat >= c.bat_dau && this.ctx.ui.dau_phat < c.bat_dau + (c.ra - c.vao) / (c.toc_do || 1))) {
            this.ctx.timeline.datDauPhat(c.bat_dau + 0.5);        // đưa khung hình của video nguồn lên xem trước
            await new Promise((r) => setTimeout(r, 350));
        }
        toast('Kéo chuột quanh dòng phụ đề cứng trên khung xem trước.', 'info', 3500);
        const vung = await this.ctx.preview.veVung(undefined, mid);
        if (!vung) return;
        this.cai.vung = vung;
        this.ctx.luuUi(true);
        this.ve();
    }

    /* Gửi tác vụ lên hàng đợi GPU. `thamSoCu` = chạy lại tác vụ cũ với đúng tham số đó. */
    async chay(loai, midCu = '', thamSoCu = null) {
        const c = this.cai;
        const mid = midCu || this.mediaNguon().mid;
        const m = this.ctx.media.find((x) => x.id === mid);
        if (loai !== 'tao-anh' && !m) throw new Error('Chọn video nguồn trước.');
        let ts = thamSoCu ? { ...thamSoCu } : {};
        if (!thamSoCu) {
            if (loai === 'phu-de') ts = { source_lang: c.ngon_ngu_noi || 'Chinese', clean_audio: !!c.demucs, whisper_model: c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium') };
            if (loai === 'ocr') {
                if (!c.vung || !m.rong) throw new Error('Kéo khung vùng phụ đề trước.');
                ts = { source_lang: c.ngon_ngu_chu || 'Chinese', vung: c.vung, tao_che: c.tao_che !== false,
                    vung_px: { x: Math.round(c.vung.x * m.rong), y: Math.round(c.vung.y * m.cao),
                        w: Math.round(c.vung.w * m.rong), h: Math.round(c.vung.h * m.cao) } };
            }
            if (loai === 'dich') {
                const src = c.dich_tu || [...this.tacVu].reverse().find(x => ['phu-de', 'ocr'].includes(x.loai) && x.media === mid)?.tham_so?.source_lang || c.ngon_ngu_noi || 'English';
                const tgt = c.dich_sang || 'Vietnamese';
                if (src === tgt) throw new Error('Ngôn ngữ nguồn và đích giống nhau — không cần dịch.');
                ts = { source_lang: src, target_lang: tgt, dich_lai_tat_ca: !!c.dich_lai_tat_ca, ngu_canh: !!c.ngu_canh };
            }
            if (loai === 'long-tieng') ts = { tts_engine: c.tts || 'edge', tts_voice: c.giong || '', tts_speed: c.tts_speed, tts_pitch: c.tts_pitch, ducking_ratio: c.giam ?? 90,
                auto_clone: (c.tts || '') === 'clone', target_lang: c.dich_sang || 'Vietnamese' };
            if (loai === 'lam-net') {
                const phongTo = !!c.lam_net_phong_to;
                const kieu = phongTo ? (c.lam_net_kieu || 'nhanh') : 'nhanh';
                if (phongTo && (kieu === 'ai' || kieu === 'ai_video')) {
                    const frames = Math.round(Number(m.thoi_luong || 0) * Number(m.fps || 30));
                    const phutMin = Math.round((frames * 1) / 60) || 1;
                    const phutMax = Math.round((frames * 3) / 60) || 2;
                    const msg = `Làm nét AI sẽ tốn khoảng ${phutMin}–${phutMax} phút. Tiếp tục?`;
                    if (!(await hoi({ tieuDe: 'Xác nhận phóng to AI', nut: 'Tiếp tục', noiDung: msg }))) return;
                }
                if (phongTo && c.lam_net_dpg && c.lam_net_dpg !== 'Gốc') {
                    const cd = parseInt(c.lam_net_dpg);
                    if (cd > 0 && Math.min(m.rong || 0, m.cao || 0) >= cd) {
                        if (!(await hoi({ tieuDe: 'Xác nhận', nut: 'Vẫn chạy', noiDung: 'Video đã đủ lớn, phóng to không có ích. Vẫn chạy?' }))) return;
                    }
                }
                ts = { kieu: kieu, do_phan_giai: phongTo ? (c.lam_net_dpg || 'Gốc') : 'Gốc', phong_to: phongTo };
            }
            if (loai === 'tao-anh') {
                const mdl = c.anh_model === 'custom' ? (c.anh_model_custom || '') : (c.anh_model || 'stablediffusionapi/anything-v5');
                const co = tinhCoAnhMacDinh((this.ctx.du.thong_so || {}).rong, (this.ctx.du.thong_so || {}).cao);
                ts = {
                    anh_model: mdl,
                    anh_prompt: c.anh_prompt || '',
                    anh_negative: c.anh_negative || '',
                    anh_rong: c.anh_rong || co.r,
                    anh_cao: c.anh_cao || co.c,
                    anh_so: c.anh_so || 1,
                    anh_steps: c.anh_steps || 20,
                    anh_guidance: c.anh_guidance || 7.0,
                    anh_seed: c.anh_seed ?? -1
                };
            }
            if (loai === 'doc-van-ban') {
                ts = {
                    van_ban: c.van_ban,
                    tts_engine: c.tts_van_ban || 'edge',
                    tts_voice: c.giong_van_ban || '', tts_speed: c.tts_speed_vb, tts_pitch: c.tts_pitch_vb,
                    nguon_doc_van_ban: c._nguon_doc_van_ban
                };
            }
        }
        if (loai === 'dich' || loai === 'long-tieng' || loai === 'can-gio') {
            // Câu gửi đi là trạng thái timeline HIỆN TẠI (chạy lại cũng lấy bản mới nhất).
            const cau = cauCuaMedia(this.tl, mid).filter((x) => (x.text || '').trim());
            if (!cau.length) throw new Error('Video này chưa có câu phụ đề.');
            ts.cau = cau.map((x) => ({ t_vao: x.t_vao, t_ra: x.t_ra, text: x.text, text_goc: x.text_goc, id: x.id }));
            ts.ids = cau.map((x) => x.id);
            if (loai === 'can-gio') {
                ts.whisper_model = c.whisper_model || (c.ngon_ngu_noi === 'Vietnamese' ? 'qbsmlabs/PhoWhisper-small' : 'medium');
            }
        }
        await this.ctx.boLuu.flush();
        await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/ai/${loai}`,
            { method: 'POST', body: { phien: this.ctx.boLuu.phien, media: mid, tham_so: ts } });
        toast(`Đã xếp "${TEN_VIEC[loai] || loai}" vào hàng đợi — ${(c.tu_ap_dung ?? true) && TU_AP_DUNG.has(loai)
            ? 'xong sẽ tự đưa vào timeline' : 'tiến độ ở cuối bảng AI'}.`, 'info', 3000);
    }

    // ------------------------------------------------------------ áp kết quả
    async apDung(v, tuDong = false) {
        const kq = v.ket_qua || {};
        const tl = this.tl;
        const mid = v.media;
        let ops = [];
        let ten = '';
        const trPd = tl.tracks.find((t) => t.loai === 'phu_de');
        if (v.loai === 'phu-de' || v.loai === 'ocr' || (v.loai === 'dich' && kq.lech_so_cau)) {
            const cu = cauCuaMedia(tl, mid);
            if (cu.length && !tuDong && !(await hoi({ tieuDe: `Thay ${cu.length} câu phụ đề cũ của video này?`, nut: 'Thay',
                noiDung: 'Bộ phụ đề mới sẽ thay bộ cũ (Ctrl+Z để lấy lại).' }))) return;
            ops = opsXoaNhieu(tl, cu.map((x) => x.id));
            const nhap = JSON.parse(JSON.stringify(tl));
            ops.forEach((op) => nhap.clips.splice(op.vi_tri, 1));
            const cauMoi = kq.cau.map((x) => ({ ...x, text_goc: v.loai === 'dich' ? '' : x.text }));
            ops = ops.concat(opsThemCau(nhap, trPd.id, mid, cauMoi));
            ten = `${v.loai === 'ocr' ? 'OCR' : v.loai === 'dich' ? 'Dịch' : 'Whisper'}: ${kq.cau.length} câu`
                + (cu.length ? ` (thay ${cu.length} câu cũ)` : '');
            if (v.loai === 'ocr' && (v.tham_so || {}).tao_che !== false && kq.vung) {
                nhap.clips.push(...ops.filter((o) => o.op === 'them').map((o) => o.gia_tri));
                const m = this.ctx.media.find((x) => x.id === mid) || {};
                const trO = tl.tracks.find((t) => t.loai === 'lop_phu');
                if (trO) {
                    ops.push(tao.them(nhap, ['clips'], { id: idClipMoi(nhap), track: trO.id, loai: 'che_phu_de', tu_media: mid,
                        t_vao: 0, t_ra: Number(m.thoi_luong) || kq.cau[kq.cau.length - 1].t_ra, vung: kq.vung,
                        kieu: 'blur', do_manh: 20, mau: '#000000' }));
                    ten += ' + vùng che';
                }
            }
        } else if (v.loai === 'dich') {
            const theoId = new Map(kq.ids.map((id, i) => [id, kq.cau[i]]));
            for (const [id, x] of theoId) {
                const c = tl.clips.find((y) => y.id === id);
                if (!c || !x) continue;
                if (!c.text_goc) ops.push(tao.dat(tl, ['clips', { id }, 'text_goc'], c.text));
                ops.push(tao.dat(tl, ['clips', { id }, 'text'], x.text));
            }
            ten = `Dịch ${theoId.size} câu`;
        } else if (v.loai === 'can-gio') {
            const theoId = new Map((kq.cau || []).map((x) => [x.id, x]));
            for (const [id, x] of theoId) {
                const c = tl.clips.find((y) => y.id === id);
                if (!c || !x) continue;
                if (c.t_vao !== x.t_vao) ops.push(tao.dat(tl, ['clips', { id }, 't_vao'], x.t_vao));
                if (c.t_ra !== x.t_ra) ops.push(tao.dat(tl, ['clips', { id }, 't_ra'], x.t_ra));
            }
            ten = `Căn giờ ${theoId.size} câu`;
            if (kq.khong_khop) ten += ` (${kq.khong_khop} câu không khớp)`;
        } else if (v.loai === 'long-tieng') {
            ops = this._opsLongTieng(kq.media_moi, mid);
            ten = 'Lồng tiếng → A2';
        } else if (v.loai === 'tach-giong') {
            ops = this._opsTachGiong(kq.media_giong, kq.media_nhac, mid);
            ten = 'Tách giọng → A2/A3';
        } else if (v.loai === 'lam-net') {
            if (!(await hoi({ tieuDe: `Thay media sang bản nét?`, nut: 'Thay', noiDung: 'Các clip đang dùng video gốc sẽ chuyển sang bản nét.' }))) return;
            const cu = tl.clips.filter(c => c.media === mid);
            for (const c of cu) {
                ops.push(tao.dat(tl, ['clips', { id: c.id }, 'media'], kq.media_moi));
            }
            ten = 'Đổi media nét';
        } else if (v.loai === 'tao-anh') {
            const mediaIds = kq.media_moi || [];
            if (!mediaIds.length) throw new Error('Không tạo được ảnh nào.');
            this.ctx.bus.emit('media_can_tai');
            
            const vTracks = tl.tracks.filter(t => t.loai === 'video');
            if (vTracks.length) {
                const tr = vTracks[0];
                const vao = this.ctx.ui.dau_phat || 0;
                ops.push(...opsChenAnhAi(tl, tr.id, mediaIds[0], vao, 3.0));
                ten = `Chèn ảnh AI đầu tiên (${mediaIds.length} ảnh tạo ra)`;
            }
        } else if (v.loai === 'doc-van-ban') {
            const mediaId = kq.media_moi;
            if (!mediaId) throw new Error('Không tạo được giọng đọc.');
            this.ctx.bus.emit('media_can_tai');
            
            const m = this.ctx.media.find(x => x.id === mediaId);
            const dai = m ? Number(m.thoi_luong) || 0 : 0;
            
            let aTr = tl.tracks.find(t => t.loai === 'audio' && t.vai !== 'nhac' && t.vai !== 'long_tieng' && t.vai !== 'giong');
            if (!aTr) {
                aTr = tl.tracks.find(t => t.loai === 'audio');
            }
            if (!aTr) {
                aTr = { id: idTrackMoi(tl, 'A'), loai: 'audio', ten: 'Âm thanh', an: false, khoa: false, tat_tieng: false };
                ops.push(tao.them(tl, ['tracks'], aTr));
            }
            
            let vao = this.ctx.ui.dau_phat || 0;
            const ts = v.tham_so || {};
            if (ts.nguon_doc_van_ban) {
                const chuClip = tl.clips.find(c => c.id === ts.nguon_doc_van_ban);
                if (chuClip) vao = chuClip.bat_dau;
            }
            
            const batDau = choTrong(tl, aTr.id, vao, dai || 1.0);
            
            ops.push(tao.them(tl, ['clips'], {
                id: idClipMoi(tl), track: aTr.id, media: mediaId, bat_dau: batDau, vao: 0, ra: dai || 1.0, am_luong: 1
            }));
            ten = 'Chèn giọng đọc văn bản';
        } else if (v.loai === 'minh-hoa') {
            const hanhDong = v.tham_so?.minh_hoa_hanh_dong || 'track';
            if (hanhDong === 'kho') {
                ten = 'Tải B-roll vào kho';
                this.ctx.bus.emit('media_can_tai');
            } else {
                const rsTr = opsThemTrack(tl, 'video');
                const vTrId = rsTr.id;
                ops.push(...rsTr.ops);
                
                const doan = kq.doan || [];
                const ids = idMoiNhieu(tl, doan.length);
                let them = 0;
                
                const clipsNguon = clipChuaMedia(tl, mid);
                for (let i = 0; i < doan.length; i++) {
                    const d = doan[i];
                    let found = false;
                    for (const c of clipsNguon) {
                        if (d.t_vao >= c.vao && d.t_vao < c.ra) {
                            const offset = (d.t_vao - c.vao) / (c.toc_do || 1);
                            const batDau = c.bat_dau + offset;
                            const thoiGianRaClip = (c.ra - c.vao) / (c.toc_do || 1);
                            const thoiGianRaVideo = (d.t_ra - d.t_vao) / (c.toc_do || 1);
                            const ra = batDau + thoiGianRaVideo > c.bat_dau + thoiGianRaClip ? (c.bat_dau + thoiGianRaClip - batDau) : thoiGianRaVideo;
                            
                            ops.push(tao.them(tl, ['clips'], {
                                id: ids[i], track: vTrId, media: d.media,
                                bat_dau: batDau, vao: 0, ra: Math.min(ra, (this.ctx.media.find(m => m.id === d.media)?.thoi_luong || ra)),
                                am_luong: 0
                            }));
                            them++;
                            found = true;
                            break;
                        }
                    }
                    if (!found && clipsNguon.length) {
                        const c = clipsNguon[0];
                        const offset = (d.t_vao - c.vao) / (c.toc_do || 1);
                        ops.push(tao.them(tl, ['clips'], {
                            id: ids[i], track: vTrId, media: d.media,
                            bat_dau: c.bat_dau + offset, vao: 0, ra: (d.t_ra - d.t_vao) / (c.toc_do || 1),
                            am_luong: 0
                        }));
                        them++;
                    }
                }
                ten = `Minh hoạ: đặt ${them} clip lên track mới`;
                this.ctx.bus.emit('media_can_tai');
            }
        }
        if (!ops.length && v.loai !== 'minh-hoa') { toast('Không có gì để áp dụng.', 'info'); return; }
        if (!this.ctx.sua(ten, ops)) return;
        await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/tac-vu/${v.id}/ap-dung`, { method: 'POST', body: { phien: this.ctx.boLuu.phien } });
        v.da_ap_dung = true;
        toast(tuDong ? `✔ ${v.nhan} xong — đã đưa vào timeline: ${ten}. Ctrl+Z để bỏ.` : `Đã áp dụng: ${ten}.`, 'success', tuDong ? 8000 : 3000);
        if (['phu-de', 'ocr', 'dich'].includes(v.loai)) this.ctx.moBang('phu_de');
    }

    /* Track A2 "Lồng tiếng": mỗi clip của video nguồn có một clip giọng khớp đúng đoạn đó. */
    _opsLongTieng(midGiong, midNguon) {
        const tl = this.tl;
        const nhap = JSON.parse(JSON.stringify(tl));
        const ops = [];
        let tr = tl.tracks.find((t) => t.vai === 'long_tieng');
        if (!tr) {
            tr = { id: 'A2', loai: 'audio', ten: 'A2', vai: 'long_tieng', an: false, khoa: false, tat_tieng: false };
            ops.push(tao.them(nhap, ['tracks'], tr));
            nhap.tracks.push(tr);
        }
        // Bỏ giọng lồng cũ của cùng video (chạy lồng tiếng lần 2).
        const cu = nhap.clips.filter((c) => c.track === tr.id && c.long_tieng_cho === midNguon).map((c) => c.id);
        for (const op of opsXoaNhieu(nhap, cu)) { ops.push(op); nhap.clips.splice(op.vi_tri, 1); }
        const giong = this.ctx.media.find((m) => m.id === midGiong) || {};
        const dai = Number(giong.thoi_luong) || Infinity;
        const nguon = clipChuaMedia(nhap, midNguon).filter((c) => nhap.tracks.find((t) => t.id === c.track && t.loai === 'video'));
        const ids = idMoiNhieu(nhap, nguon.length);
        nguon.forEach((c, i) => {
            if (Number(c.vao) >= dai) return;
            ops.push(tao.them(nhap, ['clips'], { id: ids[i], track: tr.id, media: midGiong, long_tieng_cho: midNguon,
                bat_dau: c.bat_dau, vao: c.vao, ra: Math.min(Number(c.ra), dai), toc_do: c.toc_do || 1, am_luong: 1 }));
            nhap.clips.push({ id: ids[i] });
        });
        return ops;
    }

    _opsTachGiong(midGiong, midNhac, midNguon) {
        const tl = this.tl;
        const nhap = JSON.parse(JSON.stringify(tl));
        const ops = [];
        
        let trGiong = nhap.tracks.find((t) => t.vai === 'giong');
        if (!trGiong) {
            trGiong = { id: idTrackMoi(nhap, 'A'), loai: 'audio', ten: 'Giọng (Demucs)', vai: 'giong', an: false, khoa: false, tat_tieng: false };
            ops.push(tao.them(nhap, ['tracks'], trGiong));
            nhap.tracks.push(trGiong);
        }
        
        let trNhac = null;
        if (midNhac) {
            trNhac = nhap.tracks.find((t) => t.vai === 'nhac');
            if (!trNhac) {
                trNhac = { id: idTrackMoi(nhap, 'A'), loai: 'audio', ten: 'Nhạc (Demucs)', vai: 'nhac', an: false, khoa: false, tat_tieng: false };
                ops.push(tao.them(nhap, ['tracks'], trNhac));
                nhap.tracks.push(trNhac);
            }
        }
        
        // Chạy tách lần 2: bỏ kết quả tách cũ của cùng video để không chồng hai lớp giọng.
        const cu = nhap.clips.filter((c) => c.tach_giong_cho === midNguon).map((c) => c.id);
        for (const op of opsXoaNhieu(nhap, cu)) { ops.push(op); nhap.clips.splice(op.vi_tri, 1); }
        const nguon = clipChuaMedia(nhap, midNguon).filter((c) => nhap.tracks.find((t) => t.id === c.track && t.loai === 'video'));
        const ids = idMoiNhieu(nhap, nguon.length * (midNhac ? 2 : 1));
        
        nguon.forEach((c, i) => {
            if (!c.tat_am) {
                ops.push(tao.dat(nhap, ['clips', { id: c.id }, 'tat_am'], true));
            }
            
            ops.push(tao.them(nhap, ['clips'], { id: ids[i], track: trGiong.id, media: midGiong, tach_giong_cho: midNguon,
                bat_dau: c.bat_dau, vao: c.vao, ra: c.ra, toc_do: c.toc_do || 1, am_luong: 1 }));
            
            if (midNhac) {
                ops.push(tao.them(nhap, ['clips'], { id: ids[i + nguon.length], track: trNhac.id, media: midNhac, tach_giong_cho: midNguon,
                    bat_dau: c.bat_dau, vao: c.vao, ra: c.ra, toc_do: c.toc_do || 1, am_luong: 1 }));
            }
        });
        return ops;
    }

    // ------------------------------------------------------------ nạp tác vụ
    async tai() {
        clearTimeout(this._h);
        try {
            const r = await api(`/api/du-an/${encodeURIComponent(this.ctx.id)}/tac-vu`);
            const cu = new Map(this.tacVu.map((v) => [v.id, v.trang_thai]));
            const vuaXong = [];
            this.tacVu = r.tac_vu;
            for (const v of this.tacVu) {
                const truoc = cu.get(v.id);
                if (truoc && ['cho', 'dang_chay'].includes(truoc) && v.trang_thai === 'xong' && v.loai !== 'xuat') {
                    this.ctx.bus.emit('media_can_tai');
                    if ((this.cai.tu_ap_dung ?? true) && TU_AP_DUNG.has(v.loai) && !v.da_ap_dung) vuaXong.push(v);
                    else toast(`✔ ${v.nhan} xong — bấm Áp dụng ở bảng AI.`, 'success', 6000);
                }
                if (truoc && ['cho', 'dang_chay'].includes(truoc) && v.trang_thai === 'loi') toast(`✘ ${v.nhan}: ${v.loi}`, 'error', 10000);
            }
            this.ctx.bus.emit('tac_vu', this.tacVu);
            for (const v of vuaXong) {
                if (this._dangAp.has(v.id)) continue;
                this._dangAp.add(v.id);
                try { await this.apDung(v, true); } catch (e) { toast(`${v.nhan} xong nhưng chưa đưa vào timeline được: ${e.message} — bấm Áp dụng ở bảng AI.`, 'error', 10000); }
                finally { this._dangAp.delete(v.id); }
            }
            if (this.el.isConnected) this.ve();
        } catch (e) { /* server bận */ }
        const dang = this.tacVu.some((v) => ['cho', 'dang_chay'].includes(v.trang_thai));
        this._h = setTimeout(() => this.tai(), dang ? 1500 : 10000);
    }
}




