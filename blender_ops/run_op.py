"""Chạy BÊN TRONG Blender (không giao diện) — mỗi lệnh 1 tiến trình, xong là thoát:

  blender --background --factory-startup --python blender_ops/run_op.py -- \
      --op bevel --in input.glb --out-dir job_dir --params '{"amount": 0.3}'

Thao tác: bevel (bo tròn cạnh), remesh (làm lưới đều), repair (sửa lỗi để in 3D), render (Cycles),
import_blend (mở file .blend -> GLB để Easy3D sửa tiếp).
Giao thức stdout giống worker AI: mỗi dòng JSON progress/done/error (Blender in log khác -> runner bỏ qua).
"""
import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from op_render import render_scene  # noqa: E402


def emit(**payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--op", required=True, choices=["bevel", "remesh", "repair", "render", "import_blend"])
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--params", default="{}")
    args = p.parse_args(argv)
    args.params = json.loads(args.params)
    return args


def load_meshes(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def scene_size(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    if not pts:
        raise ValueError("File không có lưới nào")
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return math.dist(lo, hi) or 1.0


def make_active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def merge_close(obj, dist):
    """Gộp điểm trùng (glTF tách điểm ở đường nối UV) — UV của Blender lưu theo góc mặt nên không mất."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(obj.data)
    bm.free()


def apply_modifier(obj, kind, **settings):
    make_active(obj)
    mod = obj.modifiers.new(kind.title(), kind)
    for key, value in settings.items():
        setattr(mod, key, value)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def op_bevel(objs, params, size):
    width = clamp(params.get("amount", 0.3), 0.01, 1) * size * 0.04
    segments = int(clamp(params.get("segments", 3), 1, 8))
    for o in objs:
        merge_close(o, size * 1e-5)
        # Chỉ bo các cạnh gấp khúc (> 30°) -> mặt cong vốn mượt không bị đụng tới.
        apply_modifier(o, "BEVEL", width=width, segments=segments, limit_method="ANGLE",
                       angle_limit=math.radians(30), harden_normals=True)
    return {"bevel_width": round(width, 5), "segments": segments}


def op_remesh(objs, params, size):
    detail = clamp(params.get("detail", 0.5), 0, 1)
    voxel = size * (0.04 - 0.035 * detail)  # chi tiết cao -> ô voxel nhỏ
    for o in objs:
        apply_modifier(o, "REMESH", mode="VOXEL", voxel_size=voxel, use_smooth_shade=True)
    return {"voxel_size": round(voxel, 5)}


def non_manifold(bm):
    return sum(1 for e in bm.edges if not e.is_manifold)


def op_repair(objs, params, size):
    before = after = 0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        before += non_manifold(bm)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=size * 1e-4)
        bmesh.ops.dissolve_degenerate(bm, dist=size * 1e-6, edges=bm.edges)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        after += non_manifold(bm)
        bm.to_mesh(o.data)
        bm.free()
    return {"non_manifold_before": before, "non_manifold_after": after}


def export_glb(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True)


def op_import_blend(src, out_path):
    """Mở .blend (script nhúng KHÔNG chạy: --disable-autoexec), xuất mọi vật đang hiện sang GLB.

    Giữ: lưới, vật liệu Principled BSDF + ảnh texture, xương + chuyển động, modifier đã áp.
    Mất: vật liệu node phức tạp/procedural (glTF không có), ảnh texture nằm ngoài file mà không tìm thấy.
    """
    bpy.ops.wm.open_mainfile(filepath=str(src), load_ui=False)
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.visible_get()]
    if not meshes:
        raise ValueError("File .blend không có vật thể (lưới) nào đang hiện")
    missing = [img.name for img in bpy.data.images
               if img.source == "FILE" and not img.packed_file and not Path(bpy.path.abspath(img.filepath)).exists()]
    bpy.ops.export_scene.gltf(filepath=str(out_path), export_format="GLB", use_visible=True, export_apply=True,
                              export_lights=False, export_cameras=False, export_animations=True)
    return {"objects": len(meshes), "tris": sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons),
            "missing_images": missing[:10]}


def main():
    t0 = time.perf_counter()
    try:
        args = parse_args()  # trong try: tham số hỏng cũng được báo theo giao thức
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.op == "import_blend":
            emit(type="progress", pct=20, msg="Blender đang mở file .blend...")
            stats = op_import_blend(args.src, out_dir / "mesh.glb")
            emit(type="done", stats={**stats, "op": args.op, "seconds": round(time.perf_counter() - t0, 1)})
            return
        emit(type="progress", pct=10, msg="Blender đang mở mô hình...")
        objs = load_meshes(args.src)
        size = scene_size(objs)
        if args.op == "render":
            emit(type="progress", pct=25, msg="Blender đang render (Cycles) — có thể mất vài phút...")
            stats = render_scene(args.params, out_dir / "render.png")
        else:
            emit(type="progress", pct=40, msg="Blender đang xử lý lưới...")
            stats = {"bevel": op_bevel, "remesh": op_remesh, "repair": op_repair}[args.op](objs, args.params, size)
            emit(type="progress", pct=85, msg="Đang lưu kết quả...")
            export_glb(out_dir / "mesh.glb", objs)
            stats["tris"] = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
        emit(type="done", stats={**stats, "op": args.op, "seconds": round(time.perf_counter() - t0, 1)})
    except Exception as exc:  # báo theo giao thức để runner hiện lỗi tiếng Việt
        traceback.print_exc()
        emit(type="error", code=type(exc).__name__, msg=str(exc)[:500])
        sys.exit(1)


main()
