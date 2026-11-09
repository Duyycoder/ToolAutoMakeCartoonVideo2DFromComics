"""Xuất cảnh đã import sang FBX cho Unity (texture nhúng, xương, chuyển động).

FBX không chứa được map Metallic-Roughness của glTF -> lưu riêng thành PNG theo chuẩn Unity Lit
(R = Metallic, A = Smoothness) để gán tay trong Unity.
"""
import math

import bpy
import numpy as np


def trace_to_image(socket):
    """Lần ngược từ input của Principled tới ảnh. Trả về (image, kênh, hệ số nhân) hoặc None."""
    channel, factor = None, 1.0
    while socket.is_linked:
        link = socket.links[0]
        node = link.from_node
        if node.type == "TEX_IMAGE":
            return (node.image, channel, factor) if node.image and channel is not None else None
        if node.type == "SEPARATE_COLOR":
            channel = ("Red", "Green", "Blue").index(link.from_socket.name)
            socket = node.inputs[0]
        elif node.type == "MATH" and node.operation == "MULTIPLY":
            linked = [s for s in node.inputs[:2] if s.is_linked]
            if len(linked) != 1:
                return None
            constant = next(s for s in node.inputs[:2] if not s.is_linked)
            factor *= constant.default_value
            socket = linked[0]
        else:
            return None
    return None


def principled_of(material):
    if not material.use_nodes:
        return None
    return next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def read_channel(traced):
    """(rộng, cao, giá trị 1 kênh theo từng pixel), hoặc None nếu input không nối với ảnh."""
    if traced is None:
        return None
    image, channel, factor = traced
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return width, height, np.clip(pixels[channel::4] * factor, 0, 1)


def save_metallic_smoothness(metal, rough, metal_default, rough_default, path):
    """Ghép 2 kênh thành PNG Unity: R = Metallic, A = 1 - Roughness."""
    width, height, _ = metal or rough
    count = width * height
    metal_values = metal[2] if metal and metal[0] == width and metal[1] == height else np.full(count, metal_default)
    rough_values = rough[2] if rough and rough[0] == width and rough[1] == height else np.full(count, rough_default)
    pixels = np.zeros(count * 4, dtype=np.float32)
    pixels[0::4] = pixels[1::4] = pixels[2::4] = metal_values
    pixels[3::4] = 1 - rough_values
    image = bpy.data.images.new("metallic_smoothness", width, height, alpha=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set(pixels)
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def write_metallic_maps(out_dir):
    """Mỗi material có map -> metallic-smoothness-<i>.png. Trả về tên các material đó, theo thứ tự <i>."""
    saved = []
    for material in list(bpy.data.materials):
        bsdf = principled_of(material)
        if bsdf is None:
            continue
        metal_input, rough_input = bsdf.inputs["Metallic"], bsdf.inputs["Roughness"]
        if not (metal_input.is_linked or rough_input.is_linked):
            continue
        metal = read_channel(trace_to_image(metal_input))
        rough = read_channel(trace_to_image(rough_input))
        if metal or rough:
            save_metallic_smoothness(metal, rough, metal_input.default_value, rough_input.default_value,
                                     out_dir / f"metallic-smoothness-{len(saved)}.png")
            saved.append(material.name)
    return saved


def unmix_base_color():
    """Màu tint khiến glTF importer chèn node MIX, FBX exporter không lần qua được nên mất texture.

    Nối thẳng ảnh vào Base Color để giữ texture, bỏ tint. Trả về số material bị bỏ tint.
    """
    dropped = 0
    for material in bpy.data.materials:
        bsdf = principled_of(material)
        if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
            continue
        mix = bsdf.inputs["Base Color"].links[0].from_node
        if mix.type not in ("MIX", "MIX_RGB"):
            continue
        image_node = next((s.links[0].from_node for s in mix.inputs
                           if s.is_linked and s.links[0].from_node.type == "TEX_IMAGE"), None)
        if image_node:
            material.node_tree.links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
            dropped += 1
    return dropped


def fit_timeline_to_actions():
    """Chỉnh timeline khớp chuyển động (mặc định 1-250 làm clip dài thừa). Trả về số frame, 0 nếu không có."""
    if not bpy.data.actions:
        return 0
    start = math.floor(min(a.frame_range[0] for a in bpy.data.actions))
    end = math.ceil(max(a.frame_range[1] for a in bpy.data.actions))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, max(end, start + 1)
    return scene.frame_end - scene.frame_start + 1


def images_kept_by_fbx():
    """Ảnh FBX tham chiếu được; ảnh chỉ đi vào SEPARATE_COLOR là Metallic-Roughness, đã đổi thành map riêng."""
    kept = []
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image and node.image.packed_file and node.image not in kept \
                    and any(link.to_node.type != "SEPARATE_COLOR" for output in node.outputs for link in output.links):
                kept.append(node.image)
    return kept


def write_textures(out_dir):
    """Ghi ảnh ra file cạnh FBX -> Unity tự gán theo tên, không cần bấm Extract Textures.

    Tên file do mình đặt (texture_<i>): tên ảnh trong GLB do client gửi nên không dùng làm đường dẫn.
    """
    names = []
    for index, image in enumerate(images_kept_by_fbx()):
        extension = ".jpg" if image.packed_file.data[:2] == b"\xff\xd8" else ".png"
        path = out_dir / f"texture_{index}{extension}"
        path.write_bytes(image.packed_file.data)
        image.filepath_raw = path.name
        names.append(path.name)
    return names


def export_fbx(objs, out_dir):
    maps = write_metallic_maps(out_dir)
    tint_dropped = unmix_base_color()
    frames = fit_timeline_to_actions()
    textures = write_textures(out_dir)
    bpy.ops.export_scene.fbx(
        filepath=str(out_dir / "model.fbx"), path_mode="STRIP",
        axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_ALL",
        object_types={"ARMATURE", "MESH"}, mesh_smooth_type="FACE", add_leaf_bones=False,
        bake_space_transform=True,  # Unity: vật không bị xoay -90° (đã kiểm tra: lưới, xương, clip không đổi)
        bake_anim=frames > 0, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
    )
    return {"objects": len(objs), "tris": sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons),
            "armatures": sum(o.type == "ARMATURE" for o in bpy.context.scene.objects),
            "anim_frames": frames, "metallic_maps": maps, "tint_dropped": tint_dropped, "textures": textures}
