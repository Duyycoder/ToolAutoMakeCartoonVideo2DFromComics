// Chạy: node --test tests/js/
// Lệnh hoàn tác của editor (webui/editor/store.js): áp/đảo op, gộp, giới hạn, thay toàn bộ.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
    Store, tao, apOp, daoOp, choTrong, thoiLuong, idClipMoi, GIOI_HAN_GHI,
    clipTai, thoiDiemMedia, hutDinh, diemDinh, chongClip, gioiHanTia, opsTach, ketThucClip,
    giaTriTai, tachKeyframes, viTriKeyframes
} from '../../webui/editor/store.js';

const tl2 = () => ({ tracks: [{ id: 'V1' }], clips: [
    { id: 'c_1', track: 'V1', media: 'm1', bat_dau: 0, vao: 2, ra: 7, toc_do: 1 },     // 0 → 5
    { id: 'c_2', track: 'V1', media: 'm2', bat_dau: 8, vao: 0, ra: 4, toc_do: 2 },     // 8 → 10
] });

test('clip dưới đầu phát và thời điểm trong media gốc', () => {
    const tl = tl2();
    assert.equal(clipTai(tl, 'V1', 4.99).id, 'c_1');
    assert.equal(clipTai(tl, 'V1', 5), null, 'mép phải không tính');
    assert.equal(clipTai(tl, 'V1', 6.5), null, 'khoảng trống');
    assert.equal(thoiDiemMedia(tl.clips[0], 1), 3);
    assert.equal(thoiDiemMedia(tl.clips[1], 9), 2, 'tốc độ 2×');
});

test('bắt dính hút vào điểm gần nhất trong ngưỡng', () => {
    const d = diemDinh(tl2(), 6, ['c_2']);
    assert.deepEqual(d.sort((a, b) => a - b), [0, 0, 5, 6]);
    assert.equal(hutDinh(5.1, d, 0.2), 5);
    assert.equal(hutDinh(5.5, d, 0.2), 5.5);
    assert.equal(hutDinh(5.9, d, 0.2), 6);
});

test('chồng clip và giới hạn tỉa', () => {
    const tl = tl2();
    assert.equal(chongClip(tl, 'V1', 4, 6), true);
    assert.equal(chongClip(tl, 'V1', 5, 8), false, 'vừa khít khe');
    assert.equal(chongClip(tl, 'V1', 4, 6, ['c_1']), false);
    const g1 = gioiHanTia(tl, tl.clips[0], 20, false);
    assert.equal(g1.sanTrai, 0, 'vao=2 nhưng không kéo trước 0');
    assert.equal(g1.tranPhai, 8, 'đụng c_2');
    const g2 = gioiHanTia(tl, tl.clips[1], 5, false);
    assert.equal(g2.sanTrai, 8, 'vao=0 nên không kéo mép trái ra thêm');
    assert.equal(g2.tranPhai, 10.5, 'media 5s, ra=4, tốc 2× → còn 0,5s');
});

test('cắt clip tại đầu phát rồi hoàn tác', () => {
    const s = new Store(tl2());
    const ops = opsTach(s.timeline, 'c_1', 3, 'c_3');
    s.thucHien('Cắt', ops);
    const [a, b] = s.timeline.clips;
    assert.equal(ketThucClip(a), 3);
    assert.deepEqual([b.id, b.bat_dau, b.vao, b.ra], ['c_3', 3, 5, 7]);
    assert.equal(opsTach(s.timeline, 'c_1', 0.01, 'x'), null, 'sát mép thì không cắt');
    s.hoanTacMot();
    assert.deepEqual(s.timeline.clips.map((c) => [c.id, c.ra]), [['c_1', 7], ['c_2', 4]]);
});

const tlMau = () => ({
    schema: 1, phien_ban: 3,
    tracks: [{ id: 'V1', an: false }, { id: 'A1', an: false }],
    clips: [{ id: 'c_1', track: 'V1', media: 'm_01', bat_dau: 0, vao: 0, ra: 5, toc_do: 1 }],
});

test('đặt giá trị theo id rồi hoàn tác/làm lại', () => {
    const s = new Store(tlMau());
    s.thucHien('Ẩn V1', [tao.dat(s.timeline, ['tracks', { id: 'V1' }, 'an'], true)]);
    assert.equal(s.timeline.tracks[0].an, true);
    s.hoanTacMot();
    assert.equal(s.timeline.tracks[0].an, false);
    s.lamLaiMot();
    assert.equal(s.timeline.tracks[0].an, true);
});

