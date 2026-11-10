"""Bake màu đỉnh thành ảnh texture cho FBX.

Lưới AI tô màu bằng màu đỉnh (COLOR_0); Unity (shader Standard/Lit) không hiển thị màu đỉnh nên vào Unity mất màu.
Easy3D đã bỏ COLOR_0 ở vật không dùng màu đỉnh trước khi gửi -> còn COLOR_0 nghĩa là màu đang hiện, cần bake.
"""
import bpy

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


def ensure_uv(obj):
    """Lưới AI không có UV -> trải UV tự động để có chỗ bake."""
    if obj.data.uv_layers:
        return
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # Lưới AI nhiễu: smart_project cắt ra hàng chục nghìn island, margin nuốt hết ảnh. Lightmap xếp đều mọi mặt.
    bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_MARGIN_DIV=0.05)
    bpy.ops.object.mode_set(mode="OBJECT")


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
