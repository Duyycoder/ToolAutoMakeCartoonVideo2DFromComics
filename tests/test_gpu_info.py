from backend.gpu_info import parse_nvidia_smi_csv


def test_parse_single_gpu():
    out = "0, NVIDIA GeForce RTX 3060 Laptop GPU, 6144, 512\n"
    gpus = parse_nvidia_smi_csv(out)
    assert gpus == [{"index": 0, "name": "NVIDIA GeForce RTX 3060 Laptop GPU",
                     "vram_total_mb": 6144, "vram_used_mb": 512}]


def test_parse_ignores_garbage_and_na_values():
    out = "No devices were found\n1, Some GPU, [N/A], [N/A]\n"
    gpus = parse_nvidia_smi_csv(out)
    assert gpus == [{"index": 1, "name": "Some GPU", "vram_total_mb": None, "vram_used_mb": None}]


def test_parse_empty():
    assert parse_nvidia_smi_csv("") == []