test('thêm/xoá clip hoàn tác đúng vị trí', () => {
    const s = new Store(tlMau());
    const clip = { id: 'c_2', track: 'V1', bat_dau: 5, vao: 0, ra: 2, toc_do: 1 };
    s.thucHien('Thêm', [tao.them(s.timeline, ['clips'], clip)]);
    s.thucHien('Xoá c_1', [tao.xoaTheoId(s.timeline, ['clips'], 'c_1')]);
    assert.deepEqual(s.timeline.clips.map((c) => c.id), ['c_2']);
    s.hoanTacMot();
    assert.deepEqual(s.timeline.clips.map((c) => c.id), ['c_1', 'c_2']);
    s.hoanTacMot();
    assert.deepEqual(s.timeline.clips.map((c) => c.id), ['c_1']);
});

test('lệnh mới xoá ngăn làm lại', () => {
    const s = new Store(tlMau());
    s.thucHien('a', [tao.dat(s.timeline, ['tracks', { id: 'V1' }, 'an'], true)]);
    s.hoanTacMot();
    s.thucHien('b', [tao.dat(s.timeline, ['tracks', { id: 'A1' }, 'an'], true)]);
    assert.equal(s.lamLai.length, 0);
    assert.equal(s.lamLaiMot(), null);
});

test('op lỗi giữa chừng thì trả lại nguyên trạng', () => {
    const s = new Store(tlMau());
    const truoc = JSON.stringify(s.timeline);
    assert.throws(() => s.thucHien('hỏng', [
        tao.dat(s.timeline, ['tracks', { id: 'V1' }, 'an'], true),
        { op: 'dat', path: ['clips', { id: 'khong_co' }, 'x'], cu: 1, moi: 2 },
    ]));
    assert.equal(JSON.stringify(s.timeline), truoc);
    assert.equal(s.hoanTac.length, 0);
});

test('gộp lệnh kéo thanh trượt trong 800ms thành một bước, giữ giá trị ban đầu', () => {
    const s = new Store(tlMau());
    const p = ['clips', { id: 'c_1' }, 'toc_do'];
    s.thucHien('Tốc độ', [tao.dat(s.timeline, p, 1.5)], { gop: 'toc', bayGio: 1000 });
    s.thucHien('Tốc độ', [tao.dat(s.timeline, p, 2)], { gop: 'toc', bayGio: 1500 });
    s.thucHien('Tốc độ', [tao.dat(s.timeline, p, 3)], { gop: 'toc', bayGio: 3000 });   // quá 800ms → bước mới
    assert.equal(s.hoanTac.length, 2);
    s.hoanTacMot();
    assert.equal(s.timeline.clips[0].toc_do, 2);
    s.hoanTacMot();
    assert.equal(s.timeline.clips[0].toc_do, 1);
});

test('ngăn hoàn tác ghi JSON được, 50 bước cuối, nạp lại vẫn Ctrl+Z được', () => {
    const s = new Store(tlMau());
    for (let i = 0; i < 70; i += 1) s.thucHien(`b${i}`, [tao.dat(s.timeline, ['clips', { id: 'c_1' }, 'bat_dau'], i + 1)]);
    const ngan = JSON.parse(JSON.stringify(s.ngan()));
    assert.equal(ngan.hoan_tac.length, GIOI_HAN_GHI);

    const mo = new Store(JSON.parse(JSON.stringify(s.timeline)), ngan);
    assert.equal(mo.timeline.clips[0].bat_dau, 70);
    mo.hoanTacMot();
    assert.equal(mo.timeline.clips[0].bat_dau, 69);
});

test('thay toàn bộ timeline (khôi phục phiên bản) là một lệnh hoàn tác được', () => {
    const s = new Store(tlMau());
    const moi = { ...tlMau(), phien_ban: 9, clips: [] };
    s.thayToanBo('Khôi phục', moi);
    assert.deepEqual(s.timeline.clips, []);
    assert.equal(s.timeline.phien_ban, 3, 'không đụng phien_ban — do bộ lưu quản');
    s.hoanTacMot();
    assert.equal(s.timeline.clips.length, 1);
});

test('chỉ đọc thì không sửa được', () => {
    const s = new Store(tlMau());
    s.chiDoc = true;
    assert.throws(() => s.thucHien('x', [tao.dat(s.timeline, ['tracks', { id: 'V1' }, 'an'], true)]));
});

test('đảo op hai lần ra lại chính nó', () => {
    const op = { op: 'them', path: ['clips'], vi_tri: 0, gia_tri: { id: 'x' } };
    assert.deepEqual(daoOp(daoOp(op)), op);
    const g = { clips: [] };
    apOp(g, op);
    apOp(g, daoOp(op));
    assert.deepEqual(g.clips, []);
});

test('chỗ trống trên track: dời ra sau clip bị chồng', () => {
    const tl = { clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 5, toc_do: 1 },
        { id: 'c_2', track: 'V1', bat_dau: 6, vao: 0, ra: 4, toc_do: 2 },   // 6 → 8
        { id: 'c_3', track: 'A1', bat_dau: 0, vao: 0, ra: 100, toc_do: 1 },
    ] };
    assert.equal(choTrong(tl, 'V1', 2, 1), 5);
    assert.equal(choTrong(tl, 'V1', 5, 1), 5, 'vừa khe 5–6');
    assert.equal(choTrong(tl, 'V1', 5, 2), 8, 'khe 5–6 không đủ 2s');
    assert.equal(choTrong(tl, 'V1', 20, 3), 20);
    assert.equal(thoiLuong(tl), 100);
    assert.equal(idClipMoi(tl), 'c_4');
});

