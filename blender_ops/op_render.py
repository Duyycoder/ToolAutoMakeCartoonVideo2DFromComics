"""Render đẹp bằng Cycles: camera + ánh sáng lấy từ khung nhìn Easy3D, sàn nhận bóng (shadow catcher).

Toạ độ: Easy3D/three.js Y-up -> Blender Z-up theo đúng quy ước của bộ nhập glTF: (x, y, z) -> (x, -z, y).
"""
import math

import bpy
from mathutils import Vector


def to_blender(v):
    x, y, z = v
    return Vector((x, -z, y))


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(hex_color):
    h = hex_color.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def use_gpu_if_possible(scene):
    """OPTIX/CUDA (NVIDIA) hoặc HIP (AMD) nếu có, không thì CPU. Trả về tên thiết bị."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except TypeError:
            continue
        devices = [d for d in prefs.devices if d.type == kind]
        if devices:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            return kind
    scene.cycles.device = "CPU"
    return "CPU"


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_scene(params, out_path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(max(8, min(1024, params.get("samples", 96))))
    scene.cycles.use_denoising = True
    device = use_gpu_if_possible(scene)
    scene.render.resolution_x = int(params.get("width", 1920))
    scene.render.resolution_y = int(params.get("height", 1080))
    scene.render.resolution_percentage = 100
    # LUÔN nền trong suốt: shadow catcher chỉ ghi bóng đổ khi film trong suốt; app tự lót màu nền nếu cần.
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = math.log2(float(params.get("exposure", 1.0)))  # cùng "Độ phơi sáng" trong app

    cam_data = bpy.data.cameras.new("Easy3DCamera")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.angle_y = math.radians(params.get("fov", 45))
    cam = bpy.data.objects.new("Easy3DCamera", cam_data)
    scene.collection.objects.link(cam)
    cam.location = to_blender(params["camera_position"])
    look_at(cam, to_blender(params["camera_target"]))
    scene.camera = cam

    world = bpy.data.worlds.new("Easy3DWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    # Ánh sáng môi trường theo MÀU TRỜI (như HemisphereLight trong app), không theo màu nền: nền tối (Studio)
    # trước đây làm ảnh Cycles tối hơn hẳn khung nhìn. Ảnh luôn nền trong suốt, app tự lót màu nền.
    bg.inputs[0].default_value = (*hex_to_linear(params.get("sky", "#ffffff")), 1)
    bg.inputs[1].default_value = float(params.get("ambient", 1.0))
    scene.world = world

    sun_data = bpy.data.lights.new("Easy3DSun", "SUN")
    sun_data.energy = float(params.get("sun_intensity", 2.0)) * 1.6
    sun_data.color = hex_to_linear(params.get("sun_color", "#ffffff"))
    sun_data.angle = math.radians(3)  # bóng hơi mềm như trong app
    sun_data.use_shadow = bool(params.get("sun_shadows", True))
    sun = bpy.data.objects.new("Easy3DSun", sun_data)
    scene.collection.objects.link(sun)
    sun.location = to_blender(params.get("sun_position", (5, 8, 4)))
    look_at(sun, Vector((0, 0, 0)))

    # Sàn vô hình chỉ để hứng bóng, giống sàn trong khung 3D. Đặt ở điểm thấp nhất của cảnh: shadow catcher
    # che mọi thứ phía sau nó -> vật thò xuống dưới sàn sẽ bị cắt mất nếu để ở z = 0.
    lowest = min((o.matrix_world @ v.co).z for o in scene.objects if o.type == "MESH" for v in o.data.vertices)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, min(0.0, lowest)))
    bpy.context.active_object.is_shadow_catcher = True

    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    return {"device": device, "samples": scene.cycles.samples,
            "width": scene.render.resolution_x, "height": scene.render.resolution_y}
