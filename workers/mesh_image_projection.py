"""Đặt mesh đúng hướng theo ảnh gốc rồi tô màu đỉnh bằng cách chiếu ảnh lên (CPU, numpy/PIL/trimesh).

Model tạo hình (Hunyuan3D) chỉ ra HÌNH, không có màu; quy ước trục cũng có thể khác glTF.
Cách làm: thử 24 hướng xoay vuông góc, chiếu hình bóng nhìn từ +Z, so IoU với vùng có vật
trong ảnh -> chọn hướng khớp nhất (đầu hướng +Y, mặt trước hướng +Z như viewport Easy3D).
Sau đó chiếu ảnh theo trục Z lên MỌI đỉnh (mặt sau nhận màu đối xứng của mặt trước) — người dùng
sửa thêm bằng chế độ "Tô vẽ" trong app.
"""
from itertools import permutations, product

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MASK_SIZE = 96
MAX_FACES_FOR_SILHOUETTE = 6000


def axis_rotations() -> list[np.ndarray]:
    """24 ma trận xoay biến trục thành trục (det = +1). Thứ tự: giữ nguyên trước, rồi các hướng giữ +Y."""
    mats = []
    for perm in permutations(range(3)):
        for signs in product((1, -1), repeat=3):
            m = np.zeros((3, 3))
            for row, (col, sign) in enumerate(zip(perm, signs)):
                m[row, col] = sign
            if np.isclose(np.linalg.det(m), 1):
                mats.append(m)
    # Ưu tiên khi hoà điểm: đơn vị, rồi những hướng giữ trục Y (quy ước glTF phổ biến nhất).
    mats.sort(key=lambda m: (not np.allclose(m, np.eye(3)), not np.allclose(m[1], [0, 1, 0])))
    return mats


def _fit_square(points_xy: np.ndarray, size: int) -> np.ndarray:
    """Đưa điểm 2D vào ô vuông size×size, giữ tỉ lệ, căn giữa (trục y hướng xuống như ảnh)."""
    mn, mx = points_xy.min(0), points_xy.max(0)
    span = max((mx - mn).max(), 1e-9)
    p = (points_xy - (mn + mx) / 2) / span * (size - 4) + size / 2
    p[:, 1] = size - p[:, 1]
    return p


def silhouette(vertices: np.ndarray, faces: np.ndarray, size: int = MASK_SIZE) -> np.ndarray:
    """Hình bóng nhìn từ +Z (x sang phải, y lên trên) — chỉ vẽ một phần mặt để nhanh."""
    if len(faces) > MAX_FACES_FOR_SILHOUETTE:
        faces = faces[np.random.default_rng(0).choice(len(faces), MAX_FACES_FOR_SILHOUETTE, replace=False)]
    p = _fit_square(vertices[:, :2], size)
    img = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(img)
    for f in faces:
        draw.polygon([tuple(p[i]) for i in f], fill=255, outline=255)
    return np.asarray(img) > 127


def image_mask(rgba: Image.Image, size: int = MASK_SIZE) -> np.ndarray:
    """Vùng có vật trong ảnh (alpha), đưa về cùng khung chuẩn như silhouette()."""
    alpha = np.asarray(rgba.getchannel('A')) > 127
    ys, xs = np.nonzero(alpha)
    if not len(xs):
        raise ValueError('Ảnh không có vật (đã tách nền nhưng trống)')
    pts = np.stack([xs, alpha.shape[0] - ys], axis=1).astype(float)  # y lên trên như silhouette
    p = _fit_square(pts, size).astype(int).clip(0, size - 1)
    mask = np.zeros((size, size), bool)
    mask[p[:, 1], p[:, 0]] = True
    # MaxFilter: lấp lỗ do lấy mẫu điểm ảnh thưa
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 127


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def best_rotation(vertices: np.ndarray, faces: np.ndarray, rgba: Image.Image) -> tuple[np.ndarray, float]:
    target = image_mask(rgba)
    best, best_score = np.eye(3), -1.0
    for m in axis_rotations():
        score = iou(silhouette(vertices @ m.T, faces), target)
        if score > best_score + 1e-3:  # hoà điểm -> giữ hướng ưu tiên đứng trước
            best, best_score = m, score
    return best, best_score


def project_colors(vertices: np.ndarray, rgba: Image.Image) -> np.ndarray:
    """Màu RGBA uint8 cho từng đỉnh: chiếu ảnh (khung bao vật) theo trục Z, kéo giãn theo khung bao mesh."""
    arr = np.asarray(rgba.convert('RGBA'))
    alpha = arr[..., 3] > 127
    ys, xs = np.nonzero(alpha)
    crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float)
    inside = crop[..., 3] > 127
    mean = crop[inside][:, :3].mean(0)
    crop[~inside, :3] = mean  # mép lệch nhẹ giữa hình và ảnh -> lấy màu trung bình thay vì nền
    h, w = inside.shape
    mn, mx = vertices.min(0), vertices.max(0)
    span = np.maximum(mx - mn, 1e-9)
    u = ((vertices[:, 0] - mn[0]) / span[0] * (w - 1)).round().astype(int).clip(0, w - 1)
    v = ((mx[1] - vertices[:, 1]) / span[1] * (h - 1)).round().astype(int).clip(0, h - 1)
    colors = np.empty((len(vertices), 4), np.uint8)
    colors[:, :3] = crop[v, u, :3].astype(np.uint8)
    colors[:, 3] = 255
    return colors


def orient_and_colorize(mesh, rgba: Image.Image) -> dict:
    """Xoay trimesh.Trimesh tại chỗ + gán màu đỉnh. Trả về thông tin để ghi log."""
    m, score = best_rotation(np.asarray(mesh.vertices), np.asarray(mesh.faces), rgba)
    t = np.eye(4)
    t[:3, :3] = m
    mesh.apply_transform(t)
    mesh.visual.vertex_colors = project_colors(np.asarray(mesh.vertices), rgba)
    return {'orientation_iou': round(score, 3), 'rotation': m.astype(int).tolist()}