// Ca DÙNG CHUNG với pytest (tests/test_editor_quy_doi.py).
import CA from './ca_quy_doi.json' with { type: 'json' };
import { hienThiNeo, neoTai, veMedia } from '../../webui/editor/store.js';

for (const ca of CA.ca) {
    test(`neo phụ đề — ${ca.ten}`, () => {
        assert.deepEqual(hienThiNeo(CA.timeline, ca.clip), ca.ket_qua);
    });
}

test('phụ đề đang hiện tại thời điểm t và đổi giờ timeline về giờ media', () => {
    const tl = JSON.parse(JSON.stringify(CA.timeline));
    tl.clips.push({ id: 's_1', track: 'S1', loai: 'phu_de', tu_media: 'm_01', t_vao: 3, t_ra: 7, text: 'a' });
    assert.deepEqual(neoTai(tl, 'phu_de', 6.5).map((x) => [x.c.id, x.clip]), [['s_1', 'c_2']]);
    assert.deepEqual(neoTai(tl, 'phu_de', 5), [], 'khoảng trống giữa hai clip');
    assert.equal(veMedia(tl, 'c_2', 7), 7, 'c_2: bat_dau 6, vao 5, tốc 2× → 5 + 1*2');
});

import { opsThemCau, opsXoaNhieu, cauCuaMedia, dongPhuDe, srtTuTimeline, opsDatGio } from '../../webui/editor/store.js';

test('thêm lô câu neo media, xuất .srt theo giờ timeline, xoá cả lô, hoàn tác', () => {
    const s = new Store(JSON.parse(JSON.stringify(CA.timeline)));
    s.thucHien('Nhập', opsThemCau(s.timeline, 'S1', 'm_01', [
        { t_vao: 1, t_ra: 2, text: 'một' }, { t_vao: 3, t_ra: 7, text: 'hai' }, { t_vao: 4.2, t_ra: 4.5, text: 'ẩn' }]));
    assert.deepEqual(cauCuaMedia(s.timeline, 'm_01').map((c) => c.text), ['một', 'hai', 'ẩn']);
    assert.deepEqual(dongPhuDe(s.timeline).map((d) => [d.c.text, d.bd]), [['một', 1], ['hai', 3], ['hai', 6], ['ẩn', null]]);
    assert.equal(srtTuTimeline(s.timeline).split('\n\n').length, 3);
    assert.ok(srtTuTimeline(s.timeline).includes('00:00:06,000 --> 00:00:07,000\nhai'));
    s.thucHien('Xoá', opsXoaNhieu(s.timeline, cauCuaMedia(s.timeline, 'm_01').map((c) => c.id)));
    assert.equal(cauCuaMedia(s.timeline, 'm_01').length, 0);
    s.hoanTacMot();
    assert.equal(cauCuaMedia(s.timeline, 'm_01').length, 3);
});

test('sửa giờ câu neo qua clip tốc 2× đổi đúng về giờ media', () => {
    const s = new Store(JSON.parse(JSON.stringify(CA.timeline)));
    s.thucHien('Nhập', opsThemCau(s.timeline, 'S1', 'm_01', [{ t_vao: 5.5, t_ra: 6, text: 'x' }]));
    const c = cauCuaMedia(s.timeline, 'm_01')[0];
    s.thucHien('Giờ', opsDatGio(s.timeline, c, 'c_2', 6.5, 7.5));
    assert.deepEqual([c.t_vao, c.t_ra], [6, 8]);
});

test('đặt vung_vao rồi hoàn tác trả về không có', () => {
    const s = new Store(tlMau());
    s.thucHien('Đặt vùng vào', [tao.dat(s.timeline, ['vung_vao'], 5)]);
    assert.equal(s.timeline.vung_vao, 5);
    s.hoanTacMot();
    assert.equal('vung_vao' in s.timeline, false);
});

import { opsXoaGon, opsChenGon, opsKhepKhoang, opsTiaToiDauPhat } from '../../webui/editor/store.js';

test('xoá gợn dồn clip sau về trước', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_2', track: 'V1', bat_dau: 3, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_3', track: 'V1', bat_dau: 6, vao: 0, ra: 2, toc_do: 1 },
    ] });
    s.thucHien('Xoá gợn', opsXoaGon(s.timeline, ['c_2']));
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_3', 4]]);
    s.hoanTacMot();
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_2', 3], ['c_3', 6]]);
});

