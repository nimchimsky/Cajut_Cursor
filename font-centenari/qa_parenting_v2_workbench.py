#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import bpy, json, math
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(bpy.path.abspath('//')).resolve()
OUT=ROOT/'qa_v2_workbench'; OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=900; scene.render.resolution_y=675; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.display.shading.light='STUDIO'
scene.display.shading.studio_light='paint.sl'
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type='WORLD'
scene.display.shading.curvature_ridge_factor=1.8
scene.display.shading.curvature_valley_factor=1.3
scene.display.shading.show_specular_highlight=True
scene.render.film_transparent=False

parents=[]
for name in ('GRUP_ASIA','GRUP_AMERICA','GRUP_AFRICA','GRUP_EUROPA'):
    p=bpy.data.objects.get(name)
    if p:
        parents.append(p)
        for child in list(p.children):
            child.matrix_parent_inverse=Matrix.Identity(4)

# Keep only the two inner jet rings for an honest sculpture-focused QA.
for obj in list(bpy.data.objects):
    if obj.name.startswith('Raig_2_') or obj.name.startswith('Broquet_2_'):
        bpy.data.objects.remove(obj,do_unlink=True)
    if obj.name.startswith('Edifici_context_'):
        obj.hide_render=True

for obj in list(bpy.data.objects):
    if obj.type=='CAMERA': bpy.data.objects.remove(obj,do_unlink=True)

coll=bpy.data.collections.get('04_LLUMS_I_CAMERES')
if coll is None:
    coll=bpy.data.collections.new('04_LLUMS_I_CAMERES'); scene.collection.children.link(coll)
def move(o):
    for c in list(o.users_collection): c.objects.unlink(o)
    coll.objects.link(o)
def look(o,t): o.rotation_euler=(Vector(t)-o.location).to_track_quat('-Z','Y').to_euler()
def cam(name,loc,target,lens):
    bpy.ops.object.camera_add(location=loc); c=bpy.context.object; c.name=name; c.data.lens=lens; move(c); look(c,target); return c
cams=[
    cam('QA_01_GENERAL',(0,-24,7.2),(0,0,2.0),50),
    cam('QA_02_OBLIQUA',(-17,-17,7.0),(0,0,2.0),52),
    cam('QA_03_ASIA',(13,-4.0,5.0),(7.25,0,2.8),62),
    cam('QA_04_AMERICA',(-13,4.0,4.7),(-7.25,0,2.45),62),
    cam('QA_05_AFRICA',(-4.0,-13,4.9),(0,-7.25,2.55),62),
    cam('QA_06_EUROPA',(4.0,13,4.9),(0,7.25,2.55),62),
    cam('QA_07_ZENITAL',(0,0,28),(0,0,0.7),48),
]
for c in cams:
    scene.camera=c; scene.render.filepath=str(OUT/f'{c.name}.png'); bpy.ops.render.render(write_still=True)

report={'groups':{},'objects':len(bpy.data.objects),'meshes':len(bpy.data.meshes),'curves':len(bpy.data.curves)}
for p in parents:
    pts=[]
    for ch in p.children:
        for co in ch.bound_box: pts.append(ch.matrix_world@Vector(co))
    report['groups'][p.name]={'children':len(p.children),'min':[min(q[i] for q in pts) for i in range(3)],'max':[max(q[i] for q in pts) for i in range(3)]}
(OUT/'qa_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Font_del_Centenari_Tarragona_QA_v2.blend'))
print(json.dumps(report))
