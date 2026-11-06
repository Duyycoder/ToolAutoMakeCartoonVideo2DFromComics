"""Thay thế `torchmcubes` khi không compile được trên Windows (cần CUDA toolkit + MSVC).

TripoSR gọi `torchmcubes.marching_cubes(volume, threshold)` rồi tự đổi trục [2, 1, 0].
torchmcubes trả đỉnh theo thứ tự (chiều cuối, giữa, đầu) còn PyMCubes trả (đầu, giữa, cuối)
-> đảo trục ở đây để khớp. Đảo trục là phép đối xứng nên hướng mặt có thể bị lật;
spike/postprocess kiểm tra `mesh.volume < 0` rồi `invert()` để sửa.
PyMCubes chạy CPU: chậm hơn ~1-3 s ở mc_resolution 256, chấp nhận được.
"""
import sys
import types


def marching_cubes(volume, threshold: float):
    import mcubes
    import numpy as np
    import torch

    verts, faces = mcubes.marching_cubes(volume.detach().float().cpu().numpy(), threshold)
    verts = np.ascontiguousarray(verts[:, ::-1], dtype=np.float32)
    faces = np.ascontiguousarray(faces, dtype=np.int64)
    return torch.from_numpy(verts).to(volume.device), torch.from_numpy(faces).to(volume.device)


def install_if_missing() -> str:
    """Trả về tên backend marching cubes đang dùng: 'torchmcubes' hoặc 'pymcubes'."""
    try:
        import torchmcubes  # noqa: F401
        return "torchmcubes"
    except ImportError:
        shim = types.ModuleType("torchmcubes")
        shim.marching_cubes = marching_cubes
        sys.modules["torchmcubes"] = shim
        return "pymcubes"