test('khép khoảng trống track', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_2', track: 'V1', bat_dau: 3, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_3', track: 'V1', bat_dau: 6, vao: 0, ra: 2, toc_do: 1 },
    ] });
    s.thucHien('Khép tại 2.5', opsKhepKhoang(s.timeline, 'V1', 2.5));
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_2', 2], ['c_3', 5]]);
    s.hoanTacMot();
    
    s.thucHien('Khép toàn bộ', opsKhepKhoang(s.timeline, 'V1'));
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_2', 2], ['c_3', 4]]);
    s.hoanTacMot();
});

test('tỉa tới đầu phát Q/W', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_2', track: 'V1', bat_dau: 3, vao: 0, ra: 3, toc_do: 1 },
        { id: 'c_3', track: 'V1', bat_dau: 7, vao: 0, ra: 2, toc_do: 1 },
    ] });
    s.thucHien('Q không gợn', opsTiaToiDauPhat(s.timeline, ['c_2'], 4, 'truoc', false));
    assert.deepEqual(s.timeline.clips.find(x => x.id === 'c_2'), { id: 'c_2', track: 'V1', bat_dau: 4, vao: 1, ra: 3, toc_do: 1 });
    assert.equal(s.timeline.clips.find(x => x.id === 'c_3').bat_dau, 7);
    s.hoanTacMot();

    s.thucHien('Q có gợn', opsTiaToiDauPhat(s.timeline, ['c_2'], 4, 'truoc', true));
    assert.deepEqual(s.timeline.clips.find(x => x.id === 'c_2'), { id: 'c_2', track: 'V1', bat_dau: 3, vao: 1, ra: 3, toc_do: 1 });
    assert.equal(s.timeline.clips.find(x => x.id === 'c_3').bat_dau, 6);
    s.hoanTacMot();
    
    s.thucHien('W có gợn', opsTiaToiDauPhat(s.timeline, ['c_2'], 5, 'sau', true));
    assert.deepEqual(s.timeline.clips.find(x => x.id === 'c_2'), { id: 'c_2', track: 'V1', bat_dau: 3, vao: 0, ra: 2, toc_do: 1 });
    assert.equal(s.timeline.clips.find(x => x.id === 'c_3').bat_dau, 6);
    s.hoanTacMot();
});

import { moRongNhom, opsTachAm, opsChiaDeu } from '../../webui/editor/store.js';

test('moRongNhom mở rộng đúng theo liên kết', () => {
    const tl = { clips: [
        { id: 'c_1', lien_ket: 'n_1' },
        { id: 'c_2', lien_ket: 'n_1' },
        { id: 'c_3', lien_ket: 'n_2' },
        { id: 'c_4', lien_ket: 'n_2' },
        { id: 'c_5' },
    ] };
    assert.deepEqual(moRongNhom(tl, ['c_1']).sort(), ['c_1', 'c_2']);
    assert.deepEqual(moRongNhom(tl, ['c_1', 'c_3']).sort(), ['c_1', 'c_2', 'c_3', 'c_4']);
    assert.deepEqual(moRongNhom(tl, ['c_5']).sort(), ['c_5']);
    assert.deepEqual(moRongNhom(tl, ['c_2', 'c_5']).sort(), ['c_1', 'c_2', 'c_5']);
});

test('opsTachAm gán mã nhóm', () => {
    const tl = { tracks: [{ id: 'V1', loai: 'video' }, { id: 'A1', loai: 'audio' }], clips: [
        { id: 'c_1', track: 'V1', media: 'm_v', bat_dau: 0, vao: 0, ra: 5, toc_do: 1, am_luong: 1 }
    ] };
    const res = opsTachAm(tl, 'c_1');
    assert.ok(res);
    const idAudio = res.id;
    // ops array
    const themOp = res.ops.find(o => o.op === 'them' && o.path[0] === 'clips');
    const lkAudio = themOp.gia_tri.lien_ket;
    assert.ok(lkAudio);
    assert.equal(themOp.gia_tri.tach_tu, 'c_1');
    const tatAmOp = res.ops.find(o => o.op === 'dat' && o.path[2] === 'tat_am');
    assert.ok(tatAmOp.moi);
    const lkVideoOp = res.ops.find(o => o.op === 'dat' && o.path[2] === 'lien_ket');
    assert.equal(lkVideoOp.moi, lkAudio);
});

test('opsTachAm thực hiện rồi hoàn tác trả timeline như cũ', () => {
    const s = new Store({ tracks: [{ id: 'V1', loai: 'video' }, { id: 'A1', loai: 'audio' }], clips: [
        { id: 'c_1', track: 'V1', media: 'm_v', bat_dau: 0, vao: 0, ra: 5, toc_do: 1, am_luong: 1 }
    ] });
    const res = opsTachAm(s.timeline, 'c_1');
    s.thucHien('Tách âm', res.ops);
    assert.equal(s.timeline.clips.length, 2);
    assert.ok(s.timeline.clips[0].lien_ket);
    s.hoanTacMot();
    assert.equal(s.timeline.clips.length, 1);
    assert.equal('lien_ket' in s.timeline.clips[0], false);
});


