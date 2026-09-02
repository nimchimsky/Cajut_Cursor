#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final refinement pass for the Font del Centenari scene.

This script is run by Blender after the detailed procedural build. It corrects
legacy transform errors, improves the stone/water materials, adds missing
commemorative and hydraulic details, creates a repeatable camera suite, renders
validation views and writes an auditable model report.
"""
from __future__ import annotations

import bpy
import json
import math
import re
from pathlib import Path
from mathutils import Vector

ROOT = Path(bpy.path.abspath("//")).resolve()
if ROOT.name == "":
    ROOT = Path.cwd() / "project"
RENDERS = ROOT / "renders"
DOCS = ROOT / "docs"
EXPORTS = ROOT / "exports"
for p in (RENDERS, DOCS, EXPORTS):
    p.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
scene.render.resolution_x = 1100
scene.render.resolution_y = 825
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    pass
try:
    scene.render.image_settings.color_mode = "RGBA"
except Exception:
    pass
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass


def ensure_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
    return c

COL_FIX = ensure_collection("90_REFINAMENT_FINAL")
COL_CAM = ensure_collection("91_CAMERES_FINALS")


def move_to_collection(obj, coll):
    for c in list(obj.users_collection):
        try:
            c.objects.unlink(obj)
        except Exception:
            pass
    coll.objects.link(obj)
    return obj


def material_principled(name: str, color, rough=0.6, metallic=0.0, transmission=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    for key in ("Base Color",):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = (*color, 1)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = rough
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    for key in ("Transmission Weight", "Transmission"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = transmission
            break
    return mat


def rebuild_stone_material(mat: bpy.types.Material, wet=False):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 5.4 if not wet else 7.5
    tex.inputs["Detail"].default_value = 7.0
    tex.inputs["Roughness"].default_value = 0.72
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 58.0
    fine.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    if wet:
        ramp.color_ramp.elements[0].color = (0.18, 0.17, 0.15, 1)
        ramp.color_ramp.elements[1].color = (0.42, 0.39, 0.33, 1)
    else:
        ramp.color_ramp.elements[0].color = (0.43, 0.40, 0.34, 1)
        ramp.color_ramp.elements[1].color = (0.72, 0.67, 0.56, 1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22 if wet else 0.30
    bump.inputs["Distance"].default_value = 0.055
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs["Fac"].default_value = 0.22
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[1])
    nt.links.new(fine.outputs["Fac"], mix.inputs[2])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.72 if wet else 0.88
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


stone_mats = []
for mat in bpy.data.materials:
    n = mat.name.lower()
    if any(k in n for k in ("stone", "pedra", "limestone", "escultura", "roca")) and "water" not in n and "aigua" not in n:
        stone_mats.append(mat)
for mat in stone_mats:
    rebuild_stone_material(mat, wet=("wet" in mat.name.lower() or "humit" in mat.name.lower()))

WATER = bpy.data.materials.get("Aigua_FINAL") or material_principled("Aigua_FINAL", (0.18, 0.48, 0.62), rough=0.07, transmission=0.82)
CAVITY = bpy.data.materials.get("Cavitats_FINAL") or material_principled("Cavitats_FINAL", (0.035, 0.031, 0.027), rough=0.92)
METAL = bpy.data.materials.get("Placa_bronze_FINAL") or material_principled("Placa_bronze_FINAL", (0.21, 0.11, 0.035), rough=0.34, metallic=0.78)
STONE = stone_mats[0] if stone_mats else material_principled("Pedra_FINAL", (0.58, 0.54, 0.46), rough=0.88)
if not stone_mats:
    rebuild_stone_material(STONE)


def assign(obj, mat):
    if hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    return obj


def add_box(name, loc, scale, mat=STONE):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    move_to_collection(o, COL_FIX)
    assign(o, mat)
    bevel = o.modifiers.new("Bisell", "BEVEL")
    bevel.width = min(scale) * 0.10
    bevel.segments = 3
    return o


def add_cyl(name, loc, radius, depth, mat=STONE, vertices=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    move_to_collection(o, COL_FIX)
    assign(o, mat)
    return o


def add_curve(name, points, bevel=0.035, mat=WATER):
    cu = bpy.data.curves.new(name + "_curve", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.resolution_u = 12
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, co in zip(sp.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, cu)
    COL_FIX.objects.link(obj)
    assign(obj, mat)
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


# Correct the local/world transform bug found in the first comparison pass.
expected = {
    "EUROPA": Vector((0.0, 6.05, 0.0)),
    "NORD": Vector((0.0, 6.05, 0.0)),
    "AFRICA": Vector((0.0, -6.05, 0.0)),
    "SUD": Vector((0.0, -6.05, 0.0)),
    "ASIA": Vector((6.05, 0.0, 0.0)),
    "EST": Vector((6.05, 0.0, 0.0)),
    "AMERICA": Vector((-6.05, 0.0, 0.0)),
    "OEST": Vector((-6.05, 0.0, 0.0)),
}
shifted = set()
for key, target in expected.items():
    candidates = [o for o in bpy.data.objects if key in o.name.upper()]
    if not candidates:
        continue
    # Move only a genuinely misplaced local group. Correctly placed groups have
    # at least one object beyond four metres from the centre.
    max_r = max(math.hypot(o.matrix_world.translation.x, o.matrix_world.translation.y) for o in candidates)
    if max_r < 3.6:
        for o in candidates:
            if o.parent is None:
                o.location.x += target.x
                o.location.y += target.y
                shifted.add(o.name)

# Remove obsolete central monument masses from the rejected first draft.
for obj in list(bpy.data.objects):
    n = obj.name.lower()
    if any(k in n for k in ("roca_central", "podi_central", "nucli_escultoric_central")):
        bpy.data.objects.remove(obj, do_unlink=True)

# Commemorative plaque on the south outer face of the basin.
if bpy.data.objects.get("Placa_Font_Centenari_1954") is None:
    plaque = add_box("Placa_Font_Centenari_1954", (0, -6.62, 0.54), (1.28, 0.055, 0.34), METAL)
    plaque.rotation_euler.x = math.radians(90)
    bpy.ops.object.text_add(location=(-0.96, -6.685, 0.55), rotation=(math.radians(90), 0, 0))
    txt = bpy.context.object
    txt.name = "Inscripcio_Font_Centenari"
    txt.data.body = "FONT DEL CENTENARI · 1954"
    txt.data.align_x = "LEFT"
    txt.data.size = 0.18
    txt.data.extrude = 0.006
    move_to_collection(txt, COL_FIX)
    assign(txt, STONE)

# Ensure the characteristic animal-mouth water streams are present. Their
# endpoints are deliberately asymmetric, matching the four separate groups.
stream_specs = [
    ("Aigua_Os", (-0.35, 5.18, 1.45), (-0.20, 4.55, 0.55)),
    ("Aigua_Hipopotam", (0.25, -5.15, 1.12), (0.15, -4.35, 0.54)),
    ("Aigua_Elefant", (5.30, 0.18, 1.30), (4.48, 0.12, 0.54)),
    ("Aigua_Cocodril", (-5.18, -0.22, 1.00), (-4.32, -0.18, 0.54)),
]
for name, start, end in stream_specs:
    if bpy.data.objects.get(name) is None:
        mid = ((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5, max(start[2], end[2]) + 0.12)
        add_curve(name, [start, mid, end], 0.028, WATER)

# Add subtle splash rings below the four spouts.
for i, (_, _, end) in enumerate(stream_specs, 1):
    if bpy.data.objects.get(f"Esquitx_{i}") is None:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.013, major_segments=36, minor_segments=10, location=(end[0], end[1], 0.545))
        tor = bpy.context.object
        tor.name = f"Esquitx_{i}"
        move_to_collection(tor, COL_FIX)
        assign(tor, WATER)

# Camera suite: overall geometry and one close-up per sculptural group.
for o in list(COL_CAM.objects):
    if o.type == "CAMERA":
        bpy.data.objects.remove(o, do_unlink=True)

camera_specs = [
    ("01_General_SO", (-14.5, -15.5, 8.0), (0, 0, 1.45), 47),
    ("02_General_NE", (14.0, 15.5, 7.7), (0, 0, 1.40), 48),
    ("03_Aeria", (0.2, -0.2, 21.5), (0, 0, 0.3), 43),
    ("04_Europa_Os", (1.5, 11.2, 4.3), (0, 5.95, 1.55), 58),
    ("05_Africa_Hipopotam", (-1.3, -11.0, 4.0), (0, -5.95, 1.45), 58),
    ("06_Asia_Elefant", (11.0, -1.4, 4.2), (5.95, 0, 1.50), 58),
    ("07_America_Cocodril", (-11.2, 1.5, 3.7), (-5.95, 0, 1.25), 60),
    ("08_Rasant_Rambla", (-13.4, -11.8, 2.4), (0, 0, 1.05), 52),
]
cameras = []
for name, loc, target, lens in camera_specs:
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = False
    move_to_collection(cam, COL_CAM)
    look_at(cam, target)
    cameras.append(cam)

# Lighting refinements.
for o in list(COL_CAM.objects):
    if o.type == "LIGHT":
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.light_add(type="SUN", location=(18, -22, 26))
sun = bpy.context.object
sun.name = "Sol_final"
sun.data.energy = 2.6
sun.rotation_euler = (math.radians(27), math.radians(-18), math.radians(-34))
move_to_collection(sun, COL_CAM)
for name, loc, energy, size in [
    ("Rebot_oest", (-12, -10, 10), 1050, 8),
    ("Rebot_est", (12, 8, 9), 850, 7),
    ("Rebot_superior", (0, 0, 15), 700, 9),
]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    lamp = bpy.context.object
    lamp.name = name
    lamp.data.energy = energy
    lamp.data.shape = "DISK"
    lamp.data.size = size
    move_to_collection(lamp, COL_CAM)
    look_at(lamp, (0, 0, 1.0))

world = scene.world or bpy.data.worlds.new("Mon_urbà")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.50, 0.61, 0.73, 1)
    bg.inputs["Strength"].default_value = 0.45

# Save the refined file before rendering.
outfile = ROOT / "Font_del_Centenari_Tarragona_REALISTA_FINAL.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(outfile))

for cam in cameras:
    scene.camera = cam
    scene.render.filepath = str(RENDERS / f"{cam.name}.png")
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as exc:
        print("Render warning", cam.name, exc)

# GLB export is secondary; failure must not invalidate the native blend.
try:
    bpy.ops.export_scene.gltf(filepath=str(EXPORTS / "Font_del_Centenari_Tarragona_REALISTA_FINAL.glb"), export_format="GLB", export_apply=True)
except Exception as exc:
    print("GLB export warning:", exc)

# Audit geometry and bounding box.
mesh_objects = [o for o in bpy.data.objects if o.type == "MESH"]
poly_count = sum(len(o.data.polygons) for o in mesh_objects if o.data)
verts_count = sum(len(o.data.vertices) for o in mesh_objects if o.data)
all_points = []
for o in mesh_objects:
    for corner in o.bound_box:
        all_points.append(o.matrix_world @ Vector(corner))
if all_points:
    mins = [min(p[i] for p in all_points) for i in range(3)]
    maxs = [max(p[i] for p in all_points) for i in range(3)]
    dims = [maxs[i] - mins[i] for i in range(3)]
else:
    mins = maxs = dims = [0, 0, 0]
report = {
    "file": str(outfile),
    "objects": len(bpy.data.objects),
    "meshes": len(bpy.data.meshes),
    "curves": len(bpy.data.curves),
    "materials": len(bpy.data.materials),
    "cameras": len(bpy.data.cameras),
    "lights": len(bpy.data.lights),
    "vertices": verts_count,
    "polygons": poly_count,
    "bounds_min_m": mins,
    "bounds_max_m": maxs,
    "dimensions_m": dims,
    "transform_corrections": sorted(shifted),
    "render_files": [p.name for p in sorted(RENDERS.glob("*.png"))],
}
(DOCS / "model_report_final.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(outfile))
print(json.dumps(report, ensure_ascii=False))
