// Chạy: node --test tests/js/
// Thao tác dựng nâng cao (webui/editor/thao_tac_clip.js): Ken Burns, đóng băng khung hình, crossfade âm thanh.
import test from 'node:test';
import assert from 'node:assert/strict';
import { Store, ketThucClip, giaTriTai } from '../../webui/editor/store.js';
import { opsKenBurns, opsDongBang, opsNoiMuotAm, capNoiMuot } from '../../webui/editor/thao_tac_clip.js';

const tlMau = () => ({
    tracks: [{ id: 'V1', loai: 'video' }, { id: 'O1', loai: 'lop_phu' }, { id: 'A1', loai: 'audio' }, { id: 'A2', loai: 'audio' }],
    clips: [
        { id: 'c_1', track: 'V1', media: 'm1', bat_dau: 0, vao: 0, ra: 6, toc_do: 1, lien_ket: 'lk_1', bien_doi: { x: 0.5, y: 0.5, ti_le: 1.5, xoay: 0 }, keyframes: {} },
        { id: 'c_2', track: 'V1', media: 'm2', bat_dau: 6, vao: 0, ra: 4, toc_do: 1 },
        { id: 'c_3', track: 'A1', media: 'm1', bat_dau: 0, vao: 0, ra: 6, toc_do: 1, lien_ket: 'lk_1' },   // tiếng tách của c_1
        { id: 'c_4', track: 'A2', media: 'nhac', bat_dau: 0, vao: 0, ra: 20, toc_do: 1 },                   // nhạc nền chạy ngang
        { id: 'c_5', track: 'O1', loai: 'chu', bat_dau: 7, ket_thuc: 9, noi_dung: 'Chào' },
    ],
});

test('Ken Burns ghi hai keyframe đầu–cuối, bỏ thì xoá sạch và giữ keyframe khác', () => {
    const s = new Store(tlMau());
    s.timeline.clips[0].keyframes = { 'hien_thi.do_mo': [{ t: 0, v: 1 }] };
    s.thucHien('KB', opsKenBurns(s.timeline, s.timeline.clips[0], 'zoom_vao'));
    const c = s.timeline.clips[0];
    assert.equal(giaTriTai(c, 'bien_doi.ti_le', 0), 1.5);
    assert.equal(giaTriTai(c, 'bien_doi.ti_le', 6), 1.875);
    s.thucHien('KB', opsKenBurns(s.timeline, c, 'lia_trai'));
    assert.equal(giaTriTai(c, 'bien_doi.ti_le', 3), 1.8);
    assert.ok(giaTriTai(c, 'bien_doi.x', 0) > giaTriTai(c, 'bien_doi.x', 6));
    s.thucHien('KB', opsKenBurns(s.timeline, c, 'bo'));
    assert.deepEqual(Object.keys(c.keyframes), ['hien_thi.do_mo']);
});

test('đóng băng giữa clip: cắt cả tiếng liên kết, chèn ảnh 2 s, mọi thứ phía sau lùi 2 s, nhạc nền giữ nguyên', () => {
    const s = new Store(tlMau());
    const kq = opsDongBang(s.timeline, 'c_1', 2.5, { id: 'm_anh' }, 2);
    s.thucHien('Đóng băng', kq.ops);
    const tim = (id) => s.timeline.clips.find((c) => c.id === id);
    const anh = tim(kq.id);
    assert.deepEqual([anh.track, anh.media, anh.bat_dau, anh.ra, anh.bien_doi.ti_le, anh.lien_ket], ['V1', 'm_anh', 2.5, 2, 1.5, undefined]);
    assert.equal(tim('c_1').ra, 2.5);
    const sauV = s.timeline.clips.find((c) => c.track === 'V1' && c.media === 'm1' && c.id !== 'c_1');
    const sauA = s.timeline.clips.find((c) => c.track === 'A1' && c.id !== 'c_3');
    assert.deepEqual([sauV.bat_dau, sauV.vao, sauA.bat_dau, sauA.vao], [4.5, 2.5, 4.5, 2.5]);
    assert.ok(sauV.lien_ket && sauV.lien_ket === sauA.lien_ket && sauV.lien_ket !== 'lk_1');
    assert.equal(tim('c_2').bat_dau, 8);
    assert.deepEqual([tim('c_5').bat_dau, tim('c_5').ket_thuc], [9, 11]);
    assert.deepEqual([tim('c_4').bat_dau, tim('c_4').ra], [0, 20]);
    s.hoanTacMot();
    assert.deepEqual(s.timeline, tlMau());
});