test('chèn gợn đẩy clip sau ra sau', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_2', track: 'V1', bat_dau: 3, vao: 0, ra: 2, toc_do: 1 },
        { id: 'c_3', track: 'V1', bat_dau: 6, vao: 0, ra: 2, toc_do: 1 },
    ] });
    s.thucHien('Chèn gợn', opsChenGon(s.timeline, 'V1', 3, 2));
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_2', 5], ['c_3', 8]]);
    s.hoanTacMot();
    assert.deepEqual(s.timeline.clips.map(c => [c.id, c.bat_dau]), [['c_1', 0], ['c_2', 3], ['c_3', 6]]);
});


import { cssFilter, sanSang } from '../../webui/editor/hieu_ung.js';

test('Hieu ung cssFilter', async () => {
    // Đợi fetch JSON load xong
    await sanSang;
    
    assert.equal(cssFilter(null, []), 'none');
    assert.equal(cssFilter({ sang: 0, tuong_phan: 0 }, []), 'none');
    
    assert.equal(cssFilter({ sang: 10, tuong_phan: -20, bao_hoa: 50, hue: 45 }, []), 'brightness(1.1) contrast(0.8) saturate(1.5) hue-rotate(45deg)');
    assert.equal(cssFilter({ nhiet: 20 }, []), 'sepia(20%)');
    assert.equal(cssFilter({ nhiet: -20 }, []), 'hue-rotate(-10deg) saturate(1.2)');
    
    assert.ok(cssFilter(null, [{loai: 'vintage', do_manh: 100}]).includes('data:image/svg+xml'));
    assert.equal(cssFilter(null, [{loai: 'mo_hop', do_manh: 20}]), 'blur(4px)');
    
    // Test bật tắt
    assert.equal(cssFilter(null, [{loai: 'vintage', bat: false}, {loai: 'mo_hop', do_manh: 10}]), 'blur(2px)');
});


// ============================================================
// TEST CHUYỂN CẢNH (lượt 9b)
// ============================================================
import { opsThemChuyenCanh, opsXoaChuyenCanh, chuyenCanhHopLe } from '../../webui/editor/store.js';

