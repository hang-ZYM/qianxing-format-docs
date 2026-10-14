# -*- coding: utf-8 -*-
"""archdraw - BOM -> 建筑施工图（SVG 四件套）。

输入"实体 BOM"（JSON，格式见 手册/29 §2），输出：
  正立面图 / 侧立面图 / 平面图 / 拱券大样图（若 BOM 含拱券件）。

画法原则（手册/29 §5）:
  - 立面=聚合画法（墙体整体面层/拱画同心弧带+放射缝/柱分段式），不逐件画色块；
  - 大样=逐构件画法（详图就要一块一块画）；
  - 全部几何从 BOM 推导（标高/半径/缝线/件数动态计算），改 BOM 图纸自动跟。

用法:
    python -m archdraw <BOM.json> [--out 输出目录]
"""


# -*- coding: utf-8 -*-
"""凯旋门 v4 施工图渲染器 —— BOM 驱动 + 建筑制图画法
v3 图乱根因: 178 件逐件画色块矩形。v4: BOM 只供几何, 按立面图画法聚合
(墙体整体面层/拱画同心弧带+放射缝/柱五段式/尺寸线/标高/图例)。
数据源: 知识库/设计文档/凯旋门v4_BOM.json -> 正立面/侧立面/平面 三图"""
import argparse
import json
import math
import os
ap = argparse.ArgumentParser(description='BOM -> 施工图四件套 (手册/29)')
ap.add_argument('bom')
ap.add_argument('--out', default='.')
args = ap.parse_args()
BOM_PATH, OUT_DIR = args.bom, args.out
bom = json.load(open(BOM_PATH, encoding='utf-8'))
PARTS = bom['parts']
KD = bom['meta']['key_dimensions']
TOTAL = bom['meta']['total']
VER = bom['meta']['version']

def find(sub):
    return [p for p in PARTS if sub in p['role']]
def one(sub):
    r = find(sub)
    if not r: raise KeyError(sub)
    return r[0]
def box(p):
    """(x0,x1,y0,y1) 由 position/scale(白盒原生1m)"""
    x, y = p['position']['x'], p['position']['y']
    w, h = p['scale'][0], p['scale'][1]
    return (x - w/2, x + w/2, y - h/2, y + h/2)

# ---- 几何推导 ----
H_SPRING = KD['起拱线']
steps = sorted(find('台阶') + find('勒脚'), key=lambda p: p['position']['y'])
pier = one('墩芯骨架')
XW = pier['scale'][0]/2 + abs(pier['position']['x'])          # 墙半宽
DOOR = one('门洞边梃')['position']['x']                        # 门洞净半宽
R1 = math.hypot(find('券石k1')[0]['position']['x'], find('券石k1')[0]['position']['y'] - H_SPRING)
R2 = math.hypot(find('外圈券饰k1')[0]['position']['x'], find('外圈券饰k1')[0]['position']['y'] - H_SPRING)
T1, T2 = find('券石k1')[0]['scale'][1]/2, find('外圈券饰k1')[0]['scale'][1]/2
ARCH_TOP = H_SPRING + R1 - T1
ent_b = box(one('额枋'))[2]                                    # 檐底
attic = one('阁楼芯体'); ab, ad = box(attic), attic['scale'][2]/2
comp = one('阁楼压条'); cb = box(comp)
cap = one('檐口盖线'); ENT_T = box(cap)[3]                     # 檐顶
rood_ridge = one('中央脊饰'); RIDGE_T = box(rood_ridge)[3]
teeth = find('齿饰块')
teeth_x0 = min(t['position']['x'] - t['scale'][0]/2 for t in teeth)
teeth_x1 = max(t['position']['x'] + t['scale'][0]/2 for t in teeth)
teeth_y = teeth[0]['position']['y']; teeth_h = teeth[0]['scale'][1]
cols = {}
for seg in ('高柱座', '柱基', '半柱柱身', '柱颈带', '柱头'):
    cols[seg] = [p for p in find(seg) if p['position']['z'] > 0]
wins = [p for p in find('卫室窗') if p['position']['z'] > 0]
imps = find('起拱横带')
spand = one('拱肩中央墙')
ks = one('拱心石')
frieze = one('横饰带体'); architr = one('额枋')
ledge = one('大檐口'); capline = one('檐口盖线')
panel = one('铭文碑板'); frame = find('碑框')
roofbeam = one('脊梁压顶'); endspires = find('脊端饰')
kx = ks['position']['x']; ky = ks['position']['y']
_pb = box(panel); px0,px1,py0,py1 = _pb
_rb = box(roofbeam); bx0,bx1,by0,by1 = _rb
flags = [p for p in find('角旗') if p['position']['z'] > 0]
_cxb = box(cols['半柱柱身'][0])
cx = cols['半柱柱身'][0]['position']['x']
sy0, sy1 = _cxb[2], _cxb[3]
skinf = find('拱肩贴皮')

