/* Tiếng cho xuất trên thiết bị: SERVER dựng (cùng bộ lọc với bản xuất server — hiệu ứng, ducking, hiệu ứng chung… khớp 100%),
   máy chỉ CHÉP luồng AAC vào MP4 (không giải mã/mã hoá lại). Đường: POST /xuat {chi_am_thanh} → chờ tác vụ → tải .m4a
   → đọc gói AAC (Mediabunny) → xoá file tạm trên server. */
import { ALL_FORMATS, BlobSource, EncodedPacketSink, Input } from '../thu_vien_ngoai/mediabunny-1.65.1.min.js';
import { api } from '../chung.js';

const cho = (ms) => new Promise((r) => setTimeout(r, ms));

/* Trả {cauHinh: AudioDecoderConfig, goi: AsyncIterator<EncodedPacket>, dong()} hoặc null nếu dự án không có tiếng. */
export async function layTiengServer(pid, phien, tuyChon, baoTienDo = () => {}, daHuy = () => false) {
    const ten = `${tuyChon.ten || 'video'} tieng-thiet-bi`;
    const g = `/api/du-an/${encodeURIComponent(pid)}`;
    const r = await api(`${g}/xuat`, { method: 'POST', body: { phien, tuy_chon: { ...tuyChon, ten, chi_am_thanh: true, xuat_srt: false, may_xuat: '' } } });
    const vid = r.viec.id;
    let tenFile = (r.file || '').split('/').pop();
    for (;;) {
        if (daHuy()) throw new Error('Đã huỷ');
        const ds = await api(`${g}/tac-vu`);
        const v = (Array.isArray(ds) ? ds : ds.ds || ds.tac_vu || []).find((x) => x.id === vid);
        if (v && v.trang_thai === 'xong') { tenFile = ((v.ket_qua || {}).file || tenFile).split('/').pop(); break; }
        if (v && ['loi', 'da_huy', 'bi_ngat'].includes(v.trang_thai)) throw new Error(`Server dựng tiếng lỗi: ${v.loi || v.trang_thai}`);
        baoTienDo(Math.round((v && v.tien_do) || 0), v && v.trang_thai === 'cho' ? 'Chờ server dựng tiếng…' : 'Server đang dựng tiếng…');
        await cho(800);
    }
    const res = await fetch(`${g}/xuat/tai?ten=${encodeURIComponent(tenFile)}`);
    if (!res.ok) throw new Error(`Không tải được tiếng (HTTP ${res.status})`);
    const blob = await res.blob();
    api(`${g}/xuat/tai?ten=${encodeURIComponent(tenFile)}`, { method: 'DELETE' }).catch(() => {});   // dọn file tạm
    const input = new Input({ source: new BlobSource(blob), formats: ALL_FORMATS });
    const track = await input.getPrimaryAudioTrack();
    if (!track) { input.dispose(); return null; }
    return {
        cauHinh: await track.getDecoderConfig(),
        goi: new EncodedPacketSink(track).packets()[Symbol.asyncIterator](),
        dong: () => input.dispose(),
    };
}