test('opsThemChuyenCanh rồi hoàn tác', () => {
    const tl0 = {
        tracks: [{ id: 'V1', loai: 'video' }],
        clips: [
            { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
            { id: 'c_2', track: 'V1', bat_dau: 2, vao: 0, ra: 2, toc_do: 1 },
        ],
        chuyen_canh: [],
    };
    const s = new Store(JSON.parse(JSON.stringify(tl0)));
    const ops = opsThemChuyenCanh(s.timeline, 'c_1', 'c_2', 'fade', 0.5);
    s.thucHien('Thêm chuyển cảnh', ops);
    assert.equal(s.timeline.chuyen_canh.length, 1);
    assert.equal(s.timeline.chuyen_canh[0].loai, 'fade');
    assert.equal(s.timeline.chuyen_canh[0].dai, 0.5);
    // Hoàn tác → chuyển cảnh biến mất
    s.hoanTacMot();
    assert.equal(s.timeline.chuyen_canh.length, 0);
});

test('chuyenCanhHopLe bỏ khi clip dời xa, kẹp dai ≤ nửa clip ngắn', () => {
    // 2 clip kề nhau, mỗi clip dài 1s, chuyển cảnh dai=2 → phải kẹp về 0.5 (nửa clip)
    const tl = {
        tracks: [{ id: 'V1', loai: 'video' }],
        clips: [
            { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 1, toc_do: 1 },
            { id: 'c_2', track: 'V1', bat_dau: 1, vao: 0, ra: 1, toc_do: 1 },
        ],
        chuyen_canh: [{ id: 'cc_1', truoc: 'c_1', sau: 'c_2', loai: 'fade', dai: 2 }],
    };
    const hopLe = chuyenCanhHopLe(tl);
    assert.equal(hopLe.length, 1);
    assert.equal(hopLe[0].dai, 0.5, 'dai phải kẹp xuống nửa clip ngắn');

    // Clip bị dời xa → chuyển cảnh bị bỏ
    const tl2 = JSON.parse(JSON.stringify(tl));
    tl2.clips[1].bat_dau = 5;
    assert.equal(chuyenCanhHopLe(tl2).length, 0, 'Chuyển cảnh phải bị bỏ khi clip không kề');
});

test('xoá clip → chuyển cảnh tự mất qua Store.thucHien, hoàn tác → trở lại', () => {
    const tl0 = {
        tracks: [{ id: 'V1', loai: 'video' }],
        clips: [
            { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2, toc_do: 1 },
            { id: 'c_2', track: 'V1', bat_dau: 2, vao: 0, ra: 2, toc_do: 1 },
        ],
        chuyen_canh: [{ id: 'cc_1', truoc: 'c_1', sau: 'c_2', loai: 'fade', dai: 0.5 }],
    };
    const s = new Store(JSON.parse(JSON.stringify(tl0)));
    assert.equal(s.timeline.chuyen_canh.length, 1);

    // Xoá clip c_1 → chuyển cảnh phải tự mất (chuyenCanhHopLe chạy trong thucHien)
    const i = s.timeline.clips.findIndex(c => c.id === 'c_1');
    s.thucHien('Xoá clip', [{ op: 'xoa', path: ['clips'], vi_tri: i, gia_tri: JSON.parse(JSON.stringify(s.timeline.clips[i])) }]);
    assert.equal(s.timeline.chuyen_canh.length, 0, 'Chuyển cảnh phải tự mất khi xoá clip trước');

    // Hoàn tác → clip c_1 trở lại, chuyển cảnh cũng trở lại
    s.hoanTacMot();
    assert.equal(s.timeline.clips.length, 2);
    assert.equal(s.timeline.chuyen_canh.length, 1, 'Hoàn tác phải khôi phục chuyển cảnh');
    assert.equal(s.timeline.chuyen_canh[0].loai, 'fade');
});

// ============================================================
// TEST CHỮ/HÌNH (lượt 10b)
// ============================================================
import { clipChuMacDinh, clipHinhMacDinh, nhanClip, hopChuHinh, bienDoiSauKeo } from '../../webui/editor/store.js';

test('clipChuMacDinh tao dung kieu', () => {
    const c = clipChuMacDinh('c_1', 'V1', 1, 3, true);
    assert.equal(c.loai, 'chu');
    assert.equal(c.bat_dau, 1);
    assert.equal(c.ket_thuc, 4);
    assert.equal(c.noi_dung, 'Tiêu đề');
    assert.equal(c.kieu.co, 100);
});

test('clipHinhMacDinh tao dung hinh', () => {
    const c = clipHinhMacDinh('h_1', 'V1', 2, 2, 'tron');
    assert.equal(c.loai, 'hinh');
    assert.equal(c.bat_dau, 2);
    assert.equal(c.ket_thuc, 4);
    assert.equal(c.dang, 'tron');
});

test('hopChuHinh tinh hop cho chu', () => {
    const c = { loai: 'chu', bien_doi: { x: 0.5, y: 0.5, ti_le: 2, xoay: 45 } };
    const h = hopChuHinh(c, 1000, 1000, 200, 100);
    assert.equal(h.w, 200);
    assert.equal(h.h, 100);
    assert.equal(h.xoay, 45);
    assert.equal(h.cx, 500);
});

test('hopChuHinh tinh hop cho hinh', () => {
    const c = { loai: 'hinh', bien_doi: { x: 0.5, y: 0.5, ti_le: 2, rong: 0.2, cao: 0.3 } };
    const h = hopChuHinh(c, 1000, 1000);
    assert.equal(h.w, 400); // 0.2 * 1000 * 2
    assert.equal(h.h, 600); // 0.3 * 1000 * 2
});

test('bienDoiSauKeo keo doi', () => {
    const b0 = { x: 0.5, y: 0.5 };
    const m = bienDoiSauKeo(b0, 'chu', 'doi', 100, -100, 1000, 1000, true);
    assert.equal(m.x, 0.6);
    assert.equal(m.y, 0.4);
});

test('bienDoiSauKeo keo xoay', () => {
    const b0 = { xoay: 10 };
    const m = bienDoiSauKeo(b0, 'chu', 'xoay', 25, 0, 1000, 1000, false);
    assert.equal(m.xoay, 35);
});

test('bienDoiSauKeo keo ti le chu', () => {
    const b0 = { ti_le: 2 };
    const m = bienDoiSauKeo(b0, 'chu', 'br', 1.5, 0, 1000, 1000, false);
    assert.equal(m.ti_le, 3);
});

test('bienDoiSauKeo keo hinh tu do', () => {
    const b0 = { rong: 0.2, cao: 0.2, ti_le: 1, xoay: 0 };
    // Keo br (bottom-right) => dx, dy tang w, h
    const m = bienDoiSauKeo(b0, 'hinh', 'br', 50, 100, 1000, 1000, true);
    // dx = 50 => dw = 50 => drong = 100 / 1000 = 0.1 => rong_moi = 0.3
    // dy = 100 => dh = 100 => dcao = 200 / 1000 = 0.2 => cao_moi = 0.4
    assert.ok(Math.abs(m.rong - 0.3) < 1e-4);
    assert.ok(Math.abs(m.cao - 0.4) < 1e-4);
});

test('nhanClip tra ve nhan dung', () => {
    assert.equal(nhanClip({ loai: 'che_phu_de', kieu: 'mosaic' }), '▦ Che (mosaic)');
    assert.equal(nhanClip({ loai: 'chu', noi_dung: 'A\nB' }), 'A B');
    assert.equal(nhanClip({ loai: 'hinh', dang: 'sao' }), '⬠ Hình (sao)');
    assert.equal(nhanClip({ loai: 'video', media: 'm1' }, { ten: 'vid.mp4' }), 'vid.mp4');
});

test('ops cắt/tỉa cho clip không media', () => {
    const s = new Store({ tracks: [{ id: 'V1', loai: 'video' }], clips: [
        { id: 'c_1', track: 'V1', loai: 'chu', bat_dau: 0, ket_thuc: 4 }
    ] });
    
    // Tỉa clip không media -> không bị giới hạn bởi vao/ra
    const g = gioiHanTia(s.timeline, s.timeline.clips[0], 0, false);
    assert.equal(g.sanTrai, 0);
    assert.equal(g.tranPhai, Infinity);
    
    // Cắt (opsTach)
    const ops = opsTach(s.timeline, 'c_1', 2, 'c_2');
    s.thucHien('Cat', ops);
    assert.equal(s.timeline.clips.length, 2);
    assert.equal(s.timeline.clips[0].ket_thuc, 2);
    assert.equal(s.timeline.clips[1].id, 'c_2');
    assert.equal(s.timeline.clips[1].bat_dau, 2);
    assert.equal(s.timeline.clips[1].ket_thuc, 4);
    
    // opsTiaToiDauPhat (Tỉa truoc ko gon)
    s.hoanTacMot();
    const opsT = opsTiaToiDauPhat(s.timeline, ['c_1'], 1, 'truoc', false);
    s.thucHien('Tia truoc', opsT);
    assert.equal(s.timeline.clips[0].bat_dau, 1);
    assert.equal(s.timeline.clips[0].ket_thuc, 4);
    
    // opsTiaToiDauPhat (Tỉa truoc co gon)
    s.hoanTacMot();
    const opsTg = opsTiaToiDauPhat(s.timeline, ['c_1'], 1, 'truoc', true);
    s.thucHien('Tia truoc gon', opsTg);
    assert.equal(s.timeline.clips[0].bat_dau, 0); // Giu nguyen
    assert.equal(s.timeline.clips[0].ket_thuc, 3); // 4 - 1
});

import { readFileSync } from 'node:fs';

test('ca_keyframe.json - nội suy giá trị', () => {
    const txt = readFileSync(new URL('ca_keyframe.json', import.meta.url), 'utf-8');
    const ca = JSON.parse(txt);
    for (const c of ca) {
        const kq = giaTriTai(c.clip, c.duongDan, c.t);
        assert.ok(Math.abs(kq - c.kq) < 1e-6, `${c.ten}: mong ${c.kq}, nhận ${kq}`);
    }
});

test('tachKeyframes - chia đôi đúng', () => {
    const c = {
        keyframes: {
            "bien_doi.ti_le": [
                { t: 0, v: 1.0, em: 'tuyen_tinh' },
                { t: 2.0, v: 2.0, em: 'tuyen_tinh' },
                { t: 4.0, v: 4.0, em: 'tuyen_tinh' }
            ]
        }
    };
    const { kfTruoc, kfSau } = tachKeyframes(c, 1.0);
    assert.equal(kfTruoc["bien_doi.ti_le"].length, 2);
    assert.equal(kfTruoc["bien_doi.ti_le"][1].t, 1.0);
    assert.equal(kfTruoc["bien_doi.ti_le"][1].v, 1.5);
    
    assert.equal(kfSau["bien_doi.ti_le"].length, 3);
    assert.equal(kfSau["bien_doi.ti_le"][0].t, 0.0);
    assert.equal(kfSau["bien_doi.ti_le"][0].v, 1.5);
    assert.equal(kfSau["bien_doi.ti_le"][1].t, 1.0); // 2.0 - 1.0
    assert.equal(kfSau["bien_doi.ti_le"][2].t, 3.0); // 4.0 - 1.0
});

test('viTriKeyframes tra ve mang x', () => {
    const c = { bat_dau: 10, vao: 0, ra: 2, toc_do: 1, keyframes: { 'a': [{t: 0.5, v: 1}, {t: 1.5, v: 2}] } };
    assert.deepEqual(viTriKeyframes(c, 10), [5, 15]);
});

test('opsTach chia keyframes', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', media: 'm_1', bat_dau: 0, vao: 0, ra: 4, toc_do: 1, keyframes: { 'a': [{t: 1.0, v: 1}, {t: 3.0, v: 3}] } }
    ]});
    s.thucHien('Cat', opsTach(s.timeline, 'c_1', 2, 'c_2'));
    assert.equal(s.timeline.clips.length, 2);
    const [c1, c2] = s.timeline.clips;
    assert.equal(c1.keyframes['a'].length, 2);
    assert.equal(c1.keyframes['a'][1].t, 2.0);
    assert.equal(c1.keyframes['a'][1].v, 2.0); // noi suy o 2.0
    
    assert.equal(c2.keyframes['a'].length, 2);
    assert.equal(c2.keyframes['a'][0].t, 0.0);
    assert.equal(c2.keyframes['a'][0].v, 2.0);
    assert.equal(c2.keyframes['a'][1].t, 1.0); // 3.0 - 2.0 = 1.0
    assert.equal(c2.keyframes['a'][1].v, 3.0);
});

