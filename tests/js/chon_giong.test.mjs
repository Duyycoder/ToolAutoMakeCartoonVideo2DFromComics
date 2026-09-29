import { taoTtsVoice, layGiongMacDinh } from '../../webui/editor/chon_giong.js';
import assert from 'assert';

try {
    // vieneu
    assert.strictEqual(taoTtsVoice('vieneu', 'Thái Sơn', 'standard'), 'Thái Sơn|standard');
    assert.strictEqual(taoTtsVoice('vieneu', null, null), 'Ngọc Lan|v3turbo');

    // clone
    assert.strictEqual(taoTtsVoice('clone', '', '', true, 'C:\\abc.wav'), 'auto');
    assert.strictEqual(taoTtsVoice('clone', '', '', false, 'C:\\abc.wav'), 'C:\\abc.wav');

    // kokoro / edge
    assert.strictEqual(taoTtsVoice('kokoro', 'diem_trinh'), 'diem_trinh');
    assert.strictEqual(taoTtsVoice('edge', 'vi-VN-NamMinhNeural'), 'vi-VN-NamMinhNeural');

    // test layGiongMacDinh
    const dsGiongEdge = ['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural'];
    assert.strictEqual(layGiongMacDinh('edge', 'vi-VN-NamMinhNeural', dsGiongEdge), 'vi-VN-NamMinhNeural'); // hợp lệ
    assert.strictEqual(layGiongMacDinh('edge', 'diem_trinh', dsGiongEdge), 'vi-VN-HoaiMyNeural'); // không hợp lệ -> lấy đầu ds
    
    const dsGiongKokoro = ['diem_trinh', 'ngoc_lan'];
    assert.strictEqual(layGiongMacDinh('kokoro', 'ngoc_lan', dsGiongKokoro), 'ngoc_lan');
    assert.strictEqual(layGiongMacDinh('kokoro', 'vi-VN-HoaiMyNeural', dsGiongKokoro), 'diem_trinh');

    assert.strictEqual(layGiongMacDinh('vieneu', 'Thái Sơn|standard', ['Thái Sơn', 'Ngọc Lan']), 'Thái Sơn|standard');
    assert.strictEqual(layGiongMacDinh('vieneu', 'diem_trinh', ['Thái Sơn', 'Ngọc Lan']), 'Thái Sơn|v3turbo');
    
    assert.strictEqual(layGiongMacDinh('clone', 'C:\\abc.wav', []), 'C:\\abc.wav');
    assert.strictEqual(layGiongMacDinh('clone', '', []), 'auto');

    console.log('OK: chon_giong.test.mjs');
} catch (e) {
    console.error('FAIL: chon_giong.test.mjs', e);
    process.exit(1); // will fail the browser test runner if it captures
}
