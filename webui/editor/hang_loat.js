import { $, api, esc, toast, chonFile } from './chung.js';
import { veDieuKhien, bindDieuKhien } from './chon_giong.js';

let hlFiles = [];
let hlTimers = null;

const TT = { cho: 'Đang chờ', dang_chay: 'Đang chạy', xong: 'Xong', loi: 'Lỗi', bi_ngat: 'Bị ngắt', da_huy: 'Đã huỷ' };

function renderList(ds) {
    const v = $('hlDanhSach');
    if (!ds || !ds.length) {
        v.innerHTML = '<p>Chưa có lô nào.</p>';
        return;
    }
    v.innerHTML = ds.map(lo => {
        const hien_tai = lo.muc.find(m => m.trang_thai === 'dang_chay') || lo.muc.find(m => m.trang_thai === 'loi' || m.trang_thai === 'bi_ngat') || lo.muc[lo.muc.length - 1];
        const hien_loi = lo.muc.find(m => m.trang_thai === 'loi');
        const countXong = lo.muc.filter(m => m.trang_thai === 'xong').length;
        let dangChay = lo.muc.some(m => m.trang_thai === 'dang_chay' || m.trang_thai === 'cho');
        if (hien_loi) dangChay = false;
        
        return `<article class="the-da" style="height: auto; padding: 15px; cursor: default;">
            <div class="noi">
                <div class="ten">${esc(lo.ten || 'Lô')} (${countXong}/${lo.muc.length} xong)</div>
                <div class="phu">Tạo lúc: ${esc(lo.tao_luc)} - Chế độ: ${lo.che_do === 'gom_mot_du_an' ? 'Gom chung' : 'Mỗi video một dự án'}</div>
                <div class="chip" style="margin-top: 10px;">
                    ${hien_tai ? `<span>Trạng thái: ${TT[hien_tai.trang_thai]} - ${esc(hien_tai.buoc_hien_tai)}</span>` : ''}
                    ${hien_loi ? `<span class="cam">Lỗi: ${esc(hien_loi.loi)}</span>` : ''}
                </div>
            </div>
            <div style="margin-top: 15px; display: flex; gap: 8px; flex-wrap: wrap;">
                ${hien_tai && hien_tai.du_an_id ? `<button class="nut nut-nho" onclick="window.location.href='/editor.html?id=${encodeURIComponent(hien_tai.du_an_id)}'">Mở dự án</button>` : ''}
                ${lo.muc.some(m => m.trang_thai === 'bi_ngat' || m.trang_thai === 'loi') ? `<button class="nut nut-nho" data-chay-tiep="${esc(lo.id)}">↻ Chạy tiếp</button>` : ''}
                ${dangChay ? `<button class="nut nut-nho" data-huy="${esc(lo.id)}">Huỷ</button>` : ''}
            </div>
        </article>`;
    }).join('');
    
    v.querySelectorAll('[data-chay-tiep]').forEach(b => {
        b.onclick = async () => {
            try {
                await api(`/api/hang-loat/${b.dataset.chayTiep}/chay-tiep`, {method: 'POST'});
                toast('Đã xếp lệnh chạy tiếp', 'success');
                loadList();
            } catch(e) { toast(e.message, 'error'); }
        };
    });
    
    v.querySelectorAll('[data-huy]').forEach(b => {
        b.onclick = async () => {
            try {
                await api(`/api/hang-loat/${b.dataset.huy}/huy`, {method: 'POST'});
                toast('Đã gửi lệnh huỷ', 'info');
                loadList();
            } catch(e) { toast(e.message, 'error'); }
        };
    });
}

async function loadList() {
    clearTimeout(hlTimers);
    try {
        const r = await api('/api/hang-loat');
        renderList(r.lo);
        const dangChay = r.lo.some(lo => lo.muc.some(m => m.trang_thai === 'dang_chay' || m.trang_thai === 'cho'));
        if (dangChay) hlTimers = setTimeout(loadList, 2000);
    } catch (e) {
        // error
    }
}

