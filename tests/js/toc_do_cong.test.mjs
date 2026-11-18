// Chạy: node --test tests/js/
// Đồ thị tốc độ clip (webui/editor/toc_do_cong.js) + chỗ store.js dùng nó (ánh xạ thời gian, cắt clip).
import test from 'node:test';
import assert from 'node:assert/strict';
import { chuan, trungBinh, nguonTai, viTriTai, catCong, MAU_DO_THI, tuMau } from '../../webui/editor/toc_do_cong.js';
import { thoiDiemMedia, veTimeline, tocDoTai, opsTach, opsTiaToiDauPhat, ketThucClip, apOp } from '../../webui/editor/store.js';
import CA from './ca_toc_do_cong.json' with { type: 'json' };

const gan = (a, b, sai = 1e-6, ten = '') => assert.ok(Math.abs(a - b) <= sai, `${ten}: ${a} ≠ ${b}`);

for (const ca of CA.ca) {
    test(`đồ thị tốc độ — ${ca.ten}`, () => {
        const d = chuan(ca.cong);
        gan(trungBinh(d), ca.trung_binh, 1e-9, 'trung bình');
        for (const [q, p] of ca.nguon) {
            gan(nguonTai(d, q), p, 1e-6, `P(${q})`);
            gan(viTriTai(d, p), q, 1e-6, `Q(${p})`);
        }
    });
}

test('cắt đồ thị giữ đúng tốc độ hai bên', () => {
    const [trai, phai] = catCong(chuan(CA.cat.cong), CA.cat.q);
    assert.deepEqual(trai, CA.cat.trai);
    assert.deepEqual(phai, CA.cat.phai);
});

test('mọi mẫu có sẵn hợp lệ và đi đủ đoạn nguồn', () => {
    for (const m of MAU_DO_THI) {
        const d = tuMau(m.id);
        assert.ok(d && d[0].q === 0 && d[d.length - 1].q === 1, m.id);
        gan(nguonTai(d, 1), 1, 1e-9, m.id);
    }
});

// Clip 4 s nguồn, tốc 1× → 3× (trung bình 2×) → dài 2 s trên timeline.
const clip = () => ({ id: 'c_1', track: 'V1', media: 'm1', bat_dau: 10, vao: 1, ra: 5, toc_do: 2,
    toc_do_cong: [{ q: 0, v: 1 }, { q: 1, v: 3 }] });

test('ánh xạ timeline ↔ media theo đồ thị', () => {
    const c = clip();
    assert.equal(ketThucClip(c), 12);
    gan(thoiDiemMedia(c, 11), 1 + 4 * 0.375, 1e-9, 'giữa clip');
    gan(veTimeline(c, 2.5), 1, 1e-9, 'ngược lại');
    gan(tocDoTai(c, 11), 2, 1e-9, 'tốc độ giữa clip');
    gan(tocDoTai(c, 10), 1, 1e-9, 'tốc độ đầu clip');
});

test('cắt clip có đồ thị: hai nửa nối liền, đúng độ dài và nguồn', () => {
    const tl = { tracks: [{ id: 'V1' }], clips: [clip()] };
    for (const op of opsTach(tl, 'c_1', 11, 'c_2')) apOp(tl, op);
    const [a, b] = tl.clips;
    gan(ketThucClip(a), 11, 1e-4, 'nửa trước kết thúc ở chỗ cắt');
    gan(ketThucClip(b), 12, 1e-4, 'nửa sau kết thúc như cũ');
    gan(a.ra, 2.5, 1e-3, 'nguồn chỗ cắt');
    gan(thoiDiemMedia(b, 11.5), thoiDiemMedia(clip(), 11.5), 2e-3, 'nửa sau phát đúng chỗ nguồn');
    gan(tocDoTai(b, 11), 2, 1e-3, 'tốc độ liền ở chỗ cắt');
});

test('tỉa tới đầu phát giữ đúng phần đồ thị còn lại', () => {
    const tl = { tracks: [{ id: 'V1' }], clips: [clip()] };
    for (const op of opsTiaToiDauPhat(tl, ['c_1'], 11, 'sau', false)) apOp(tl, op);
    const [a] = tl.clips;
    gan(ketThucClip(a), 11, 1e-4, 'kết thúc ở đầu phát');
    gan(tocDoTai(a, 10.5), 1.5, 1e-3, 'tốc độ phần trước giữ nguyên');
});