test('đóng băng ở mép cuối clip không cắt, chỉ chèn ảnh sau clip', () => {
    const tl = tlMau();
    const kq = opsDongBang(tl, 'c_1', 6, { id: 'm_anh' }, 1);
    assert.equal(kq.ops.filter((o) => o.op === 'them').length, 1);
    assert.equal(kq.ops.find((o) => o.op === 'them').gia_tri.bat_dau, 6);
    assert.equal(opsDongBang(tl, 'c_1', 9, { id: 'm_anh' }), null);
});

test('crossfade âm thanh: clip sau sang track khác, sớm 0.5 s, hai clip fade chéo', () => {
    const tl = { tracks: [{ id: 'A1', loai: 'audio' }, { id: 'A2', loai: 'audio' }], clips: [
        { id: 'a', track: 'A1', media: 'm1', bat_dau: 0, vao: 0, ra: 5, toc_do: 1 },
        { id: 'b', track: 'A1', media: 'm2', bat_dau: 5, vao: 3, ra: 8, toc_do: 1 },
        { id: 'x', track: 'A2', media: 'm3', bat_dau: 4, vao: 0, ra: 2, toc_do: 1 },        // A2 bận → phải thêm track
    ] };
    assert.equal(capNoiMuot(tl, ['a', 'x']), null);
    const s = new Store(tl);
    const kq = opsNoiMuotAm(s.timeline, ['b', 'a']);
    s.thucHien('Crossfade', kq.ops);
    const [a, b] = s.timeline.clips;
    assert.equal(kq.track, 'A3');
    assert.deepEqual([b.track, b.bat_dau, b.vao, b.am_vao, a.am_ra, ketThucClip(b)], ['A3', 4.5, 2.5, 0.5, 0.5, 10]);
});

test('crossfade khi clip sau không còn phần đầu để lấy thêm: cả clip dời sớm lên', () => {
    const tl = { tracks: [{ id: 'A1', loai: 'audio' }, { id: 'A2', loai: 'audio' }], clips: [
        { id: 'a', track: 'A1', media: 'm1', bat_dau: 0, vao: 0, ra: 5, toc_do: 1 },
        { id: 'b', track: 'A1', media: 'm2', bat_dau: 5, vao: 0, ra: 4, toc_do: 1 }] };
    const s = new Store(tl);
    const kq = opsNoiMuotAm(s.timeline, ['a', 'b']);
    s.thucHien('Crossfade', kq.ops);
    const b = s.timeline.clips[1];
    assert.deepEqual([kq.track, b.bat_dau, b.vao, ketThucClip(b)], ['A2', 4.5, 0, 8.5]);
});

test('tách phụ đề dùng chung: clip trùng đoạn nguồn nhận nhóm riêng + bản sao câu, mảnh đã cắt giữ nguyên', async () => {
    const { opsTachNeo } = await import('../../webui/editor/thao_tac_clip.js');
    const { hienThiNeo } = await import('../../webui/editor/store.js');
    const tl = { tracks: [{ id: 'V1', loai: 'video' }, { id: 'S1', loai: 'phu_de' }], clips: [
        { id: 'c_1', track: 'V1', media: 'm1', bat_dau: 0, vao: 0, ra: 3, toc_do: 1 },       // hai mảnh của một lần cắt
        { id: 'c_2', track: 'V1', media: 'm1', bat_dau: 3, vao: 3, ra: 6, toc_do: 1 },
        { id: 'c_3', track: 'V1', media: 'm1', bat_dau: 20, vao: 0, ra: 2, toc_do: 1 },      // cùng video thêm lần nữa
        { id: 'c_4', track: 'S1', loai: 'phu_de', tu_media: 'm1', t_vao: 1, t_ra: 1.5, text: 'Ơ Duy' },
        { id: 'c_5', track: 'S1', loai: 'phu_de', tu_media: 'm1', t_vao: 4, t_ra: 5, text: 'chỉ ở mảnh sau' },
    ] };
    const s = new Store(tl);
    const kq = opsTachNeo(s.timeline);
    assert.equal(kq.soCau, 1);
    s.thucHien('Tách', kq.ops);
    const c = s.timeline.clips;
    assert.deepEqual([c[0].nhom_neo, c[1].nhom_neo, c[2].nhom_neo], [undefined, undefined, 'n_1']);
    const ban = c.find((x) => x.tu_nhom === 'n_1');
    assert.equal(ban.text, 'Ơ Duy');
    assert.deepEqual(hienThiNeo(s.timeline, c[3]).map((k) => k.clip), ['c_1']);
    assert.deepEqual(hienThiNeo(s.timeline, ban).map((k) => [k.clip, k.bd]), [['c_3', 21]]);
    assert.equal(opsTachNeo(s.timeline).soCau, 0, 'tách rồi thì không còn gì dính');
});

