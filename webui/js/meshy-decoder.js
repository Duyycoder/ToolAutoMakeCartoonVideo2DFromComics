// Cấu trúc Meshy v1: https://github.com/Amal-David/meshy2glb/blob/main/NOTES.md
const HEADER_BYTES = 32;
const ENCRYPTED_BYTES = 8192;
const TAG_BYTES = 16;
const TAIL_OFFSET = HEADER_BYTES + ENCRYPTED_BYTES + TAG_BYTES;
const FORMAT_KEY = 'JSON{"accessors":[{"bufferView":';

/** Khôi phục GLB trong bộ nhớ để dùng chung bộ đọc glTF của Easy3D. */
export async function decodeMeshyFile(buffer) {
  const bytes = new Uint8Array(buffer);
  if (bytes.length < TAIL_OFFSET || new TextDecoder().decode(bytes.subarray(0, 8)) !== 'MESHY.AI') {
    throw new Error('File Meshy không hợp lệ hoặc bị thiếu dữ liệu.');
  }
  const version = new DataView(buffer).getUint16(8, true);
  if (version !== 1) throw new Error(`Chưa hỗ trợ Meshy phiên bản ${version}.`);

  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('Để mở file Meshy, hãy dùng ứng dụng Easy3D hoặc mở qua localhost/HTTPS.');
  const key = await subtle.importKey('raw', new TextEncoder().encode(FORMAT_KEY), 'AES-GCM', false, ['decrypt']);
  const algorithm = { name: 'AES-GCM', iv: bytes.subarray(10, 22) };
  let prefix;
  try {
    prefix = await subtle.decrypt(algorithm, key, bytes.subarray(HEADER_BYTES, TAIL_OFFSET));
  } catch {
    throw new Error('Không xác thực được phần đầu file Meshy. File có thể bị hỏng.');
  }

  const tail = bytes.subarray(TAIL_OFFSET);
  const glbLength = prefix.byteLength + tail.byteLength;
  const header = new DataView(prefix);
  if (header.getUint32(0, true) !== 0x46546c67 || header.getUint32(4, true) !== 2
      || header.getUint32(8, true) !== glbLength) {
    throw new Error('Dữ liệu GLB trong file Meshy không hợp lệ.');
  }
  const glb = new Uint8Array(glbLength);
  glb.set(new Uint8Array(prefix));
  glb.set(tail, prefix.byteLength);

  // Phần đuôi được lưu nguyên dạng. Kiểm tra biên của từng chunk trước khi đọc.
  const view = new DataView(glb.buffer);
  if (view.getUint32(16, true) !== 0x4e4f534a) throw new Error('File Meshy thiếu chunk JSON của GLB.');
  for (let offset = 12; offset < glbLength;) {
    if (offset + 8 > glbLength) throw new Error('Chunk GLB trong file Meshy bị thiếu dữ liệu.');
    const size = view.getUint32(offset, true);
    offset += 8 + size;
    if (size % 4 || offset > glbLength) throw new Error('Kích thước chunk GLB trong file Meshy không hợp lệ.');
  }
  return glb.buffer;
}