test('opsTiaToiDauPhat voi keyframes', () => {
    const s = new Store({ clips: [
        { id: 'c_1', track: 'V1', media: 'm_1', bat_dau: 0, vao: 0, ra: 4, toc_do: 1, keyframes: { 'a': [{t: 1.0, v: 1}, {t: 3.0, v: 3}] } }
    ]});
    s.thucHien('Tia Q', opsTiaToiDauPhat(s.timeline, ['c_1'], 2, 'truoc', true));
    const c = s.timeline.clips[0];
    assert.equal(c.keyframes['a'][0].t, 0);
    assert.equal(c.keyframes['a'][0].v, 2); // t_cut = 2
    assert.equal(c.keyframes['a'][1].t, 1); // 3 - 2 = 1
});

// Test menu mục cho clip (lượt 16)
import { mucMenuChoClip, opsNhanDoi } from '../../webui/editor/store.js';

test('mucMenuChoClip ẩn Tắt tiếng và Tốc độ cho hình/chữ', () => {
    const tl = { tracks: [{ id: 'V1', loai: 'video' }], clips: [
        { id: 'c_anh', track: 'V1', media: 'm_anh' },
        { id: 'c_chu', track: 'V1', loai: 'chu' },
        { id: 'c_vid', track: 'V1', media: 'm_vid' }
    ] };
    const mediaDict = {
        m_anh: { id: 'm_anh', loai: 'anh' },
        m_vid: { id: 'm_vid', loai: 'video', co_am_thanh: true }
    };
    
    const menuAnh = mucMenuChoClip(tl, mediaDict, 'c_anh', []);
    assert.equal(menuAnh.some(m => m.id === 'tieng'), false);
    assert.equal(menuAnh.some(m => m.id === 'toc'), false);
    
    const menuChu = mucMenuChoClip(tl, mediaDict, 'c_chu', []);
    assert.equal(menuChu.some(m => m.id === 'tieng'), false);
    assert.equal(menuChu.some(m => m.id === 'toc'), false);
    
    const menuVid = mucMenuChoClip(tl, mediaDict, 'c_vid', []);
    assert.equal(menuVid.some(m => m.id === 'tieng'), true);
    assert.equal(menuVid.some(m => m.id === 'toc'), true);
});

