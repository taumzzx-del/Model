"""Generate an editable sculptural headset inspired by the supplied reference.

Run: blender --background --python create_model.py
No external libraries, textures, or assets are required.
"""
import bpy
import math
import os
import sys
from mathutils import Vector

OUT = os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != 'Collection':
        bpy.data.collections.remove(collection)
default = bpy.data.collections.get('Collection')
if default:
    bpy.data.collections.remove(default)

collections = {}
for name in ['01 Headband', '02 Ear shells', '03 Crown foliage', '04 Feather ornaments',
             '05 Woven tendrils', '06 Hanging cable', '07 Studio']:
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    collections[name] = c

def material(name, color, roughness=0.72):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    return m

clay = material('Warm grey sculpting clay', (0.190, 0.193, 0.181))
edge_clay = material('Raised clay details', (0.205, 0.208, 0.195))
inset_clay = material('Recessed clay', (0.140, 0.145, 0.136))
pad_clay = material('Inner cushions', (0.125, 0.134, 0.122))
white = material('White studio', (0.94, 0.94, 0.94))

def assign(obj, collection, mat=clay):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collections[collection].objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    if obj.type == 'MESH':
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj

def mesh(name, verts, faces, collection, mat=clay):
    data = bpy.data.meshes.new(name + ' geometry')
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    collections[collection].objects.link(obj)
    data.materials.append(mat)
    for poly in data.polygons:
        poly.use_smooth = True
    return obj

def curve(name, coords, radius, collection, mat=clay, cyclic=False, radii=None):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 18
    data.bevel_depth = radius
    data.bevel_resolution = 5
    data.use_fill_caps = True
    spl = data.splines.new('BEZIER')
    spl.bezier_points.add(len(coords) - 1)
    for i, (p, co) in enumerate(zip(spl.bezier_points, coords)):
        p.co = co
        p.handle_left_type = 'AUTO'
        p.handle_right_type = 'AUTO'
        if radii:
            p.radius = radii[i]
    spl.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    collections[collection].objects.link(obj)
    data.materials.append(mat)
    return obj

def sphere(name, pos, scale, collection, mat=clay):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return assign(obj, collection, mat)

def catmull(points, t):
    pts = [Vector(p) for p in points]
    at = min(t, 0.999999) * (len(pts) - 1)
    i = int(at)
    u = at - i
    a, b, c, d = pts[max(0, i-1)], pts[i], pts[i+1], pts[min(len(pts)-1, i+2)]
    return 0.5 * ((2*b) + (-a+c)*u + (2*a-5*b+4*c-d)*u*u + (-a+3*b-3*c+d)*u*u*u)