# ---- 调色板 / 画布 / 坐标 ----
PAPER='#faf7f2'; WALL='#cfc0a6'; DEEP='#b9a88c'; ARCH='#a89878'; JOINT='#8f7f63'
LIGHT='#ddd0b8'; CORN1='#beb096'; CORN2='#b3a389'; CORN3='#9a8a70'; CORN4='#8f7f63'
VOID='#e9e6df'; ROOF='#4a7a6a'; ROOFD='#3d665a'; RED='#8e2438'; INK='#4a4238'
TXT='#2b2b2b'; GRAY='#7a7a7a'; DIM='#999080'; FONT='Microsoft YaHei, sans-serif'
S = 80.0
CX, GY = 760.0, 1330.0
W, H = 1520, 1560
def X(x): return CX + x*S
def Y(y): return GY - y*S
out=[]
def E(s): out.append(s)
def R(x0,y0,w,h,fill,sw=1.0,stroke=INK):
    E(f'<rect x="{X(x0):.1f}" y="{Y(y0+h):.1f}" width="{w*S:.1f}" height="{h*S:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def L(x1,y1,x2,y2,stroke=INK,sw=1.0,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    E(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" y2="{Y(y2):.1f}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def P(d,fill='none',sw=1.0,stroke=INK):
    E(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def T(x_px,y_px,s,size=8.5,fill=GRAY,anchor='middle',bold=False):
    b=' font-weight="bold"' if bold else ''
    E(f'<text x="{x_px:.1f}" y="{y_px:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-family="{FONT}"{b}>{s}</text>')

def apt(phi, rr):
    a=math.radians(phi); return X(rr*math.cos(a)), Y(H_SPRING+rr*math.sin(a))
def arc_d(rr, stroke=JOINT, sw=0.9):
    phis=[i*7.5 for i in range(25)]
    d='M'+' L'.join(f'{apt(p,rr)[0]:.1f},{apt(p,rr)[1]:.1f}' for p in phis)
    E(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
def band(ri, ro, fill, sw=1.1):
    phis=[i*7.5 for i in range(25)]
    d='M'+' L'.join(f'{apt(p,ro)[0]:.1f},{apt(p,ro)[1]:.1f}' for p in phis[::-1])
    d+=' L'+' L'.join(f'{apt(p,ri)[0]:.1f},{apt(p,ri)[1]:.1f}' for p in phis)+' Z'
    P(d,fill=fill,sw=sw)


def elevation():
    E(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    E(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
    E(f'<rect x="14" y="14" width="{W-28}" height="{H-28}" fill="none" stroke="#d8d2c4" stroke-width="1.2"/>')
    T(W/2, 36, f'凯旋门 {VER} · 圣地大门版 — 正立面施工图', size=17, fill=TXT, bold=True)
    T(W/2, 54, f'千星奇域 A+B 工艺 ｜ BOM {TOTAL} 件 · 左右镜像对称 ｜ 数据源: 凯旋门{VER}_BOM.json ｜ 比例 {S:.0f} px/m', size=9.5, fill=GRAY)
    # 地面
    L(-7.2, 0, 7.2, 0, stroke='#3a332c', sw=2.5)
    E(f'<rect x="{X(-6.55):.0f}" y="{Y(0):.0f}" width="{13.1*S:.0f}" height="4" fill="#ddd8cd"/>')
    # 主体墙 (外轮廓减门洞)
    d=(f'M {X(-XW):.1f},{Y(0.72):.1f} L {X(-XW):.1f},{Y(ent_b):.1f} L {X(XW):.1f},{Y(ent_b):.1f} '
       f'L {X(XW):.1f},{Y(0.72):.1f} L {X(DOOR):.1f},{Y(0.72):.1f} L {X(DOOR):.1f},{Y(H_SPRING):.1f} ')
    phis=[i*7.5 for i in range(25)]
    d+=' L'.join(f'{apt(p,R1-T1)[0]:.1f},{apt(p,R1-T1)[1]:.1f}' for p in phis)
    d+=f' L {X(-DOOR):.1f},{Y(0.72):.1f} Z'
    P(d, fill=WALL, sw=1.4)
    # 台阶
    for st in steps:
        x0,x1,y0,y1 = box(st)
        fill = CORN1 if '盖顶' in st['role'] else '#c2b499'
        R(x0, y0, x1-x0, y1-y0, fill, sw=0.9)
    L(-XW, 0.72, XW, 0.72, stroke='#a89a80', sw=0.7)
    # 拱肩凹入区
    sx0,sx1,sy0,sy1 = box(spand)
    R(sx0, sy0, sx1-sx0, sy1-sy0, DEEP, sw=0.8)
    for sk in skinf:
        if sk['position']['z']>0:
            a0,a1,b0,b1 = box(sk); R(a0,b0,a1-a0,b1-b0,'#c3b49a',sw=0.7)
    # 拱券: 洞口进深弧 + 双环带 + 放射缝 + 拱心石
    arc_d(R1-T1, stroke='#c9c4bb', sw=1.2)
    arc_d(R1-T1+0.10, stroke='#d8d4cb', sw=0.8)
    band(R1-T1, R1+T1, ARCH)
    band(R2-T2, R2+T2, '#b0a081')
    for k in range(12):
        phi=7.5+15*k
        for rr0,rr1 in ((R1-T1+0.03,R1+T1-0.03),(R2-T2+0.03,R2+T2-0.03)):
            p1=apt(phi,rr0); p2=apt(phi,rr1)
            E(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="{JOINT}" stroke-width="0.8"/>')
    kh=ks['scale'][1]/2; kw=ks['scale'][0]/2
    P(f'M {X(-kw*0.9):.1f},{Y(ky-kh):.1f} L {X(-kw):.1f},{Y(ky+kh):.1f} L {X(kw):.1f},{Y(ky+kh):.1f} L {X(kw*0.9):.1f},{Y(ky-kh):.1f} Z', fill=LIGHT, sw=1.2)
    L(kx-0.28, ky, kx+0.28, ky, stroke=JOINT, sw=0.8)
    # 起拱横带
    for im in imps:
        x0,x1,y0,y1 = box(im); R(x0,y0,x1-x0,y1-y0,CORN1,sw=0.8)
    # 半柱五段 + 凹槽 + 侧影
    for seg,fillc in (('高柱座','#b5a68b'),('柱基',LIGHT),('半柱柱身',LIGHT),('柱颈带',LIGHT),('柱头',LIGHT)):
        for c in cols[seg]:
            x0,x1,y0,y1=box(c)
            R(x0,y0,x1-x0,y1-y0,fillc,sw=0.9)
    for c in cols['半柱柱身']:
        ccx=c['position']['x']; csd=c['scale'][0]/2
        for off in (-0.16,0,0.16): L(ccx+off,sy0+0.12,ccx+off,sy1-0.12,stroke='#b8a98d',sw=0.9)
        E(f'<line x1="{X(ccx+csd):.1f}" y1="{Y(sy1):.1f}" x2="{X(ccx+csd):.1f}" y2="{Y(sy0):.1f}" stroke="#a08f73" stroke-width="1.6"/>')
    # 卫室窗
    for w_ in wins:
        x0,x1,y0,y1 = box(w_); R(x0,y0,x1-x0,y1-y0,VOID,sw=0.8)
        L(w_['position']['x'],y0,w_['position']['x'],y1,stroke='#b8ad9c',sw=0.6)
        L(x0,(y0+y1)/2,x1,(y0+y1)/2,stroke='#b8ad9c',sw=0.6)
    return

def elevation_upper():
    # 檐部四带 + 齿饰
    for piece, fillc in ((architr,CORN1),(frieze,CORN2)):
        x0,x1,y0,y1=box(piece); R(x0,y0,x1-x0,y1-y0,fillc,sw=0.9)
    n_t=len(teeth)
    for t in [t for t in teeth if t['position']['z']>0]:
        x0,x1,y0,y1=box(t); R(x0,y0,x1-x0,y1-y0,'#a4947a',sw=0.5,stroke='#93836a')
    for piece, fillc in ((ledge,CORN3),(capline,CORN4)):
        x0,x1,y0,y1=box(piece); R(x0,y0,x1-x0,y1-y0,fillc,sw=0.9)
    L(box(ledge)[0], box(ledge)[2], box(ledge)[1], box(ledge)[2], stroke='#7d6e57', sw=1.2)
    # 阁楼 + 碑板 + 框
    x0,x1,y0,y1=box(attic); R(x0,y0,x1-x0,y1-y0,WALL,sw=0.9)
    fw=0.19
    R(px0-fw,py0-fw,px1-px0+2*fw,py1-py0+2*fw,LIGHT,sw=0.9)
    R(px0,py0,px1-px0,py1-py0,DEEP,sw=0.7)
    for i,ly in enumerate((py0+0.26, (py0+py1)/2, py1-0.26)):
        L(px0+0.28,ly,px1-0.28,ly,stroke='#a89a7f',sw=0.7)
    x0,x1,y0,y1=box(comp); R(x0,y0,x1-x0,y1-y0,CORN3,sw=0.9)
    cl=one('阁楼压条盖线'); x0,x1,y0,y1=box(cl); R(x0,y0,x1-x0,y1-y0,CORN4,sw=0.6)
    # 屋顶
    R(bx0,by0,bx1-bx0,by1-by0,ROOFD,sw=0.9)
    for sxx in (1,-1):
        E(f'<line x1="{X(sxx*(bx1)):.1f}" y1="{Y(by0):.1f}" x2="{X(0):.1f}" y2="{Y(by1):.1f}" stroke="{ROOF}" stroke-width="4" stroke-linecap="round"/>')
    R(bx0-0.08, by0-0.05, bx1-bx0+0.16, 0.10, ROOF, sw=0.6)
    for es in endspires:
        ex,ey=es['position']['x'],es['position']['y']
        R(ex-0.25,ey-0.225,0.5,0.45,RED,sw=0.8); L(ex,ey-0.225,ex,ey-0.55,stroke='#6b5a44',sw=1.0)
    rx,ry=rood_ridge['position']['x'],rood_ridge['position']['y']
    rw,rh=rood_ridge['scale'][0]/2,rood_ridge['scale'][1]/2
    P(f'M {X(rx):.1f},{Y(ry+rh):.1f} L {X(rx-rw*0.6):.1f},{Y(ry+rh-0.16):.1f} L {X(rx+rw*0.6):.1f},{Y(ry+rh-0.16):.1f} Z', fill=RED, sw=0.7)
    # 角旗 x2 (投影)
    for fl in flags:
        fx=fl['position']['x']; fy=fl['position']['y']+fl['scale'][1]/2
        L(fx, 10.63+DY_PROJ(), fx, fy, stroke='#6b5a44', sw=1.5)
        E(f'<path d="M {X(fx):.1f},{Y(fy-0.03):.1f} L {X(fx+0.52):.1f},{Y(fy-0.19):.1f} L {X(fx):.1f},{Y(fy-0.35):.1f} Z" fill="{RED}" stroke="{INK}" stroke-width="0.6"/>')

_DY = None
def DY_PROJ():
    global _DY
    if _DY is None:
        _DY = one('额枋')['position']['y'] - 9.225 if VER == 'v4' else 0.0
    return _DY

def elevation_anno():
    # 尺寸: 总宽 / 门洞净宽
    def dim_h(xa, xb, y_px, label, size=9.5):
        E(f'<line x1="{X(xa):.1f}" y1="{y_px}" x2="{X(xb):.1f}" y2="{y_px}" stroke="{DIM}" stroke-width="0.9"/>')
        for xx in (xa,xb):
            E(f'<line x1="{X(xx)-4:.1f}" y1="{y_px+4:.1f}" x2="{X(xx)+4:.1f}" y2="{y_px-4:.1f}" stroke="{DIM}" stroke-width="0.9"/>')
        T((X(xa)+X(xb))/2, y_px-5, label, size=size, fill=GRAY)
    tw=steps[0]['scale'][0]/2
    dim_h(-tw, tw, GY+28, '%.2f m (台阶总宽)'%(2*tw), size=10)
    dim_h(-DOOR, DOOR, GY+56, '%.2f m (门洞净宽)'%(2*DOOR))
    # 右侧标高
    gx=X(7.0)
    E(f'<line x1="{gx:.1f}" y1="{Y(0):.1f}" x2="{gx:.1f}" y2="{Y(RIDGE_T+0.3):.1f}" stroke="{DIM}" stroke-width="0.9"/>')
    lv=[(0.00,'地面'),(0.72,'台面'),(H_SPRING,'起拱线'),(ARCH_TOP,'拱冠内顶'),
        (ent_b,'檐底'),(ENT_T,'檐顶'),(cb[3],'阁楼顶'),(RIDGE_T,'脊顶')]
    for l,nm in lv:
        E(f'<line x1="{gx-5:.1f}" y1="{Y(l):.1f}" x2="{gx+5:.1f}" y2="{Y(l):.1f}" stroke="{DIM}" stroke-width="0.9"/>')
        T(gx+10, Y(l)+3, '%.2f  %s'%(l,nm), size=8, fill=GRAY, anchor='start')
    # 左侧层名
    LC=bom['meta']['layer_counts']
    layers=[('① 基座层', 0.40),('② 墩身层·柱式', PCY_PROJ()),('③ 拱券层', H_SPRING+1.4),
            ('④ 檐部层', ent_b+1.0),('⑤ 阁楼层', ab[2]+ (ab[3]-ab[2])/2 - ab[2] + ab[2]),('⑥ 屋顶+旗', RIDGE_T-0.4)]
    layers=[(a, PCY_PROJ() if '墩身' in a else b) for a,b in layers]
    for i,(nm,lvv) in enumerate(layers):
        cnt = list(LC.values())[i] if i < len(LC) else 0
        E(f'<line x1="{X(-7.0):.1f}" y1="{Y(lvv):.1f}" x2="{X(-6.6):.1f}" y2="{Y(lvv):.1f}" stroke="{DIM}" stroke-width="0.8" stroke-dasharray="3,3"/>')
        E(f'<circle cx="{X(-6.6):.1f}" cy="{Y(lvv):.1f}" r="2.2" fill="{DIM}"/>')
        T(X(-7.0)-6, Y(lvv)+3.5, '%s (%d件)'%(nm,cnt), size=9.5, fill=TXT, anchor='end')
    # 资产标注
    def note(px_x,px_y,tx,ty,s):
        E(f'<line x1="{px_x:.1f}" y1="{px_y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{DIM}" stroke-width="0.7"/>')
        E(f'<circle cx="{px_x:.1f}" cy="{px_y:.1f}" r="2" fill="{DIM}"/>')
        T(tx, ty+3, s, size=8, fill=GRAY, anchor='start' if tx>px_x else 'end')
    note(X(-4.6),Y(PCY_PROJ()), X(-7.0), Y(PCY_PROJ())+14, '墩身贴皮 石质墙壁20001337')
    note(X(cx+0.5),Y(sy1-0.2), X(cx+1.0), Y(sy1+0.3), '半柱五段 白盒10009001/10009008')
    note(X(R2+0.2),Y(H_SPRING+0.6), X(R2+0.8), Y(H_SPRING+0.2), '券石×%d+外圈饰×%d' % (len(find('券石k')), len(find('外圈券饰k'))))
    note(X(kx+0.45),Y(ky+0.4), X(kx+0.9), Y(ky+0.75), '拱心石(凸出)')
    note(X(teeth_x1-0.3),Y(teeth_y), X(teeth_x1+0.6), Y(teeth_y)+6, '齿饰块×%d'%len(teeth))
    note(X(px0-0.3),Y(py1), X(px0-0.8), Y(py1)-10, '铭文碑板(凹色)')
    note(X(1.2),Y(by1), X(1.7), Y(by1)-6, '瓦坡20002120(本色)')
    note(X(wins[0]['position']['x']),Y(box(wins[0])[3]), X(wins[0]['position']['x']-0.6), Y(box(wins[0])[3])+22, '卫室窗20002154')
    # 图例
    leg=[(WALL,'墙体·墩身/拱上墙'),(DEEP,'凹入·贴皮'),(ARCH,'拱券带'),(LIGHT,'半柱·凸出件'),
         (CORN3,'檐部·齿饰'),(ROOF,'瓦坡屋顶'),(RED,'旗·脊饰')]
    lx0,ly0=90,H-96
    for i,(c,nm) in enumerate(leg):
        xx=lx0+i*140
        E(f'<rect x="{xx:.1f}" y="{ly0:.1f}" width="18" height="11" fill="{c}" stroke="{INK}" stroke-width="0.7"/>')
        T(xx+24, ly0+9.5, nm, size=8.5, fill=TXT, anchor='start')
    T(lx0, ly0+30, 'A+B 工艺: 白盒骨架(10009001/10009008/10009006) + 石纹贴皮切片(20001337/20001335/20002158) + 本色件(窗/瓦/旗) ｜ generated by archdraw', size=8.5, fill=GRAY, anchor='start')
    T(W-90, H-40, 'archdraw · 千星奇域', size=8, fill='#b0a89a', anchor='end')
    E('</svg>')
    p=os.path.join(OUT_DIR, '凯旋门%s_正立面图.svg'%VER)
    open(p,'w',encoding='utf-8').write('\n'.join(out))
    print('written:', p, len(out),'elements')

def PCY_PROJ():
    return pier['position']['y']

elevation(); elevation_upper(); elevation_anno()

def draw_side():
    S2=44.0; CX2, GY2 = 430.0, 720.0; W2, H2 = 860, 860
    o=[]
    def Xs(z): return CX2 + z*S2
    def Ys(y): return GY2 - y*S2
    def R2(z0,y0,w,h,fill,sw=1.0,stroke=INK):
        o.append(f'<rect x="{Xs(z0):.1f}" y="{Ys(y0+h):.1f}" width="{w*S2:.1f}" height="{h*S2:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    def L2(z1,y1,z2,y2,stroke=INK,sw=1.0):
        o.append(f'<line x1="{Xs(z1):.1f}" y1="{Ys(y1):.1f}" x2="{Xs(z2):.1f}" y2="{Ys(y2):.1f}" stroke="{stroke}" stroke-width="{sw}"/>')
    def T2(x,y,s,size=8.5,fill=GRAY,anchor='middle',bold=False):
        b=' font-weight="bold"' if bold else ''
        o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-family="{FONT}"{b}>{s}</text>')
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W2}" height="{H2}" viewBox="0 0 {W2} {H2}">')
    o.append(f'<rect width="{W2}" height="{H2}" fill="{PAPER}"/>')
    o.append(f'<rect x="12" y="12" width="{W2-24}" height="{H2-24}" fill="none" stroke="#d8d2c4" stroke-width="1.2"/>')
    T2(W2/2, 36, f'凯旋门 {VER} · 侧立面图（东面）', size=15, fill=TXT, bold=True)
    T2(W2/2, 54, '进深 5.0 m (台阶) / 3.2 m (墙体) ｜ 同一套 BOM 的侧向投影', size=9, fill=GRAY)
    L2(-3.1, 0, 3.1, 0, stroke='#3a332c', sw=2.2)
    for st in steps:
        x0,x1,y0,y1 = box(st)
        d = st['scale'][2]/2
        fill = CORN1 if '盖顶' in st['role'] else '#c2b499'
        R2(-d, y0, 2*d, y1-y0, fill, sw=0.9)
    # 墙体大块 (墩身+拱上墙同深)
    R2(-1.6, 0.72, 3.2, ent_b-0.72, WALL, sw=1.2)
    # 暗龛木窗板 (侧立面主装饰)
    PCYp = pier['position']['y']; PIERHp = pier['scale'][1]
    R2(-1.6, PCYp-PIERHp/2, 3.2, PIERHp, DEEP, sw=0.8)
    o.append(f'<rect x="{Xs(-1.6):.1f}" y="{Ys(PCYp+PIERHp/2)+6:.1f}" width="{3.2*S2:.1f}" height="{PIERHp*S2-12:.1f}" fill="none" stroke="#a08f73" stroke-width="0.8"/>')
    for zz in (-1.0, 0, 1.0): L2(zz, PCYp-PIERHp/2+0.1, zz, PCYp+PIERHp/2-0.1, stroke='#a89a80', sw=0.6)
    # 檐部
    for piece, fillc in ((architr,CORN1),(frieze,CORN2),(ledge,CORN3),(capline,CORN4)):
        x0,x1,y0,y1=box(piece); d=piece['scale'][2]/2
        R2(-d, y0, 2*d, y1-y0, fillc, sw=0.9)
    # 齿饰带(侧向一排)
    for t in [t for t in teeth if t['position']['x']>0.3 and t['position']['z']>0]:
        y0,y1=box(t)[2],box(t)[3]; R2(-1.5, y0, 0.24, y1-y0, '#a4947a', sw=0.5, stroke='#93836a')
        R2(1.26, y0, 0.24, y1-y0, '#a4947a', sw=0.5, stroke='#93836a')
    # 阁楼 + 压条
    for piece, fillc in ((attic,WALL),(comp,CORN3)):
        x0,x1,y0,y1=box(piece); d=piece['scale'][2]/2
        R2(-d, y0, 2*d, y1-y0, fillc, sw=0.9)
    cl=one('阁楼压条盖线'); x0,x1,y0,y1=box(cl); R2(-cl['scale'][2]/2, y0, cl['scale'][2], y1-y0, CORN4, sw=0.6)
    # 屋顶侧影: 脊梁 + 瓦坡断面三角
    R2(-0.6, by0, 1.2, by1-by0, ROOFD, sw=0.9)
    o.append(f'<path d="M {Xs(-0.6):.1f},{Ys(by0):.1f} L {Xs(0):.1f},{Ys(by0+0.9):.1f} L {Xs(0.6):.1f},{Ys(by0):.1f}" fill="{ROOF}" stroke="{INK}" stroke-width="1"/>')
    for es in endspires:
        ez=0; ey=es['position']['y']; R2(ez-0.25, ey-0.225, 0.5, 0.45, RED, sw=0.8)
    T2(CX2, Ys(RIDGE_T)-10, '脊饰 顶点 %.2f m'%RIDGE_T, size=8)
    # 标高
    gx=Xs(2.35)
    o.append(f'<line x1="{gx:.1f}" y1="{Ys(0):.1f}" x2="{gx:.1f}" y2="{Ys(RIDGE_T+0.3):.1f}" stroke="{DIM}" stroke-width="0.9"/>')
    for l,nm in [(0.00,'地面'),(0.72,'台面'),(H_SPRING,'起拱线'),(ent_b,'檐底'),(RIDGE_T,'脊顶')]:
        o.append(f'<line x1="{gx-4:.1f}" y1="{Ys(l):.1f}" x2="{gx+4:.1f}" y2="{Ys(l):.1f}" stroke="{DIM}" stroke-width="0.9"/>')
        T2(gx+8, Ys(l)+3, '%.2f %s'%(l,nm), size=8, fill=GRAY, anchor='start')
    def dim_h(za, zb, y_px, label):
        o.append(f'<line x1="{Xs(za):.1f}" y1="{y_px}" x2="{Xs(zb):.1f}" y2="{y_px}" stroke="{DIM}" stroke-width="0.9"/>')
        for zz in (za,zb):
            o.append(f'<line x1="{Xs(zz)-4:.1f}" y1="{y_px+4:.1f}" x2="{Xs(zz)+4:.1f}" y2="{y_px-4:.1f}" stroke="{DIM}" stroke-width="0.9"/>')
        T2((Xs(za)+Xs(zb))/2, y_px-5, label, size=9)
    dim_h(-2.5, 2.5, GY2+26, '5.00 m (台阶进深)')
    dim_h(-1.6, 1.6, GY2+50, '3.20 m (墙体进深)')
    T2(60, H2-40, '注: 侧立面主装饰=暗龛木窗板20001377(通高) ｜ archdraw', size=8, fill='#b0a89a', anchor='start')
    o.append('</svg>')
    p=os.path.join(OUT_DIR, '凯旋门%s_侧立面图.svg' % VER)
    open(p,'w',encoding='utf-8').write('\n'.join(o)); print('written:', p)
draw_side()

def draw_plan():
    S3=80.0; CX3, CZ3 = 460.0, 420.0; W3, H3 = 900, 860
    o=[]
    def Xp(x): return CX3 + x*S3
    def Zp(z): return CZ3 - z*S3
    def R3(x0,z0,w,d,fill,sw=1.0,stroke=INK,dash=None):
        dd=f' stroke-dasharray="{dash}"' if dash else ''
        o.append(f'<rect x="{Xp(x0):.1f}" y="{Zp(z0+d)-0:1f}" width="{w*S3:.1f}" height="{d*S3:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dd}/>')
    def R3f(x0,z0,w,d,fill,sw=1.0,stroke=INK,dash=None):
        dd=f' stroke-dasharray="{dash}"' if dash else ''
        o.append(f'<rect x="{Xp(x0):.1f}" y="{Zp(z0):.1f}" width="{w*S3:.1f}" height="{d*S3:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dd}/>')
    def T3(x,y,s,size=8.5,fill=GRAY,anchor='middle',bold=False):
        b=' font-weight="bold"' if bold else ''
        o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-family="{FONT}"{b}>{s}</text>')
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W3}" height="{H3}" viewBox="0 0 {W3} {H3}">')
    o.append(f'<rect width="{W3}" height="{H3}" fill="{PAPER}"/>')
    o.append(f'<rect x="12" y="12" width="{W3-24}" height="{H3-24}" fill="none" stroke="#d8d2c4" stroke-width="1.2"/>')
    T3(W3/2, 36, f'凯旋门 {VER} · 平面图', size=15, fill=TXT, bold=True)
    T3(W3/2, 54, '俯视投影 ｜ 门洞通道沿南北(z)向 ｜ 柱=半柱贴墙(投影圆)', size=9, fill=GRAY)
    # 台阶 (俯视外框)
    for st in steps:
        w=st['scale'][0]; d=st['scale'][2]
        fill = CORN1 if '盖顶' in st['role'] else '#c2b499'
        R3f(-w/2, d/2, w, d, fill, sw=0.9)
    # 墙体轮廓 (挖门洞): 门洞 = x(-DOOR,DOOR) 贯穿 z
    for sx in (1,-1):
        R3f(DOOR if sx<0 else -XW, 1.6, XW-DOOR, -3.2, WALL, sw=1.2) if False else R3f(-XW if sx<0 else DOOR, 1.6, XW-DOOR, 3.2, WALL, sw=1.2)
    # 门洞地面 (台阶顶面)
    R3f(-DOOR, 1.6, 2*DOOR, 3.2, '#d8d2c4', sw=0.6, stroke='#b0a89a')
    # 柱 x4
    for c in find('半柱柱身'):
        x,z=c['position']['x'],c['position']['z']; r=c['scale'][0]/2
        o.append(f'<circle cx="{Xp(x):.1f}" cy="{Zp(z):.1f}" r="{r*S3:.1f}" fill="{LIGHT}" stroke="{INK}" stroke-width="1"/>')
    # 暗龛/卫室窗标记
    for w_ in find('卫室窗'):
        x,z=w_['position']['x'],w_['position']['z']
        R3f(x-0.32, z+0.05 if z>0 else z-0.37, 0.64, 0.32, VOID, sw=0.6)
    T3(Xp(4.85), Zp(1.9)-4, '卫室窗', size=7.5)
    # 阁楼投影 (虚线)
    R3f(-attic['scale'][0]/2, attic['scale'][2]/2, attic['scale'][0], attic['scale'][2], 'none', sw=0.9, stroke='#8f7f63', dash='5,4')
    T3(Xp(0), Zp(1.42), '阁楼边线(上方)', size=7.5, fill='#8f7f63')
    # 屋顶小脊
    R3f(-roofbeam['scale'][0]/2, roofbeam['scale'][2]/2, roofbeam['scale'][0], roofbeam['scale'][2], ROOFD, sw=0.9)
    T3(Xp(0), Zp(0)+3, '脊梁', size=7.5, fill='#e8e2d5')
    # 通行箭头
    o.append(f'<path d="M {Xp(0):.1f},{Zp(-2.9):.1f} L {Xp(0):.1f},{Zp(2.9):.1f}" stroke="{RED}" stroke-width="1.6" marker-end="url(#ar)"/>')
    o.append('<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="%s"/></marker></defs>'%RED)
    T3(Xp(0.4), Zp(2.6), '通行向', size=8, fill=RED, anchor='start')
    # 尺寸
    def dim_w(xa, xb, y_px, label):
        o.append(f'<line x1="{Xp(xa):.1f}" y1="{y_px}" x2="{Xp(xb):.1f}" y2="{y_px}" stroke="{DIM}" stroke-width="0.9"/>')
        for xx in (xa,xb):
            o.append(f'<line x1="{Xp(xx)-4:.1f}" y1="{y_px+4:.1f}" x2="{Xp(xx)+4:.1f}" y2="{y_px-4:.1f}" stroke="{DIM}" stroke-width="0.9"/>')
        T3((Xp(xa)+Xp(xb))/2, y_px-5, label, size=9)
    tw=steps[0]['scale'][0]/2
    dim_w(-tw, tw, Zp(-2.5)+30, '12.90 m (台阶总宽)')
    dim_w(-DOOR, DOOR, Zp(-1.6)-14, '5.50 m (门洞净宽)')
    T3(60, H3-40, 'A+B 工艺 ｜ 白盒骨架+贴皮切片 ｜ archdraw', size=8, fill='#b0a89a', anchor='start')
    o.append('</svg>')
    p=os.path.join(OUT_DIR, '凯旋门%s_平面图.svg' % VER)
    open(p,'w',encoding='utf-8').write('\n'.join(o)); print('written:', p)
draw_plan()

n_ring = len(find("券石k")); ring_pitch = 180.0 / n_ring
n_ring = len(find('券石k')); ring_pitch = 180.0 / n_ring

S4 = 150.0
CX4, CY4 = 560.0, 880.0        # 拱圆心的像素位
W4, H4 = 1180, 1000
def Xp(x): return CX4 + x*S4
def Yp(y): return CY4 - (y - H_SPRING)*S4    # 以起拱线为基准

o=[]
def E4(s): o.append(s)
def T4(x,y,s,size=9,fill=GRAY,anchor='middle',bold=False,rot=None):
    b=' font-weight="bold"' if bold else ''
    r=f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ''
    E4(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-family="{FONT}"{b}{r}>{s}</text>')

E4(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W4}" height="{H4}" viewBox="0 0 {W4} {H4}">')
E4(f'<rect width="{W4}" height="{H4}" fill="{PAPER}"/>')
E4(f'<rect x="14" y="14" width="{W4-28}" height="{H4-28}" fill="none" stroke="#d8d2c4" stroke-width="1.2"/>')
T4(W4/2, 40, '凯旋门 %s · 拱券大样图 (1:20)' % VER, size=17, fill=TXT, bold=True)
T4(W4/2, 60, '拱 = 旋转白盒拼装: 内圈券石×%d(通深3.2m) + 外圈券饰×%d(双面) + 拱心石×2 ｜ 三轴Z旋转(P2判例)' % (n_ring, 2*n_ring), size=9.5, fill=GRAY)

# ---- 背景墙体 (示意) ----
E4(f'<rect x="{Xp(-3.6):.0f}" y="{Yp(10.1):.0f}" width="{7.2*S4:.0f}" height="{(10.1-3.6)*S4:.0f}" fill="{WALL}" opacity="0.35" stroke="none"/>')
# 拱洞
E4(f'<path d="M {Xp(-R1+0.225):.1f},{Yp(H_SPRING):.1f} L {Xp(-R1+0.225):.1f},{Yp(3.6):.1f} L {Xp(R1-0.225):.1f},{Yp(3.6):.1f} L {Xp(R1-0.225):.1f},{Yp(H_SPRING):.1f} A {((R1-0.225)*S4):.1f} {((R1-0.225)*S4):.1f} 0 0 1 {Xp(R1-0.225):.1f},{Yp(H_SPRING):.1f} Z" fill="{VOID}" stroke="{INK}" stroke-width="1.2"/>')

# ---- 内圈券石 ×12: 逐块 rotated rect ----
inner_stones = sorted(find('券石k'), key=lambda p: p['position']['x'])
for i, st in enumerate(inner_stones):
    x, y = st['position']['x'], st['position']['y']
    w, t = st['scale'][0], st['scale'][1]
    rz = st['rotation']['z']
    phi = 90 - rz
    fill = ARCH if i % 2 == 0 else '#b0a081'
    cx, cy = Xp(x), Yp(y)
    E4(f'<rect x="{cx - w*S4/2:.1f}" y="{cy - t*S4/2:.1f}" width="{w*S4:.1f}" height="{t*S4:.1f}" fill="{fill}" stroke="{INK}" stroke-width="1.1" transform="rotate({rz:.1f} {cx:.1f} {cy:.1f})"/>')
    if i % max(1, n_ring//6) == 0 or i == n_ring - 1:
        T4(cx, cy+4, 'k%d' % (i+1), size=8.5, fill='#5a4f3e', rot=rz)
# ---- 外圈券饰: 南面 12 块 ----
outer_stones = sorted([p for p in find('外圈券饰k') if p['position']['z'] > 0], key=lambda p: p['position']['x'])
for i, st in enumerate(outer_stones):
    x, y = st['position']['x'], st['position']['y']
    w, t = st['scale'][0], st['scale'][1]
    rz = st['rotation']['z']
    fill = '#bcae92' if i % 2 == 0 else '#c6b899'
    cx, cy = Xp(x), Yp(y)
    E4(f'<rect x="{cx - w*S4/2:.1f}" y="{cy - t*S4/2:.1f}" width="{w*S4:.1f}" height="{t*S4:.1f}" fill="{fill}" stroke="{INK}" stroke-width="1.1" transform="rotate({rz:.1f} {cx:.1f} {cy:.1f})"/>')
# ---- 拱心石 ----
ksh = ks['scale'][1]; ksw = ks['scale'][0]
E4(f'<rect x="{Xp(kx)-ksw*S4/2:.1f}" y="{Yp(ky)-ksh*S4/2:.1f}" width="{ksw*S4:.1f}" height="{ksh*S4:.1f}" fill="{LIGHT}" stroke="{INK}" stroke-width="1.4"/>')
T4(Xp(kx), Yp(ky)+5, '拱心石 0.80×0.90', size=9.5, fill=TXT, bold=True)

# ---- 圆心 / 半径 / 角度标注 ----
E4(f'<circle cx="{Xp(0):.1f}" cy="{Yp(H_SPRING):.1f}" r="4" fill="{RED}"/>')
E4(f'<line x1="{Xp(0)-14:.1f}" y1="{Yp(H_SPRING):.1f}" x2="{Xp(0)+14:.1f}" y2="{Yp(H_SPRING):.1f}" stroke="{RED}" stroke-width="1"/>')
E4(f'<line x1="{Xp(0):.1f}" y1="{Yp(H_SPRING)-14:.1f}" x2="{Xp(0):.1f}" y2="{Yp(H_SPRING)+14:.1f}" stroke="{RED}" stroke-width="1"/>')
T4(Xp(0)+12, Yp(H_SPRING)+18, '圆心=起拱线 y=%.2f' % H_SPRING, size=8.5, fill=RED, anchor='start')
# 半径线 (φ=45° 方向)
for rr, lab in ((R1, 'R1=%.3f m (内圈中径)' % R1), (R2, 'R2=%.3f m (外圈中径)' % R2)):
    ex, ey = Xp(rr*math.cos(math.radians(45))), Yp(H_SPRING + rr*math.sin(math.radians(45)))
    E4(f'<line x1="{Xp(0):.1f}" y1="{Yp(H_SPRING):.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{DIM}" stroke-width="0.9" stroke-dasharray="6,3"/>')
    T4((Xp(0)+ex)/2+8, (Yp(H_SPRING)+ey)/2, lab, size=8.5, fill=GRAY, anchor='start', rot=-45)
# φ 角度放射线 (每 30°)
for ang in range(0, 181, 30):
    a = math.radians(ang)
    x1, y1 = Xp((R1-0.5)*math.cos(a)), Yp(H_SPRING+(R1-0.5)*math.sin(a))
    x2, y2 = Xp((R2+0.55)*math.cos(a)), Yp(H_SPRING+(R2+0.55)*math.sin(a))
    E4(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{DIM}" stroke-width="0.7" stroke-dasharray="3,3"/>')
    xl, yl = Xp((R2+0.85)*math.cos(a)), Yp(H_SPRING+(R2+0.85)*math.sin(a))
    T4(xl, yl+3, 'φ=%d°' % ang, size=8, fill=GRAY)

# ---- 右侧: 券石规格表 + 通道剖面小样 ----
tx = 880
T4(tx, 130, '券石规格 (三轴Z旋转 rot_z = 90°−φ)', size=10, fill=TXT, bold=True)
rows = [('构件', '尺寸(m)', '数量', '染色'), ('内圈券石', '0.85×0.45×3.20' if VER=='v4' else '0.42×0.45×3.20', str(len(find('券石k'))), '④暗'),
        ('外圈券饰', '0.90×0.40×0.50' if VER=='v4' else '0.48×0.40×0.50', str(len(find('外圈券饰k'))), '②亮'), ('拱心石', '0.90×0.95×0.60' if VER=='v5' else '0.80×0.90×0.60', '2', '①最亮')]
for ri, row in enumerate(rows):
    yy = 150 + ri*22
    for ci, cell in enumerate(row):
        fill = TXT if ri == 0 else GRAY
        bold = ri == 0
        T4(tx-110+ci*82, yy, cell, size=8.5, fill=fill, anchor='start', bold=bold)
E4(f'<rect x="{tx-118:.0f}" y="{136:.0f}" width="330" height="86" fill="none" stroke="#d8d2c4" stroke-width="1"/>')
E4(f'<line x1="{tx-118:.0f}" y1="150" x2="{tx+212:.0f}" y2="150" stroke="#d8d2c4" stroke-width="1"/>')
T4(tx-110, 258, '全部 = 白盒10009001 长方体', size=8.5, fill=GRAY, anchor='start')
T4(tx-110, 274, 'rot_z 逐块: 步进%.1f° (%d 块/圈)' % (ring_pitch, n_ring), size=8.5, fill=GRAY, anchor='start')
T4(tx-110, 290, '弧长槽位: 内圈 %.3f m/块 → 石宽咬合闭缝' % (2*math.pi*R1/(2*n_ring)), size=8.5, fill=GRAY, anchor='start')

# 通道剖面小样 (过拱冠的竖剖)
T4(tx, 330, '门洞通道剖面 (过拱冠, 南北向)', size=10, fill=TXT, bold=True)
py0 = 350
ps = 42.0
E4(f'<rect x="{tx-70:.0f}" y="{py0:.0f}" width="{3.2*ps:.0f}" height="{5.5*ps:.0f}" fill="none" stroke="#d8d2c4" stroke-width="0"/>')
# 拱腹弧 (通道顶)
E4(f'<path d="M {tx-70:.0f},{py0+2.1*ps:.0f} A {2.75*ps:.0f} {2.75*ps:.0f} 0 0 1 {tx-70+3.2*ps:.0f},{py0+2.1*ps:.0f}" fill="{VOID}" stroke="{INK}" stroke-width="1.2"/>')
E4(f'<rect x="{tx-70:.0f}" y="{py0+2.1*ps:.0f}" width="{3.2*ps:.0f}" height="{3.4*ps:.0f}" fill="{VOID}" stroke="{INK}" stroke-width="1.2"/>')
# 内圈通深券石带 (弧形带)
E4(f'<path d="M {tx-70:.0f},{py0+2.1*ps:.0f} A {2.75*ps:.0f} {2.75*ps:.0f} 0 0 1 {tx-70+3.2*ps:.0f},{py0+2.1*ps:.0f} L {tx-70+3.2*ps:.0f},{py0+2.1*ps-1:.0f} A {(2.75*ps+0.45*ps):.0f} {(2.75*ps+0.45*ps):.0f} 0 0 0 {tx-70:.0f},{py0+2.1*ps-1:.0f} Z" fill="{ARCH}" stroke="{INK}" stroke-width="0.9"/>')
# 外圈饰带 (两端)
for sxx in (0, 1):
    bx = tx-70 + sxx*(3.2*ps-0.5*ps)
    E4(f'<rect x="{bx:.0f}" y="{py0+1.2*ps:.0f}" width="{0.5*ps:.0f}" height="{0.75*ps:.0f}" fill="#bcae92" stroke="{INK}" stroke-width="0.8"/>')
T4(tx-70, py0+5.75*ps+16, '内圈券石通深3.2m(拱腹) · 外圈饰贴两面(z=±1.70)', size=8, fill=GRAY, anchor='start')
T4(tx-70, py0+2.0*ps, '净宽5.50', size=7.5, fill=GRAY)
T4(tx-70+1.6*ps, py0+4.6*ps, '通行向', size=8, fill=RED)

# ---- 底部: 定位表 ----
T4(90, 660, '内圈券石定位表 (圆心=门中心·起拱线; X 东 Y 上)', size=10, fill=TXT, bold=True, anchor='start')
hdr = ('k#', 'φ', 'X(m)', 'Y(m)', 'rot_z')
for ci, h in enumerate(hdr):
    T4(90+ci*70, 682, h, size=8.5, fill=TXT, anchor='start', bold=True)
step = max(1, n_ring // 12)
shown = 0
for i, st in enumerate(inner_stones):
    if i % step and i != n_ring - 1:
        continue
    x, y, rz = st['position']['x'], st['position']['y'], st['rotation']['z']
    phi = 90 - rz
    row = ('k%d' % (i+1), '%.1f°' % phi, '%+.2f' % x, '%.2f' % y, '%+.1f°' % rz)
    for ci, cell in enumerate(row):
        T4(90+ci*70, 702+shown*17, cell, size=8.5, fill=GRAY, anchor='start')
    shown += 1
T4(90, 702+shown*17+4, '(每%d块示1, 内圈共%d块)' % (step, n_ring), size=8, fill='#b0a89a', anchor='start')
T4(90, 950, '大样图画法注: 详图逐块画构件 (区别于立面的整体面层画法) ｜ archdraw ｜ source: BOM json', size=8, fill='#b0a89a', anchor='start')
E4('</svg>')
p = os.path.join(OUT_DIR, '凯旋门%s_拱券大样图.svg' % VER)
open(p, 'w', encoding='utf-8').write('\n'.join(o))
print('written:', p)


if __name__ == '__main__':
    import os as _os
    _os.makedirs(OUT_DIR, exist_ok=True)
    elevation(); elevation_upper(); elevation_anno()
    # 大样图由上方模块级代码直接写出；draw_detail 这个函数名不存在（历史遗留引用），
    # 原先写在元组里会在构造元组时抛 NameError 并以非零码退出，故移除。
    for fn in (draw_side, draw_plan):
        try:
            fn()
        except Exception as ex:
            print(type(ex).__name__, '-', ex)
