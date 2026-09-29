// Shim tối thiểu của `node:assert/strict` (chỉ những hàm tests/js dùng).
class LoiAssert extends Error {}

function bang(a, b) {
    if (Object.is(a, b)) return true;
    if (typeof a !== 'object' || typeof b !== 'object' || !a || !b) return false;
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    const ka = Object.keys(a), kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => bang(a[k], b[k]));
}

const assert = {
    equal(a, b, msg) { if (!Object.is(a, b)) throw new LoiAssert(msg || `${JSON.stringify(a)} !== ${JSON.stringify(b)}`); },
    deepEqual(a, b, msg) { if (!bang(a, b)) throw new LoiAssert(msg || `${JSON.stringify(a)} khác ${JSON.stringify(b)}`); },
    ok(v, msg) { if (!v) throw new LoiAssert(msg || `${v} không truthy`); },
    throws(fn, msg) {
        try { fn(); } catch (e) { return; }
        throw new LoiAssert(msg || 'Không ném lỗi');
    },
};
export default assert;