test('opsNhanDoi chèn gợn đúng vị trí sau clip', () => {
    const tl = { tracks: [{ id: 'V1', loai: 'video' }], clips: [
        { id: 'c_1', track: 'V1', bat_dau: 0, vao: 0, ra: 2 },
        { id: 'c_2', track: 'V1', bat_dau: 2, vao: 0, ra: 2 }
    ] };
    const { ops, idsMoi } = opsNhanDoi(tl, ['c_1']);
    // ops sẽ chứa lệnh dời c_2 ra xa 2 giây, và lệnh thêm clip mới tại bat_dau=2
    const pushOp = ops.find(o => o.op === 'dat' && o.path[1].id === 'c_2');
    assert.ok(pushOp);
    assert.equal(pushOp.moi, 4); // c_2 dời đến 4
    
    const addOp = ops.find(o => o.op === 'them' && o.gia_tri.id === idsMoi[0]);
    assert.ok(addOp);
    assert.equal(addOp.gia_tri.bat_dau, 2); // clone của c_1 nằm ở 2
});

test("opsChiaDeu chia đúng N phần", () => {
    const s = new Store({ clips: [
        { id: "c_1", track: "V1", media: "m_1", bat_dau: 0, vao: 0, ra: 6, toc_do: 1 }
    ]});
    const ops = opsChiaDeu(s.timeline, "c_1", 3);
    assert.ok(ops, "Có ops sinh ra");
    s.thucHien("Chia deu", ops);
    assert.equal(s.timeline.clips.length, 3, "Bị cắt thành 3 clip");
    const [c1, c2, c3] = s.timeline.clips;
    assert.equal(c1.bat_dau, 0); assert.equal(c1.ra, 2);
    assert.equal(c2.bat_dau, 2); assert.equal(c2.ra, 4);
    assert.equal(c3.bat_dau, 4); assert.equal(c3.ra, 6);
    
    s.hoanTacMot();
    assert.equal(s.timeline.clips.length, 1);
});