export async function initHangLoat() {
    // Phục hồi từ localStorage và lấy mặc định
    try {
        const confRes = await api('/api/config');
        const g = confRes || {};              // GET /api/config trả thẳng object cấu hình (không bọc trong .config)
        const tr = g.translate || {};
        const as = g.autosub || {};
        const vi = g.video || {};
        
        const ca = JSON.parse(localStorage.getItem('hlCaiDat') || '{}');
        
        const defTTS = as.tts_engine || tr.tts_engine || 'edge';
        const defGiong = as.tts_voice || tr.tts_voice || '';
        const defDich = tr.target_lang || 'Vietnamese';
        const defNgonNguChu = tr.source_lang || 'Chinese';
        const defNgonNguNoi = tr.source_lang || 'Chinese';

        // Wait, UI does not have hlNgonNguChu, hlNgonNguNoi in html yet. 
        // We will just set what we have in JS. The HTML in luot6.md might not have it or might.
        // The prompt says "đọc giá trị mặc định từ `/api/config` như bảng AI đang làm (xem webui/editor/bang_ai.js cách nó lấy engine dịch, model Ollama, giọng TTS mặc định)".
        
        $('hlDichSang').value = ca['hlDichSang'] !== undefined ? ca['hlDichSang'] : defDich;
        $('hlGiongTTS').value = ca['hlGiongTTS'] !== undefined ? ca['hlGiongTTS'] : defTTS;
        
        let ttsVoiceVal = ca['hlGiongTen'] !== undefined ? ca['hlGiongTen'] : defGiong;
        window.hlTtsVoiceVal = ttsVoiceVal;
        
        const updateTtsUi = () => {
            const eng = $('hlGiongTTS').value;
            const lang = $('hlDichSang').value;
            const caLocal = JSON.parse(localStorage.getItem('hlCaiDat') || '{}');
            const curVal = caLocal[`hlGiongTen_${eng}`] || window.hlTtsVoiceVal || '';
            $('hlAiChonGiong').innerHTML = veDieuKhien(eng, curVal, 'hlCg', caLocal.hlTtsSpeed ?? as.tts_speed ?? 1.0, caLocal.hlTtsPitch ?? as.tts_pitch ?? 0);
            // Hộp thoại hàng loạt lưu cài đặt vào localStorage 'hlCaiDat' (không có this.cai/ctx như bảng AI).
            const luu = (doi) => {
                const ca2 = JSON.parse(localStorage.getItem('hlCaiDat') || '{}');
                doi(ca2);
                localStorage.setItem('hlCaiDat', JSON.stringify(ca2));
            };
            bindDieuKhien($('hlAiChonGiong'), eng, lang, curVal, (val) => {
                window.hlTtsVoiceVal = val;
                luu((ca2) => { ca2.hlGiongTen = val; ca2[`hlGiongTen_${eng}`] = val; });
            }, (speed) => luu((ca2) => { ca2.hlTtsSpeed = speed; }),
               (pitch) => luu((ca2) => { ca2.hlTtsPitch = pitch; }));
        };
        $('hlGiongTTS').addEventListener('change', updateTtsUi);
        $('hlDichSang').addEventListener('change', updateTtsUi);
        // Call updateTtsUi to initially render it
        setTimeout(updateTtsUi, 50);

        ['hlCheDo', 'hlKhungHinh', 'hlPhuDeLoai', 'hlVungOcr', 'hlXuatChatLuong', 'hlXuatBoMaHoa'].forEach(id => {
            if (ca[id] !== undefined && $(id)) $(id).value = ca[id];
        });
        ['hlTaoPhuDe', 'hlChePhuDe', 'hlDich', 'hlLongTieng', 'hlXuat'].forEach(id => {
            if (ca[id] !== undefined) $(id).checked = ca[id];
        });
    } catch(e) {}
    
    const uiUpdate = () => {
        $('hlPhuDeVung').style.display = $('hlTaoPhuDe').checked ? 'block' : 'none';
        $('hlOcrVung').style.display = $('hlPhuDeLoai').value === 'ocr' ? 'block' : 'none';
        $('hlDichVung').style.display = $('hlDich').checked ? 'block' : 'none';
        $('hlLongTiengVung').style.display = $('hlLongTieng').checked ? 'block' : 'none';
        $('hlXuatVung').style.display = $('hlXuat').checked ? 'flex' : 'none';
        
        const ca = JSON.parse(localStorage.getItem('hlCaiDat') || '{}');
        ['hlCheDo', 'hlKhungHinh', 'hlPhuDeLoai', 'hlVungOcr', 'hlDichSang', 'hlGiongTTS', 'hlXuatChatLuong', 'hlXuatBoMaHoa'].forEach(id => ca[id] = $(id).value);
        ca['hlGiongTen'] = window.hlTtsVoiceVal || '';
        ['hlTaoPhuDe', 'hlChePhuDe', 'hlDich', 'hlLongTieng', 'hlXuat'].forEach(id => ca[id] = $(id).checked);
        localStorage.setItem('hlCaiDat', JSON.stringify(ca));
    };
    
    ['hlTaoPhuDe', 'hlPhuDeLoai', 'hlDich', 'hlLongTieng', 'hlXuat'].forEach(id => $(id).addEventListener('change', uiUpdate));
    uiUpdate();
    
    let hlThuMuc = '';
    
    function renderSelectedFiles() {
        const v = $('hlSoFile');
        let htm = [];
        if (hlThuMuc) {
            htm.push(`<div>📂 Thư mục: ${esc(hlThuMuc.split('/').pop().split('\\').pop())} <span style="cursor:pointer;color:red;" data-xoa-folder="1">✕</span></div>`);
        }
        if (hlFiles.length) {
            htm.push(hlFiles.map((f, i) => `<div>📄 ${esc(f.split('/').pop().split('\\').pop())} <span style="cursor:pointer;color:red;" data-xoa-file="${i}">✕</span></div>`).join(''));
        }
        if (!htm.length) {
            v.innerHTML = '0 file đã chọn';
            return;
        }
        v.innerHTML = htm.join('');
        v.querySelectorAll('[data-xoa-file]').forEach(b => {
            b.onclick = () => {
                hlFiles.splice(Number(b.dataset.xoaFile), 1);
                renderSelectedFiles();
            };
        });
        const bx = v.querySelector('[data-xoa-folder]');
        if (bx) {
            bx.onclick = () => {
                hlThuMuc = '';
                renderSelectedFiles();
            };
        }
    }

    $('hlChonFile').onclick = async () => {
        try {
            const files = await chonFile('media');
            if (files && files.length) {
                hlFiles = [...hlFiles, ...files];
                renderSelectedFiles();
            }
        } catch(e) { toast(e.message, 'error'); }
    };
    
    const hlChonThuMucBtn = document.createElement('button');
    hlChonThuMucBtn.className = 'nut';
    hlChonThuMucBtn.textContent = '📂 Chọn cả thư mục';
    hlChonThuMucBtn.style.marginLeft = '10px';
    hlChonThuMucBtn.onclick = async () => {
        try {
            const folder = await chonFile('folder');
            if (folder) {
                hlThuMuc = folder;
                renderSelectedFiles();
            }
        } catch(e) { toast(e.message, 'error'); }
    };
    $('hlChonFile').parentNode.insertBefore(hlChonThuMucBtn, $('hlChonFile').nextSibling);
    
    $('hlChay').onclick = async () => {
        const urls = $('hlUrls').value.split('\n').map(x => x.trim()).filter(Boolean);
        if (!hlFiles.length && !urls.length && !hlThuMuc) {
            toast('Hãy chọn file hoặc dán link.', 'warn');
            return;
        }
        
        const buoc = {};
        if ($('hlTaoPhuDe').checked) {
            buoc.phu_de = $('hlPhuDeLoai').value;
            if (buoc.phu_de === 'ocr') {
                const v = $('hlVungOcr').value.split(',').map(x => parseFloat(x));
                if (v.length === 4) {
                    buoc.vung_ocr = {x: v[0]/100, y: v[1]/100, w: v[2]/100, h: v[3]/100};
                }
                buoc.che_phu_de = $('hlChePhuDe').checked;
            }
        }
        if ($('hlDich').checked) {
            buoc.dich = { target_lang: $('hlDichSang').value };
        }
        if ($('hlLongTieng').checked) {
            const caTts = JSON.parse(localStorage.getItem('hlCaiDat') || '{}');
            buoc.long_tieng = {
                tts_engine: $('hlGiongTTS').value,
                tts_voice: window.hlTtsVoiceVal,
                tts_speed: caTts.hlTtsSpeed,
                tts_pitch: caTts.hlTtsPitch,
                target_lang: $('hlDichSang').value,
                auto_clone: $('hlGiongTTS').value === 'clone' && (!window.hlTtsVoiceVal || window.hlTtsVoiceVal === 'auto'),
                ducking_ratio: 90
            };
        }
        if ($('hlXuat').checked) {
            buoc.xuat = {
                do_phan_giai: "",
                bo_ma_hoa: $('hlXuatBoMaHoa').value || "auto",
                crf: parseInt($('hlXuatChatLuong').value) || 19,
                xuat_srt: true
            };
        }
        
        const kh = $('hlKhungHinh').value;
        const thong_so = kh === 'theo_video_dau' ? {theo_video_dau: true} :
                         kh === '16:9' ? {rong: 1920, cao: 1080, fps: 30} :
                         kh === '9:16' ? {rong: 1080, cao: 1920, fps: 30} :
                         {rong: 1080, cao: 1080, fps: 30};
        
        const data = {
            files: hlFiles,
            urls: urls,
            thu_muc: hlThuMuc || null,
            che_do: $('hlCheDo').value,
            ten: $('hlTen').value || 'Lô video',
            thong_so: thong_so,
            buoc: buoc
        };
        
        $('hlChay').disabled = true;
        try {
            await api('/api/hang-loat', { method: 'POST', body: data });
            toast('Đã thêm vào hàng đợi.', 'success');
            hlFiles = [];
            hlThuMuc = '';
            renderSelectedFiles();
            $('hlUrls').value = '';
            loadList();
        } catch(e) {
            toast(e.message, 'error');
        } finally {
            $('hlChay').disabled = false;
        }
    };
    
    // Khi load trang
    loadList();
    $('tcTab').addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (b && b.dataset.tab === 'hang-loat') {
            loadList();
        }
    });
}


