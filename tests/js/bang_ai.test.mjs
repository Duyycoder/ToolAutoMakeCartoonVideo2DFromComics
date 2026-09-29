import test from 'node:test';
import assert from 'node:assert';
import { moTaUpscale, tinhCoAnhMacDinh } from '../../webui/editor/bang_ai.js';

test('moTaUpscale - cảnh báo khi nguồn đã >= đích', () => {
    const res = moTaUpscale('ai', 1920, 1080, '720p (HD)');
    assert.ok(res.includes('⚠️ Video đã đủ lớn, phóng to không có ích.'), 'Phải có cảnh báo');
    assert.ok(res.includes('AI (RealESRGAN anime)'), 'Phải nói về anime');
    assert.ok(res.includes('mất chi tiết nhỏ'), 'Cảnh báo về anime');
});

test('moTaUpscale - không cảnh báo khi đích lớn hơn', () => {
    const res = moTaUpscale('ai_video', 640, 480, '1080p (Full HD)');
    assert.ok(!res.includes('⚠️ Video đã đủ lớn'), 'Không có cảnh báo');
    assert.ok(res.includes('AI vẽ lại nét viền'), 'Mô tả ai_video');
    assert.ok(!res.includes('mất chi tiết nhỏ'), 'ai_video không có cảnh báo anime bệt');
});

test('moTaUpscale - không cảnh báo khi độ phân giải gốc', () => {
    const res = moTaUpscale('nhanh', 1920, 1080, 'Gốc');
    assert.ok(!res.includes('⚠️ Video đã đủ lớn'), 'Không có cảnh báo');
    assert.ok(res.includes('co giãn thường'), 'Mô tả co giãn nhanh');
});

test('tinhCoAnhMacDinh - thu về tối đa 1024, giữ tỉ lệ và bội 8', () => {
    const thieu = tinhCoAnhMacDinh(0, 0);
    assert.deepStrictEqual(thieu, { r: 1024, c: 1024 });

    const nho = tinhCoAnhMacDinh(800, 600);
    assert.deepStrictEqual(nho, { r: 800, c: 600 });
    
    const vua = tinhCoAnhMacDinh(500, 500);
    assert.deepStrictEqual(vua, { r: 504, c: 504 }); // 500/8 = 62.5 -> 63*8 = 504

    const toNgang = tinhCoAnhMacDinh(1920, 1080);
    // 1920, 1080 -> 1024 / 1920 = 0.5333... -> r=1024, c=576
    assert.deepStrictEqual(toNgang, { r: 1024, c: 576 });
    
    const toDoc = tinhCoAnhMacDinh(1080, 1920);
    assert.deepStrictEqual(toDoc, { r: 576, c: 1024 });
});

import { opsChenAnhAi } from '../../webui/editor/bang_ai.js';

test('opsChenAnhAi - tìm khe trống và tạo lệnh thêm clip đúng', () => {
    const tl = {
        clips: [
            { track: 'V1', bat_dau: 0, vao: 0, ra: 2 }, // 0-2
            { track: 'V1', bat_dau: 4, vao: 0, ra: 2 }  // 4-6
        ],
        _idCount: 1
    };
    // dauPhat = 1, thoiLuong = 3
    // Khe trống tiếp theo sau 1 mà chứa được 3s là đoạn sau 6s (vì đoạn 2-4 chỉ có 2s).
    const ops = opsChenAnhAi(tl, 'V1', 'm_123', 1, 3.0);
    assert.strictEqual(ops.length, 1);
    assert.strictEqual(ops[0].op, 'them');
    assert.strictEqual(ops[0].path[0], 'clips');
    assert.strictEqual(ops[0].gia_tri.track, 'V1');
    assert.strictEqual(ops[0].gia_tri.media, 'm_123');
    assert.strictEqual(ops[0].gia_tri.bat_dau, 6);
    assert.strictEqual(ops[0].gia_tri.ra, 3.0);
});


import { layModelWhisperMacDinh } from '../../webui/editor/bang_ai.js';
test('layModelWhisperMacDinh - PhoWhisper cho tiếng Việt', () => {
    assert.strictEqual(layModelWhisperMacDinh('Vietnamese'), 'qbsmlabs/PhoWhisper-small');
    assert.strictEqual(layModelWhisperMacDinh('Chinese'), 'medium');
    assert.strictEqual(layModelWhisperMacDinh('English'), 'medium');
});
