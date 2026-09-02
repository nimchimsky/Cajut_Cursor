#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import bpy
import json
import math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = Path(bpy.path.abspath("//")).resolve()
RENDERS = ROOT / "renders_v2"
DOCS = ROOT / "docs_v2"
RENDERS.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'
scene.render.resolution_x = 960
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

# The original procedural script created every sculpture in local coordinates,
# then assigned a parent *and* an inverse matrix. That deliberately preserved the
# old world coordinates, so all four groups stayed piled up at the origin while
# the cameras looked at the empty rim. Resetting the inverse makes the authored
# local coordinates actually follow the four cardinal group empties.
parents = []
for name in ('GRUP_ASIA', 'GRUP_AMERICA', 'GRUP_AFRICA', 'GRUP_EUROPA'):
    p = bpy.data.objects.get(name)
    if p:
        parents.append(p)
        for child in list(p.children):
            child.matrix_parent_inverse = Matrix.Identity(4)

# Remove the visually dominant outer ring of generic jets. The real fountain has
# a central composition of jets, but the first model's 26 thin curves obscured the
# sculpture and made the monument read like a generic splash pad.
for obj in list(bpy.data.objects):
    n = obj.name
    if n.startswith('Raig_2_') or n.startswith('Broquet_2_'):
        bpy.data.objects.remove(obj, do_unlink=True)

# Slightly thicken the remaining water curves and make them less emissive.
for obj in bpy.data.objects:
    if obj.type == 'CURVE' and ('Raig_' in obj.name or 'Aigua_' in obj.name or 'Cortina_aigua_' in obj.name):
        try:
            obj.data.bevel_depth = max(obj.data.bevel_depth, 0.018)
            obj.data.bevel_resolution = max(obj.data.bevel_resolution, 3)
        except Exception:
            pass

# Improve water material so the sculpture remains legible through it.
water = bpy.data.materials.get('Aigua_font')
if water and water.use_nodes:
    bsdf = next((n for n in water.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        if 'Base Color' in bsdf.inputs: bsdf.inputs['Base Color'].default_value = (0.07,0.25,0.34,1)
        if 'Roughness' in bsdf.inputs: bsdf.inputs['Roughness'].default_value = 0.12
        for key in ('Transmission Weight','Transmission'):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = 0.55
                break
        if 'Emission Strength' in bsdf.inputs: bsdf.inputs['Emission Strength'].default_value = 0.0

# Strengthen the aged limestone contrast.
for mat in bpy.data.materials:
    if not mat.use_nodes: continue
    if 'Pedra_Hontoria' in mat.name:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf and 'Roughness' in bsdf.inputs: bsdf.inputs['Roughness'].default_value = 0.91

# Delete existing cameras and make cameras that actually frame each group.
for obj in list(bpy.data.objects):
    if obj.type == 'CAMERA':
        bpy.data.objects.remove(obj, do_unlink=True)

cam_coll = bpy.data.collections.get('04_LLUMS_I_CAMERES')
if cam_coll is None:
    cam_coll = bpy.data.collections.new('04_LLUMS_I_CAMERES')
    scene.collection.children.link(cam_coll)

def move(obj, coll):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)

def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z','Y').to_euler()

def add_camera(name, loc, target, lens=52):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    move(cam, cam_coll)
    look_at(cam, target)
    return cam

cams = [
    add_camera('V2_01_GENERAL_RAMBLA',(0,-25,7.5),(0,0,2.1),50),
    add_camera('V2_02_GENERAL_OBLIQUA',(-18,-18,7.0),(0,0,2.0),52),
    add_camera('V2_03_ASIA_ELEFANT',(13.5,-4.8,5.2),(7.2,0,3.0),62),
    add_camera('V2_04_AMERICA_COCODRIL',(-13.5,4.5,4.8),(-7.2,0,2.5),62),
    add_camera('V2_05_AFRICA_HIPOPOTAM',(-4.5,-13.5,5.0),(0,-7.2,2.7),62),
    add_camera('V2_06_EUROPA_OS',(4.5,13.5,5.0),(0,7.2,2.7),62),
    add_camera('V2_07_ZENITAL',(0,0,28),(0,0,0.8),48),
]

# Restore a balanced daylight rig.
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.object.light_add(type='SUN', location=(20,-25,28))
sun = bpy.context.object
sun.name='Sol_V2'; sun.data.energy=2.8
sun.rotation_euler=(math.radians(28),math.radians(-18),math.radians(-35))
move(sun,cam_coll)
for name,loc,energy,size in [
    ('Area_Oest',(-12,-10,11),1000,8),
    ('Area_Est',(12,8,10),850,8),
    ('Area_Superior',(0,0,16),650,10),
]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    l=bpy.context.object; l.name=name; l.data.energy=energy; l.data.shape='DISK'; l.data.size=size
    move(l,cam_coll); look_at(l,(0,0,1.5))

# Hide oversized generic context blocks in close-up validation renders.
for obj in bpy.data.objects:
    if obj.name.startswith('Edifici_context_'):
        obj.hide_render = True

out = ROOT / 'Font_del_Centenari_Tarragona_REALISTA_v2.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out))

for cam in cams:
    scene.camera = cam
    scene.render.filepath = str(RENDERS / f'{cam.name}.png')
    bpy.ops.render.render(write_still=True)

# Report the actual positions of the four group parents and child bounds.
report={'file':str(out),'objects':len(bpy.data.objects),'meshes':len(bpy.data.meshes),'curves':len(bpy.data.curves),'materials':len(bpy.data.materials),'cameras':len(bpy.data.cameras),'groups':{}}
for p in parents:
    children=list(p.children)
    pts=[]
    for child in children:
        for co in child.bound_box:
            pts.append(child.matrix_world @ Vector(co))
    report['groups'][p.name]={
        'parent_location':list(p.location),
        'children':len(children),
        'bounds_min':[min(v[i] for v in pts) for i in range(3)] if pts else None,
        'bounds_max':[max(v[i] for v in pts) for i in range(3)] if pts else None,
    }
(DOCS/'validation_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(json.dumps(report,ensure_ascii=False))
