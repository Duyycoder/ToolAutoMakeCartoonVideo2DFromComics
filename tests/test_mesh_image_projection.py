"""Dò hướng + chiếu màu cho mesh của Hunyuan3D. Cần numpy/Pillow/trimesh (có trong .venv-ai / .venv-hunyuan)."""
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
trimesh = pytest.importorskip("trimesh")
Image = pytest.importorskip("PIL.Image")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "workers"))
from mesh_image_projection import axis_rotations, best_rotation, orient_and_colorize, silhouette  # noqa: E402


def l_shape():
    """Chữ L bất đối xứng (đứng thẳng theo +Y, mặt trước +Z) — đủ để phân biệt mọi hướng xoay."""
    tall = trimesh.creation.box(extents=(0.4, 2.0, 0.3))
    tall.apply_translation((-0.6, 1.0, 0))
    foot = trimesh.creation.box(extents=(1.6, 0.4, 0.3))
    foot.apply_translation((0, 0.2, 0))
    return trimesh.util.concatenate([tall, foot])


def front_image(mesh, left_rgb=(255, 0, 0), right_rgb=(0, 0, 255)):
    """'Ảnh gốc' giả: hình bóng nhìn từ +Z, nửa trái đỏ, nửa phải xanh, nền trong suốt."""
    mask = silhouette(np.asarray(mesh.vertices), np.asarray(mesh.faces), size=128)
    arr = np.zeros((128, 128, 4), np.uint8)
    arr[mask, 3] = 255
    arr[:, :64][mask[:, :64], :3] = left_rgb
    arr[:, 64:][mask[:, 64:], :3] = right_rgb
    return Image.fromarray(arr, "RGBA")


def test_24_unique_rotations():
    mats = axis_rotations()
    assert len(mats) == 24
    assert np.allclose(mats[0], np.eye(3))
    assert len({m.astype(int).tobytes() for m in mats}) == 24


@pytest.mark.parametrize("wrong", [1, 5, 13, 20])
def test_recovers_orientation_from_image(wrong):
    upright = l_shape()
    image = front_image(upright)
    tilted = upright.copy()
    t = np.eye(4)
    t[:3, :3] = axis_rotations()[wrong].T  # model trả về sai hướng
    tilted.apply_transform(t)
    m, score = best_rotation(np.asarray(tilted.vertices), np.asarray(tilted.faces), image)
    assert score > 0.8
    assert np.allclose(np.asarray(tilted.vertices) @ m.T, np.asarray(upright.vertices), atol=1e-6)


def test_colors_follow_image_left_right():
    mesh = l_shape()
    info = orient_and_colorize(mesh, front_image(mesh))
    colors = np.asarray(mesh.visual.vertex_colors)
    x = np.asarray(mesh.vertices)[:, 0]
    left, right = colors[x < x.min() + 0.2], colors[x > x.max() - 0.2]
    assert info["orientation_iou"] > 0.8
    assert (left[:, 0] > 200).all() and (left[:, 2] < 60).all(), "bên trái phải đỏ"
    assert (right[:, 2] > 200).all() and (right[:, 0] < 60).all(), "bên phải phải xanh"
