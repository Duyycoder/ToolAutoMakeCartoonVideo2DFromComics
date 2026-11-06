"""Bind a temporary welded mesh with Blender Automatic Weights, returning weights in input vertex order."""
import json
import struct
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def skin_weights(src, result):
    data = Path(src).read_bytes()
    if len(data) < 12:
        raise ValueError("Dữ liệu gắn xương bị thiếu")
    count, index_count, joint_bytes = struct.unpack_from("<III", data)
    index_offset = 12 + count * 12
    joint_offset = index_offset + index_count * 4
    if (not 1 <= count <= 1_000_000 or not 1 <= index_count <= 6_000_000 or index_count % 3
            or joint_bytes > 262_144 or joint_offset + joint_bytes != len(data)):
        raise ValueError("Lưới gắn xương không hợp lệ")
    points = np.frombuffer(data, dtype="<f4", count=count * 3, offset=12).reshape(-1, 3)
    indices = np.frombuffer(data, dtype="<u4", count=index_count, offset=index_offset).reshape(-1, 3)
    joints = json.loads(data[joint_offset:])
    heads = np.asarray([j["p"] for j in joints], dtype=np.float64)
    parents = [j["parent"] for j in joints]
    if (not 1 <= len(joints) <= 1024 or heads.shape != (len(joints), 3) or not np.isfinite(heads).all()
            or not np.isfinite(points).all() or indices.max() >= count
            or parents.count(-1) != 1
            or any(type(p) is not int or p < -1 or p >= len(joints) or p == i for i, p in enumerate(parents))):
        raise ValueError("Dữ liệu khớp hoặc đỉnh không hợp lệ")
    for parent in parents:
        for _ in joints:
            if parent < 0:
                break
            parent = parents[parent]
        else:
            raise ValueError("Cây xương không hợp lệ")

    lo, hi = points.min(axis=0).astype(np.float64), points.max(axis=0).astype(np.float64)
    scale = (hi - lo).max()
    if not scale:
        raise ValueError("Lưới không có kích thước")
    center = (lo + hi) / 2
    # Hàn bản sao dùng để tính nhiệt; giữ ánh xạ để không đụng vào UV hay thứ tự đỉnh của Easy3D.
    vertices, original_to_welded = np.unique(np.round((points - center) / scale, 6), axis=0, return_inverse=True)
    original_to_welded = original_to_welded.reshape(-1)
    faces = original_to_welded[indices]
    a, b, c = faces.T
    faces = faces[(a != b) & (b != c) & (c != a)]
    if not len(faces):
        raise ValueError("Lưới không có tam giác hợp lệ")
    heads = (heads - center) / scale
    if np.abs(heads).max() > 10000:
        raise ValueError("Khớp nằm quá xa lưới")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("BindMesh")
    mesh.from_pydata(vertices.tolist(), [], faces.tolist())
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new("BindMesh", mesh)
    arm = bpy.data.armatures.new("BindArmature")
    rig = bpy.data.objects.new("BindArmature", arm)
    bpy.context.collection.objects.link(obj)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    children = [[] for _ in joints]
    for i, p in enumerate(parents):
        if p >= 0:
            children[p].append(i)
    bones = []
    for i, (head, parent) in enumerate(zip(heads, parents)):
        bone = arm.edit_bones.new(str(i))
        bone.head = Vector(head)
        if children[i]:
            tail = Vector(heads[children[i][0]])
        elif parent >= 0:
            tail = bone.head + (bone.head - Vector(heads[parent])) * 0.3
        else:
            tail = bone.head.copy()
        if (tail - bone.head).length < 1e-5:
            tail.y += 1e-3
        bone.tail = tail
        bones.append(bone)
    for i, p in enumerate(parents):
        if p >= 0:
            bones[i].parent = bones[p]
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(True)
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")

    group_ids = [int(group.name) for group in obj.vertex_groups]
    indices_out = np.zeros((len(vertices), 4), dtype="<u2")
    weights_out = np.zeros((len(vertices), 4), dtype="<f4")
    for v in obj.data.vertices:
        weights = sorted(((g.weight, group_ids[g.group]) for g in v.groups if g.weight > 0), reverse=True)[:4]
        total = sum(w for w, _ in weights)
        if not total:
            raise ValueError("Blender không gán được trọng số cho toàn bộ lưới")
        for i, (weight, bone) in enumerate(weights):
            indices_out[v.index, i] = bone
            weights_out[v.index, i] = weight / total
    with Path(result).open("wb") as output:
        output.write(indices_out[original_to_welded].tobytes())
        output.write(weights_out[original_to_welded].tobytes())
    return {"vertices": count, "welded_vertices": len(vertices)}
