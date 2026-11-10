"""Bake màu đỉnh thành ảnh texture cho FBX.

Lưới AI tô màu bằng màu đỉnh (COLOR_0); Unity (shader Standard/Lit) không hiển thị màu đỉnh nên vào Unity mất màu.
Easy3D đã bỏ COLOR_0 ở vật không dùng màu đỉnh trước khi gửi -> còn COLOR_0 nghĩa là màu đang hiện, cần bake.
"""
import bmesh
import bpy
import numpy as np

BAKE_SIZE = 2048


def needs_bake(material):
    """Base Color lấy từ màu đỉnh (trực tiếp hoặc qua MIX nhân với màu), không có ảnh."""
    bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if material.use_nodes else None
    if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
        return False
    node = bsdf.inputs["Base Color"].links[0].from_node
    nodes = [node]
    if node.type in ("MIX", "MIX_RGB"):
        nodes += [s.links[0].from_node for s in node.inputs if s.is_linked]
    types = {n.type for n in nodes}
    return "VERTEX_COLOR" in types and "TEX_IMAGE" not in types


def smooth_face_normals(mesh, rounds=4):
    """Pháp tuyến mặt đã làm mượt qua các đỉnh: mặt lưới AI lởm chởm (bậc thang), pháp tuyến thô nhảy lung tung."""
    count = len(mesh.polygons)
    faces = np.empty(count * 3, dtype=np.int64)
    mesh.polygons.foreach_get("vertices", faces)  # lưới glTF luôn là tam giác
    faces = faces.reshape(-1, 3)
    normals = np.empty(count * 3)
    mesh.polygons.foreach_get("normal", normals)
    normals = normals.reshape(-1, 3)
    for _ in range(rounds):
        per_vertex = np.zeros((len(mesh.vertices), 3))
        for corner in range(3):
            np.add.at(per_vertex, faces[:, corner], normals)
        normals = per_vertex[faces].sum(axis=1)
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
    return faces, normals


def box_unwrap(obj):
    """Chiếu phẳng mỗi mặt theo 1 trong 6 hướng ±X/±Y/±Z -> mặt liền nhau cùng hướng thành 1 mảng lớn liền mạch.

    smart_project/lightmap cắt lưới AI thành hàng chục nghìn mảnh 1 tam giác; Unity nén texture theo khối 4x4
    và mipmap trộn các mảnh không liên quan -> noise. Mảng lớn thì pixel cạnh nhau là điểm cạnh nhau trên bề mặt.
    """
    mesh = obj.data
    # GLB từ three.js thường không dùng chung đỉnh (mỗi tam giác 3 đỉnh riêng) -> mọi mặt rời nhau. Gộp đỉnh trùng.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(mesh)
    bm.free()
    faces, normals = smooth_face_normals(mesh)
    axis = np.abs(normals).argmax(axis=1)
    sign = np.sign(normals[np.arange(len(axis)), axis])
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    corners = co.reshape(-1, 3)[faces]  # (mặt, 3 góc, xyz)
    u_axis, v_axis = np.array([1, 0, 0])[axis], np.array([2, 2, 1])[axis]  # X->(y,z) Y->(x,z) Z->(x,y)
    u = np.take_along_axis(corners, u_axis[:, None, None], axis=2)[..., 0]
    v = np.take_along_axis(corners, v_axis[:, None, None], axis=2)[..., 0]
    uv = np.stack([u * sign[:, None], v], axis=-1)  # hướng âm lật u: mặt trước/sau cùng trục không đè nhau
    layer = mesh.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=0.003, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def ensure_uv(obj):
    """Lưới AI không có UV -> trải UV tự động để có chỗ bake."""
    if not obj.data.uv_layers:
        box_unwrap(obj)


def bake_vertex_colors(objs):
    """Mỗi vật cần bake -> 1 ảnh (đã pack để write_textures ghi ra cạnh FBX). Trả về số vật đã bake."""
    targets = [o for o in objs if o.data.color_attributes
               and any(s.material and needs_bake(s.material) for s in o.material_slots)]
    if not targets:
        return 0
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    for obj in targets:
        for other in scene.objects:
            other.select_set(other == obj)
        ensure_uv(obj)
        image = bpy.data.images.new(f"{obj.name}_color", BAKE_SIZE, BAKE_SIZE)
        baked = []
        for slot in obj.material_slots:
            if not (slot.material and needs_bake(slot.material)):
                continue
            if slot.material.users > 1:  # dùng chung với vật khác -> tách riêng để ảnh không đè nhau
                slot.material = slot.material.copy()
            tree = slot.material.node_tree
            node = tree.nodes.new("ShaderNodeTexImage")
            node.image = image
            tree.nodes.active = node
            baked.append((slot.material, node))
        # EXTEND: mỗi tam giác lightmap là 1 island, kiểu margin mặc định (theo mặt kề) để lại khe đen
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8, margin_type="EXTEND", use_clear=True)
        for material, node in baked:
            bsdf = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            material.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        image.pack()
    return len(targets)