def leaf(name, points, width, collection, normal=(0, -1, 0), thick=0.20,
         vein=False, mat=clay, shape=0.8):
    """Solid, tapered leaf/feather with a curved centerline and raised midrib."""
    normal = Vector(normal).normalized()
    verts, faces = [], []
    rings, sides = 36, 16
    for i in range(rings + 1):
        t = i / rings
        p = catmull(points, t)
        tangent = (catmull(points, min(t + .002, 1)) - catmull(points, max(0, t-.002))).normalized()
        across = normal.cross(tangent).normalized()
        face_normal = tangent.cross(across).normalized()
        w = width * max(0.004, math.sin(math.pi*t)**shape)
        # Thick roots and slim, sharply pointed tips, with a shallow sculpted ridge.
        thickness = max(.004, w * thick)
        for j in range(sides):
            angle = 2*math.pi*j/sides
            xx = math.cos(angle)
            yy = math.sin(angle)
            ridge = 0.028 * math.sin(math.pi*t) * max(0, yy)**5
            v = p + across * (w*xx) + face_normal * (thickness*yy + ridge)
            verts.append(tuple(v))
    for i in range(rings):
        for j in range(sides):
            a = i*sides+j
            b = i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(rings*sides+j for j in range(sides)))
    obj = mesh(name, verts, faces, collection, mat)
    sub = obj.modifiers.new('Soft sculpt surface', 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    if vein:
        ps = []
        for k in range(9):
            t=.12+.75*k/8
            p=catmull(points,t)
            ps.append(tuple(p+normal*(width*thick*math.sin(math.pi*t)**shape+.018)))
        curve(name+' central ridge', ps, .016, collection, mat,
              radii=[.35,.8,1,1,1,.8,.65,.4,.06])
    return obj

# Arched, thick headband. The open center and narrow rim define the silhouette.
a, b, base = 2.00, 3.18, 3.05
verts, faces = [], []
segments = 112
for i in range(segments+1):
    t=math.pi*i/segments
    p=Vector((a*math.cos(t), .05, base+b*math.sin(t)))
    radial=Vector((math.cos(t)/a,0,math.sin(t)/b)).normalized()
    for r,y in [(-.105,-.34),(.105,-.34),(.105,.34),(-.105,.34)]:
        q=p+radial*r+Vector((0,y,0))
        verts.append(tuple(q))
for i in range(segments):
    for j in range(4):
        faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
faces.extend([(3,2,1,0),tuple(4*segments+j for j in range(4))])
band=mesh('Continuous oval head arch',verts,faces,'01 Headband')
bev=band.modifiers.new('Rounded band edges','BEVEL')
bev.width=.075
bev.segments=4
bev=band.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')

inner=[]
for i in range(49):
    t=.13+(math.pi-.26)*i/48
    p=Vector((a*math.cos(t),.13,base+b*math.sin(t)))
    radial=Vector((math.cos(t)/a,0,math.sin(t)/b)).normalized()
    inner.append(tuple(p-radial*.13))
curve('Continuous inner headband padding',inner,.095,'01 Headband',pad_clay)

def frame(side):
    n=Vector((side*.96,-.28,0)).normalized()
    u=Vector((.28,side*.96,0)).normalized()
    v=Vector((0,0,1))
    return n,u,v

def oval_shell(name,center,normal,u,rx,rz,profile,mat=clay):
    center,normal,u=Vector(center),Vector(normal),Vector(u)
    vertical=Vector((0,0,1))
    verts,faces=[],[]
    N=96
    for r,d in profile:
        for j in range(N):
            angle=math.tau*j/N
            p=center+u*(rx*r*math.cos(angle))+vertical*(rz*r*math.sin(angle))+normal*d
            verts.append(tuple(p))
    for i in range(len(profile)-1):
        for j in range(N):
            faces.append((i*N+j,i*N+(j+1)%N,(i+1)*N+(j+1)%N,(i+1)*N+j))
    obj=mesh(name,verts,faces,'02 Ear shells',mat)
    return obj

def oval_curve(name,center,n,u,rx,rz,depth,radius,collection,mat=clay):
    center=Vector(center)
    ps=[]
    for j in range(24):
        t=math.tau*j/24
        ps.append(tuple(center+u*rx*math.cos(t)+Vector((0,0,rz*math.sin(t)))+n*depth))
    return curve(name,ps,radius,collection,mat,True)

ear_centers={}
for side,label in [(-1,'Left'),(1,'Right')]:
    center=Vector((side*1.99,0,2.85))
    ear_centers[side]=center
    n,u,v=frame(side)
    oval_shell(label+' soft inner ear cushion',center-n*.25,n,u,.73,.99,
               [(0,-.14),(.75,-.14),(.96,-.12),(1.03,-.03),(1.03,.09),(.96,.19),(.72,.19),(0,.19)],pad_clay)
    oval_shell(label+' sculpted outer ear housing',center+n*.03,n,u,.76,1.03,
               [(0,-.15),(.88,-.15),(1,-.10),(1.035,0),(1.02,.11),(.94,.23),(.80,.27),(0,.27)])
    oval_curve(label+' outer shell lip',center,n,u,.70,.96,.23,.038,'02 Ear shells',edge_clay)
    # Sunken annular medallion and slightly raised central oval.
    oval_shell(label+' recessed oval medallion',center+n*.312,n,u,.43,.67,
               [(0,-.015),(.78,-.015),(1,0),(1,.025),(.86,.040),(0,.040)],inset_clay)
    oval_curve(label+' inset oval border',center,n,u,.45,.69,.32,.049,'02 Ear shells')
    oval_shell(label+' central oval relief',center+n*.35,n,u,.30,.48,
               [(0,-.01),(.85,-.01),(1,.025),(.95,.07),(.8,.105),(0,.105)],edge_clay)
    # A gently organic yoke joins each earcup and the arch.
    curve(label+' upper yoke',[(side*1.99,-.05,3.42),(side*2.10,-.13,3.75),
                             (side*2.05,-.17,4.10)],.13,'01 Headband')

# Twined climbing stems on the outside of the head arch.
for strand in range(3):
    ps=[]
    for k in range(67):
        t=.04+(math.pi-.08)*k/66
        radial=Vector((math.cos(t)/a,0,math.sin(t)/b)).normalized()
        offset=.13+.105*math.cos(t*13+strand*2.1)
        p=Vector((a*math.cos(t),.05,base+b*math.sin(t)))
        p+=radial*offset+Vector((0,-.24+.13*math.sin(t*13+strand*2.1),0))
        ps.append(tuple(p))
    curve('Arch climbing vine %02d'%(strand+1),ps,.065 if strand else .095,'05 Woven tendrils')

# Flame-like leaves follow the crest instead of forming a solid second headband.
crown_leaves=[
 ('Left rising crest',[(-1.74,-.39,4.23),(-1.99,-.42,4.59),(-1.74,-.40,5.07),(-1.71,-.39,5.60)],.24),
 ('Left outer split leaf',[(-1.95,-.34,4.60),(-2.24,-.35,4.99),(-2.09,-.33,5.33)],.17),
 ('Left inner flame',[(-1.71,-.42,5.03),(-1.47,-.44,5.46),(-1.40,-.40,5.85)],.20),
 ('Upper left bud',[(-1.40,-.40,5.57),(-1.21,-.44,5.93),(-.93,-.36,6.16)],.16),
 ('Crown left spire',[(-1.12,-.28,5.93),(-.78,-.27,6.28),(-.29,-.22,6.62)],.13),
 ('Crown swept flame',[(.61,-.33,6.11),(.23,-.41,6.38),(-.04,-.37,6.68),(-.59,-.32,6.78)],.24),
 ('Crown horizontal fork',[(.64,-.40,6.13),(.23,-.46,6.27),(-.50,-.48,6.36)],.145),
 ('Crown lower fork',[(.80,-.40,5.98),(.54,-.44,6.05),(.14,-.50,6.11)],.14),
 ('Right prominent hanging leaf',[(1.10,-.52,5.94),(1.27,-.57,5.59),(1.31,-.58,5.17),(1.10,-.55,4.80)],.28),
 ('Right upper folded petal',[(1.10,-.50,5.72),(.91,-.53,6.04),(.99,-.50,6.38)],.18),
 ('Right outside pointed petal',[(1.37,-.45,5.73),(1.61,-.44,5.35),(1.74,-.43,4.85)],.21),
 ('Right inner fork',[(1.22,-.55,5.59),(1.11,-.59,5.34),(.91,-.55,5.19)],.13),
 ('Right climbing flame',[(1.94,-.44,4.17),(1.93,-.48,4.63),(2.20,-.46,5.03)],.15),
 ('Right outer climbing flame',[(2.01,-.42,3.98),(2.27,-.45,4.30),(2.37,-.37,4.56)],.16),
 ('Left lower pointed leaf',[(-2.03,-.36,3.79),(-2.26,-.44,4.05),(-2.08,-.43,4.36)],.15),
]
for name,ps,w in crown_leaves:
    leaf(name,ps,w,'03 Crown foliage',vein='prominent' in name or 'swept' in name)

# Organic wreaths and small roots flowing over the two ear shells.
for side,label in [(-1,'Left'),(1,'Right')]:
    c=ear_centers[side]
    n,u,v=frame(side)
    for j in range(3):
        ps=[]
        for k in range(15):
            t=.04+math.pi*1.48*k/14+j*.20
            rx=.80+.04*math.sin(3*t+j)
            rz=1.09+.09*math.sin(2*t+j)
            q=c+u*(rx*math.cos(t))+v*(rz*math.sin(t))+n*(.23+.085*math.sin(4*t+j*2))
            ps.append(tuple(q))
        curve(label+' braided ear wreath '+str(j+1),ps,.065+j*.01,'05 Woven tendrils')
    curve(label+' long cheek vine',[(side*1.82,-.57,3.91),(side*1.62,-.79,3.42),
                                  (side*1.77,-.91,2.62),(side*1.57,-.86,1.87),
                                  (side*.95,-.69,1.53)],.092,'05 Woven tendrils',
          radii=[.4,1,1,.9,.12])

# Open, ribbed wings spreading behind the earcups.
for side,label in [(1,'Right'),(-1,'Left')]:
    shift=0 if side==1 else -.35
    def wing_point(x,y,z):
        return (x if side==1 else x-4.15,y,z+shift)
    leaf(label+' long upper wing feather',[
        wing_point(2.05,.40,3.28),wing_point(2.78,.40,4.06),
        wing_point(3.51,.36,4.72),wing_point(4.00,.33,4.80)],
        .255,'04 Feather ornaments',normal=(0,-1,0),thick=.25,vein=True)
    for j in range(5):
        high=4.10-.29*j
        ps=[wing_point(2.10,.35,3.31-.12*j),
            wing_point(2.73,.31,high-.24),
            wing_point(3.69-.035*j,.27,high),
            wing_point(3.89-.07*j,.24,high-.12),
            wing_point(3.22-.13*j,.21,high-.54),
            wing_point(2.16,.25,2.68-.13*j)]
        curve(label+' open wing loop %02d'%(j+1),ps,.058 if j<3 else .065,
              '04 Feather ornaments',radii=[1,1,.84,.73,.92,1])
    leaf(label+' lower wing barb',[
        wing_point(2.0,.25,2.30),wing_point(2.65,.22,2.12),wing_point(3.21,.20,2.36)],
        .115,'04 Feather ornaments')

# A broad bird/dragon ornament on the front of the left shell.
# Separate overlapping sculpted feathers keep the ornament editable.
leaf('Left bird swept head and neck',[(-2.01,-.85,3.54),(-1.67,-1.0,3.28),
     (-1.34,-1.04,2.90),(-1.28,-1.04,2.49),(-1.39,-1.00,2.11)],.29,
     '04 Feather ornaments',thick=.32)
leaf('Left bird upward curved crown',[(-1.62,-1.04,3.22),(-1.05,-.99,3.14),
     (-.77,-.91,3.42),(-.39,-.85,3.31)],.19,'04 Feather ornaments')
leaf('Left bird pointed upper beak',[(-1.47,-1.02,3.04),(-1.01,-1.04,2.98),
     (-.53,-1.02,3.14),(-.28,-.96,3.27)],.15,'04 Feather ornaments',shape=1.05)
leaf('Left bird pointed lower beak',[(-1.32,-1.03,2.83),(-.88,-1.06,2.79),
     (-.44,-1.04,2.98),(-.31,-.99,3.10)],.13,'04 Feather ornaments')

for j in range(7):
    root=(-1.76+.085*j,-1.08,3.06-.09*j)
    if j<3:
        tip=(-2.04+.24*j,-1.08,1.83-.12*j)
        mid=(-1.85+.17*j,-1.16,2.32-.09*j)
    else:
        tip=(-1.2+.29*(j-3),-1.03,1.37-.07*math.sin(j))
        mid=(-1.45+.14*(j-3),-1.16,1.87-.035*j)
    leaf('Left bird trailing neck feather %02d'%(j+1),[root,mid,tip],
         .106 if j<3 else .125,'04 Feather ornaments',thick=.30)
for j in range(4):
    leaf('Left bird swept flight feather %02d'%(j+1),[
        (-1.43,-1.06,2.70-.12*j),(-.85,-1.05,2.54-.14*j),
        (-.33+.075*j,-.95,2.64-.20*j),(-.18+.035*j,-.90,2.88-.26*j)],
        .095,'04 Feather ornaments',thick=.29)

# A teardrop relief eye, bordered by a thin line of clay.
eye_center=Vector((-1.82,-1.129,3.235))
eye_outline=[(-1.96,-1.18,3.39),(-1.82,-1.21,3.30),(-1.71,-1.19,3.14),
             (-1.84,-1.18,3.16)]
curve('Bird teardrop eye outline',eye_outline,.026,'04 Feather ornaments',edge_clay,True)
eye=sphere('Bird shallow eye relief',eye_center,(.065,.024,.132),'04 Feather ornaments',inset_clay)
eye.rotation_euler[1]=-.52

# Small curled crest on the other side of the left earcup.
curve('Left curled crest stem',[(-2.09,-.77,3.53),(-2.42,-.84,3.65),
     (-2.64,-.85,3.46),(-2.53,-.88,3.24),(-2.35,-.88,3.29),
     (-2.39,-.87,3.45)],.085,'04 Feather ornaments',radii=[1,1,1,.85,.70,.35])
for j in range(3):
    leaf('Left forward ornamental flame '+str(j+1),[
        (-2.25-.08*j,-.66,2.61-.15*j),(-2.80-.07*j,-.73,2.25-.18*j),
        (-3.06-.02*j,-.68,2.56-.26*j),(-3.02+.11*j,-.61,3.24-.19*j)],
        .16,'04 Feather ornaments',thick=.35)
curve('Left forward upward scroll',[(-2.41,-.63,2.65),(-2.91,-.70,2.62),
     (-3.12,-.67,3.02),(-3.09,-.59,3.51),(-3.18,-.58,3.61)],
     .077,'05 Woven tendrils',radii=[1,1,1,.85,.28])

# Loose roots below the headset form the horizontal lower silhouette.
bridges=[
 [(-2.36,-.58,2.13),(-1.79,-.71,1.82),(-.85,-.72,1.57),(.29,-.63,1.57),(1.32,-.49,1.95),(1.82,-.46,2.52)],
 [(-1.70,-.37,2.00),(-1.03,-.50,1.89),(-.04,-.54,1.95),(.93,-.51,2.25),(1.51,-.44,2.87),(1.89,-.36,3.40)],
 [(-2.50,-.21,2.05),(-1.79,-.34,1.72),(-.86,-.38,1.36),(.04,-.30,1.30),(.88,-.33,1.48),(1.53,-.46,2.23)],
 [(-1.61,.23,1.99),(-.68,.18,1.80),(.16,.20,1.84),(1.01,.04,2.02),(1.62,-.16,2.58)],
]
for i,ps in enumerate(bridges):
    curve('Lower sweeping tendril %02d'%(i+1),ps,.095 if i==0 else .072,
          '05 Woven tendrils',radii=[.5]+[1]*(len(ps)-2)+[.5])
for j in range(3):
    leaf('Lower curling leaf '+str(j+1),[(-.65+.35*j,-.57,1.68+.06*j),
        (-.66+.36*j,-.72,1.95+.03*j),(-.29+.36*j,-.66,1.95+.08*j)],
        .10,'03 Crown foliage')

# Branching root collar below the right earcup.
for j in range(4):
    leaf('Right cable collar petal '+str(j+1),[(1.95+.10*j,-.25,2.00),
         (1.87+.14*j,-.43,1.65),(1.73+.18*j,-.47,1.37)],
         .17,'03 Crown foliage',thick=.34)

# Four separate hanging cable loops and a visible USB-style connector.
loops=[
 [(1.93,-.31,1.73),(1.46,-.63,1.12),(1.06,-.72,.32),(1.26,-.65,-.10),
  (1.74,-.49,-.12),(2.13,-.36,.58),(2.29,-.31,1.53)],
 [(2.10,-.20,1.65),(2.32,-.42,.80),(2.29,-.58,-.20),(1.76,-.68,-.85),
  (1.43,-.65,-.89),(1.38,-.59,-.53),(1.65,-.49,.27),(1.90,-.38,1.45)],
 [(2.24,.12,1.68),(2.68,-.05,1.09),(2.68,-.14,.22),(2.48,-.22,-.23),
  (2.24,-.26,.01),(2.16,-.24,.65),(2.05,-.07,1.48)],
 [(2.05,.16,1.61),(1.77,.13,.95),(1.25,.05,.46),(.85,-.12,.50),
  (.65,-.30,.98),(1.06,-.43,1.68),(1.57,-.36,2.05)],
]
for i,ps in enumerate(loops):
    curve('Hanging cable loop %02d'%(i+1),ps,.079 if i==1 else .065,'06 Hanging cable')

cord=[(1.83,-.19,1.75),(1.34,-.44,1.04),(.66,-.62,.45),(.35,-.67,-.03),(.29,-.66,-.38)]
curve('Loose connector cable',cord,.053,'06 Hanging cable')

def rounded_box(name,center,size,collection,mat=clay,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    obj=bpy.context.object
    obj.name=name
    obj.scale=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    assign(obj,collection,mat)
    modifier=obj.modifiers.new('Rounded machined edges','BEVEL')
    modifier.width=bevel
    modifier.segments=4
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return obj

rounded_box('USB connector clay sleeve',(.29,-.66,-.50),(.22,.16,.32),'06 Hanging cable',bevel=.027)
rounded_box('USB connector tip',(.29,-.66,-.73),(.16,.11,.19),'06 Hanging cable',inset_clay,bevel=.010)
rounded_box('Connector recessed seam',(.29,-.66,-.385),(.23,.17,.024),'06 Hanging cable',inset_clay,bevel=.008)

# Clean studio lighting, orthographic camera and an unobtrusive floor.
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=96
scene.cycles.use_denoising=False
scene.render.threads_mode='FIXED'
scene.render.threads=8
scene.render.resolution_x=1200
scene.render.resolution_y=1200
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=True
scene.world.color=(.80,.80,.80)
scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.94,.94,.94,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.35
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.use_nodes=True
nodes=scene.node_tree.nodes
nodes.clear()
rl=nodes.new('CompositorNodeRLayers')
over=nodes.new('CompositorNodeAlphaOver')
over.inputs[0].default_value=1.0
over.inputs[1].default_value=(16,16,16,1)
output=nodes.new('CompositorNodeComposite')
scene.node_tree.links.new(rl.outputs['Image'],over.inputs[2])
scene.node_tree.links.new(over.outputs['Image'],output.inputs['Image'])

def point_at(obj, target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def area(name,pos,power,size,target):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power
    data.shape='DISK'
    data.size=size
    obj=bpy.data.objects.new(name,data)
    collections['07 Studio'].objects.link(obj)
    obj.location=pos
    point_at(obj,target)

area('Large softbox upper left',(-5,-7,11),700,6,(0,0,3))
area('Right soft fill',(7,-5,6),320,5,(1,0,3))
area('Top rim light',(1,5,10),900,5,(0,0,4))
area('Low frontal fill',(0,-7,1),75,4,(0,0,2))
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1.10))
floor=bpy.context.object
floor.name='White shadow floor'
assign(floor,'07 Studio',white)
floor.hide_render=True
floor.hide_viewport=True

camera_data=bpy.data.cameras.new('Reference three quarter camera')
camera=bpy.data.objects.new('Reference three quarter camera',camera_data)
collections['07 Studio'].objects.link(camera)
camera.location=(10,-17,8.7)
point_at(camera,(.12,0,2.98))
camera_data.type='ORTHO'
camera_data.ortho_scale=9.0
camera_data.lens=52
scene.camera=camera

# All shapes remain separate and named; curves retain editable control points.
scene['model_notes']='Reference-inspired sculptural headset. Editable curves and separate leaf meshes; no external assets.'
scene['reference_limit']='One supplied view: rear details and hidden surfaces are interpreted.'
for screen in bpy.data.screens:
    for area_ui in screen.areas:
        if area_ui.type=='VIEW_3D':
            space=area_ui.spaces.active
            space.region_3d.view_perspective='CAMERA'
            space.shading.type='MATERIAL'
            space.clip_end=500
bpy.ops.object.select_all(action='DESELECT')
band.select_set(True)
bpy.context.view_layer.objects.active=band
scene.render.filepath=os.path.join(OUT,'headset_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'sculptural_headset.blend'))
print('MODEL_OBJECTS',sum(1 for o in scene.objects if o.type in {'MESH','CURVE'} and o!=floor))
if '--draft' in sys.argv:
    scene.render.resolution_x=640
    scene.render.resolution_y=640
    scene.cycles.samples=12
    scene.render.filepath=os.path.join(OUT,'draft_preview.png')
bpy.ops.render.render(write_still=True)
# An exchange file contains the actual headset, excluding lights and studio geometry.
bpy.ops.object.select_all(action='DESELECT')
for obj in list(scene.objects):
    if obj.type=='MESH' and obj!=floor:
        obj.select_set(True)
    elif obj.type=='CURVE':
        depsgraph=bpy.context.evaluated_depsgraph_get()
        data=bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
        duplicate=bpy.data.objects.new(obj.name+' export mesh',data)
        scene.collection.objects.link(duplicate)
        duplicate.matrix_world=obj.matrix_world.copy()
        duplicate.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,'sculptural_headset.glb'),
                          use_selection=True,export_apply=True,export_yup=True)
print('DELIVERABLES_READY',OUT)