test('tự cắt khoảng lặng: bỏ phần im (chừa đệm), phần sau dồn lên, tiếng liên kết cắt y hệt', async () => {
    const { opsCatKhoangLang } = await import('../../webui/editor/thao_tac_clip.js');
    const tl = { tracks: [{ id: 'V1', loai: 'video' }, { id: 'A1', loai: 'audio' }], clips: [
        { id: 'c_1', track: 'V1', media: 'm1', bat_dau: 10, vao: 2, ra: 12, toc_do: 1, lien_ket: 'lk_1' },     // 10 → 20
        { id: 'c_2', track: 'V1', media: 'm2', bat_dau: 20, vao: 0, ra: 3, toc_do: 1 },
        { id: 'c_3', track: 'A1', media: 'm1', bat_dau: 10, vao: 2, ra: 12, toc_do: 1, lien_ket: 'lk_1' },
    ] };
    const s = new Store(tl);
    // media: im 4–6 s (timeline 12–14) và 9–13 s (timeline 17–20, chạm cuối clip); khoảng 0–1 s nằm ngoài clip.
    const kq = opsCatKhoangLang(s.timeline, 'c_1', [[0, 1], [4, 6], [9, 13]], 0.25);
    assert.equal(kq.so, 2);
    assert.equal(kq.giam, 1.5 + 2.75);
    s.thucHien('Cắt lặng', kq.ops);
    const tren = (tr) => s.timeline.clips.filter((c) => c.track === tr).sort((a, b) => a.bat_dau - b.bat_dau)
        .map((c) => [c.media, c.bat_dau, c.vao, c.ra]);
    assert.deepEqual(tren('V1'), [['m1', 10, 2, 4.25], ['m1', 12.25, 5.75, 9.25], ['m2', 15.75, 0, 3]]);
    assert.deepEqual(tren('A1'), [['m1', 10, 2, 4.25], ['m1', 12.25, 5.75, 9.25]]);
    assert.equal(opsCatKhoangLang(s.timeline, 'c_2', [[5, 9]]), null, 'không có khoảng lặng trong clip');
});

test('hiệu ứng vào/ra của clip: keyframe ở đầu và cuối, đổi sang Không thì gỡ sạch', async () => {
    const { opsHieuUngClip } = await import('../../webui/editor/thao_tac_clip.js');
    const s = new Store({ tracks: [{ id: 'V1', loai: 'video' }], clips: [
        { id: 'c_1', track: 'V1', media: 'm1', bat_dau: 5, vao: 0, ra: 4, toc_do: 1, bien_doi: { x: 0.5, y: 0.5, ti_le: 1, xoay: 0 },
            keyframes: { 'bien_doi.xoay': [{ t: 0, v: 10 }] } }] });
    const c = s.timeline.clips[0];
    s.thucHien('HU', opsHieuUngClip(s.timeline, c, 'phong_to', 'truot_trai', 0.5));
    assert.equal(giaTriTai(c, 'hien_thi.do_mo', 0), 0);
    assert.equal(giaTriTai(c, 'hien_thi.do_mo', 0.5), 1);
    assert.equal(giaTriTai(c, 'bien_doi.ti_le', 0), 0.6);
    assert.equal(giaTriTai(c, 'bien_doi.ti_le', 2), 1);
    assert.equal(giaTriTai(c, 'bien_doi.x', 3.5), 0.5);
    assert.equal(giaTriTai(c, 'bien_doi.x', 4), -0.1);
    assert.deepEqual([c.hu_vao, c.hu_ra, c.hu_dai], ['phong_to', 'truot_trai', 0.5]);
    s.thucHien('HU', opsHieuUngClip(s.timeline, c, '', '', 0.5));
    assert.deepEqual(Object.keys(c.keyframes), ['bien_doi.xoay']);
    assert.deepEqual([c.hu_vao, c.hu_ra, c.hu_dai], [undefined, undefined, undefined]);
});
