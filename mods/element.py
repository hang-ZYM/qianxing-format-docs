# -*- coding: utf-8 -*-
"""element.build — 元件构造 + 打包（元件通道固化，案例 #71 / #72，2026-10-14）。

把既有的最小闭环构造器（已实证导入成功）升级为标准模块：
**从零构造 7.1 形态元件体 → 打包元件方言 .gia → 过门禁**。这是"元件路线"的产线入口
（元件体构造环1 + 打包环3 + 门禁环4）。

案例 #72（2026-10-14）：**元件库显示名 = 元件体 f6 槽 cid1 组件的 f11.f1**（空则回退
该 aid 的官方 prefab 名，10008001="元件组"）。故主件体必须由 set_body_name 填入真名，
否则导入后元件库一律显示"元件组"（见 set_body_name）。

═══ 不变量对齐 ═══
  不变量1 禁克隆：元件体**从官方 prefab 模板从零生成**（synth.load_template），不读任何既有
        元件包字节作输出源；编辑器自产的 `元件组.gia` 仅用于结构对拍（只读）。
  不变量2 新方言先给门禁覆盖：门禁是 trial_gate（已含 _element_checks + 并入的 _check_element_body）。
  不变量3 门禁必走：后验 = 元件体门禁 + .gia 包门禁 + roundtrip，任一不过 → ModuleRejected，
        不落盘新版本、不入 oplog 的 ok 行。
  不变量6 金标准版本：CURRENT_VERSION='7.1.0'（案例 #71/#51）。

═══ 元件体形态（7.1 正典，1073742029.gil f4 / 元件组.gia f11.f1 逐字节相等）═══
  元件组主件（aid 10008001）：{f1:元件guid, f2:10008001(裸), f6:游戏组件槽, f7:编辑组件槽,
                              f8:行为组件槽, f9:3, f10:1}；f6.cid61/f65 = 成员摆放表。
  **f6 槽 cid1 组件 = 名字组件**（f11.f1 = UTF-8 显示名；`0801 5a<len> 0a<slen> <name>`）——
  编辑器「元件库」显示名的权威来源；**空则回退该 aid 的官方 prefab 名**（10008001="元件组"）。
  模板直映路恒给空名（模板 `0801 5a00`）⇒ 必须由 set_body_name 填真名（2026-10-14 定案，
  否则库内 9 件全显示"元件组"）。见 set_body_name/read_body_name。
  成员（aid = 官方 prefab）：{f1:元件guid, f2:aid(裸), f6/f7/f8, f10:1}（物件元件无 f9）。
  构造两条路（两条都已实证/对拍）：
    ①模板直映（无实例数据）—— 模板.f6/f7/f8 直映元件.f6/f7/f8 + {f1,f2,f9?,f10}。
      （实体体是模板 f6→f5/f7→f6/f8→f7 平移一层——两方言分水岭）
    ②实例数据路（有 scale/rot/color/name）—— synth 造实体体后**槽位平移**：
      entity.f5→elem.f6（去实例态 cid19/52）、entity.f6→elem.f7、entity.f7→elem.f8，
      f2 改裸 aid + 补 f10。cid 序列与真实样本成员逐项吻合（本次对拍实证）。

═══ 四要素 ═══
  前置（PreconditionError，不计失败换路）：name 合法 / members 形态 / aid 有官方模板 /
    kind 合法 / 成员数 ≤ MEMBER_LIMIT（纯溢出保护；原"240"常数来自旧方言实测，未证实）/ guid 段位（给值时）。
  执行（确定性）：分配 guid（None → P.alloc_guids 台账）→ 逐成员造元件体 → 主件造体 + 填 cid61
    摆放表 → 组 AssetBundle（f1×1 主件 + f2×N 成员 + f3 元数据四段尾横杠 + f5 '7.1.0'）→ 落 out_dir。
  后验（ModuleRejected）：roundtrip 字节守恒 + 元件体门禁（trial_gate._check_element_body）+
    .gia 包门禁（asset.run_trial_gate，TRIAL_SICK 拦）。不落 .gil 版本（.gia 版本归属未定案）。
  Result：artifact=.gia 路径；value={path, count, guids, kind}；checks 记账。

═══ 调用 ═══
  r = element.build(members=[{"aid":10009001, "pos":(0,0,0)}], name="最小元件_test1")
  r = element.build(members=[{"aid":10009001,"pos":(x,z,y),"scale":(..),"rot":(rx,ry,rz),
                              "color":(rgb24,alpha,blend),"name":"券石k46"}], name="凯旋门下段")
  kind="group"（默认，元件组）| "single"（单体元件，1 条目自引用闭环）。

自测：mods/test_element.py（QXYV2_ROOT 重定向 + 落盘目录注入，零污染）。
"""
from __future__ import annotations

import os
import struct
import sys
import time
from pathlib import Path

from . import asset, config, core

# 元数据首段（账号 uid）：脱敏占位——真实值经环境变量 QXY_ACCOUNT 注入。缺省用中性
# 数字占位，保持正典形态 `uid-时间戳-图号-\文件名.gia`；数字段使门禁「占位零值」告警
# 不触发（该告警按整段字面等于 "0" 判定）。不写死任何真实账号。
ACCOUNT = os.environ.get("QXY_ACCOUNT", "000000000")
CURRENT_VERSION = "7.1.0"             # 不变量6 版本锁（案例 #51/#71）
BAND_ELEMENT = (0x40400000, 0x40500000)        # 用户元件段（案例 #71）
BAND_LEVEL_ENTITY = (0x41400000, 0x41500000)   # 关卡实体段（避开）
MEMBER_LIMIT = 512                    # 纯溢出保护（非引擎上限）。原"240"来自旧方言实测（M3 未证实），
                                      # 且与案例 #51 的方言错误混淆——见 本项目内部报告。266 决定性测试需放行。
MASTER_AID = 10008001                 # 元件组容器 prefab
CID_NAME = 1                          # 名字组件 cid（**元件库显示名的权威字段**，2026-10-14 定案）
CID_NAME_FIELD = 11                   # 名字组件载荷字段号（f11）
CID_MEMBER_TABLE = 61                 # 主件 f6 槽：成员摆放表组件
CID_MEMBER_TABLE_FIELD = 65           # 摆放表载荷字段号
_DEFAULT_MAP_ID = "1073742029"        # 元数据图号字段（四段尾横杠方言组成部分）
_R_NAME_ILLEGAL = set(' /\\:*?"<>|')


def _ensure():
    """装载工具树（只读依赖）：qxy.synth + qxy.paradigm；qxfmt 由 mods/config 自举。

    工具树位置经 mods/config 解析（QXY_TOOL_ROOT）——开源仓库不附带工具树，
    缺配置时如实抛 PreconditionError（换路，不计失败），绝不猜路径。
    """
    config.ensure_qxfmt()                     # 确保 qxfmt 可导入（仓库 src/ 自举）
    root = config.require_tool_root("元件构造/打包/元件体门禁链路")
    if str(root) not in sys.path:
        sys.path.append(str(root))
    import qxy.synth as synth                 # noqa: E402
    import qxy.paradigm as P                  # noqa: E402
    from qxfmt.pbtree import parse, emit, first, varint_value, roundtrip  # noqa: E402
    from qxfmt.container import Container     # noqa: E402
    return synth, P, parse, emit, first, varint_value, roundtrip, Container


# ---------------------------------------------------------------------------
# 元件体构造（从理解生成，非克隆）
# ---------------------------------------------------------------------------

def _cid_of(comp, parse, varint_value):
    """组件槽的 cid（首子字段 f1 的 varint）。"""
    c = parse(comp)
    return varint_value(c[0]) if c else None


def build_body_from_template(aid, guid, member_table=None, carry_rotation=True):
    """模板直映路：官方 prefab aid → 元件体字节（无实例数据；复现本次成功件形态）。

    member_table 非 None 时，把主件 cid61 摆放表填为真实成员（元件组专用）。
    carry_rotation=True（现缺省）时摆放表记录 f3 一并写成员旋转——f3=成员旋转已定案
    （2026-10-14：用户真实样本「测试2」f3={280,280,280} + A/B 判定实验 B 件转/ A 件不转），
    详见 patch_member_table 与 本项目内部报告。传 False 仅复现旧形态（回归用）。
    """
    synth, _, parse, emit, first, varint_value, _, _ = _ensure()
    tmpl = synth.load_template(aid)
    if tmpl is None:
        raise core.PreconditionError(f"asset_id {aid} 无 prefab 模板（official_prefab_db）")
    nodes = [[1, 0, synth._wv(guid)], [2, 0, synth._wv(aid)]]
    for x in parse(tmpl):
        f = x[0]
        if f in (1, 2):
            continue                       # f1 换 guid、f2 换裸 aid
        if f == 6 and member_table is not None and _cid_of(x[2], parse, varint_value) == CID_MEMBER_TABLE:
            nodes.append([6, 2, patch_member_table(x[2], member_table, carry_rotation=carry_rotation)])
        else:
            nodes.append([f, x[1], x[2]])  # f6/f7/f8 直映；f9/f10 原样
    return emit(nodes)


def _rotmsg(rot):
    """旋转 → {f1:X°,f2:Y°,f3:Z°} 消息字节（零分量逐轴省略；全零 → b""）。

    字节形态（定案 2026-10-14）：`0d <f32 X>`=f1、`15 <f32 Y>`=f2、`1d <f32 Z>`=f3。
    真实样本「测试2」rec1 f3 = `0d00008c431500008c431d00008c43`（三轴各 280°，= _rotmsg({1:280,2:280,3:280})）；
    A/B 的 B 件 rec2 f3 = `150000b442`（= _rotmsg({2:90.0})）。两者均入回归（test_element.py）。
    """
    if not rot:
        return b""
    out = b""
    for f, v in ((1, rot.get(1)), (2, rot.get(2)), (3, rot.get(3))):
        if v:
            out += (bytes([(f << 3) | 5]) + struct.pack("<f", float(v)))
    return out


def _posmsg(pos):
    """位置 (x,y,z) → {f1:x,f2:y,f3:z} 消息字节（逐分量写，与真实样本一致）。"""
    x, y, z = pos
    return (b"\x0d" + struct.pack("<f", x) +
            b"\x15" + struct.pack("<f", y) +
            b"\x1d" + struct.pack("<f", z))


def patch_member_table(comp, member_table, carry_rotation=True):
    """主件 f6 槽 cid61 → 带成员记录的摆放表（正典形态逐字节解自真实样本）。

    记录 = {f1:成员身份 token, f2:位置{3×f32}, f3:旋转{…}(msg), f5:身份 token, f6:序号}；每条包一层 f1。

    **f3 语义已定案（2026-10-14）= 成员旋转**（三轴 {f1:X°,f2:Y°,f3:Z°} 度、零分量省略），
    与 f2（位置）对偶。证据：① 用户真实样本「测试2」主件 0x40400007 rec1 f3 逐字节
    = `0d00008c431500008c431d00008c43`（用户确认=三轴各转 280°、无缩放）；② A/B 单变量判定实验
    （本项目内部报告）：旋转只写成员体（A）**不转**、旋转写进摆放表 f3（B）**转了**
    → 编辑器组成员实例化取旋转于 f3（H1 坐实）。

    `carry_rotation`（现缺省 **True**）控制是否把成员旋转写进 f3；传 False 仅复现旧形态（回归用）。
    """
    synth, _, _, emit, _, _, _, _ = _ensure()
    recs = b""
    for (mguid, maid, idx, pos, rot) in member_table:
        posmsg = _posmsg(pos)
        f3 = _rotmsg(rot) if carry_rotation else b""
        rec = emit([[1, 0, synth._wv(mguid)], [2, 2, posmsg], [3, 2, f3],
                    [5, 0, synth._wv(maid)], [6, 0, synth._wv(idx)]])
        recs += synth._lf(1, rec)
    return emit([[1, 0, synth._wv(CID_MEMBER_TABLE)],
                 [CID_MEMBER_TABLE_FIELD, 2, recs]])


def set_body_name(body, name):
    """把元件体的「名字组件」（cid1，首 f6 槽）的 f11.f1 写成 name —— 元件库显示名权威字段。

    ═══ 定案 2026-10-14（案例 #72，接 #71 系列）═══
    编辑器「元件库」里一个元件的**显示名**取自**元件体**的名字组件：
        f6 槽 → 组件 cid=1 → f11 → f1（UTF-8 串）
    组件原始字节形态 = `08 01 5a <len> 0a <slen> <utf8 name>`（= {f1:1, f11:{f1:name}}）。
    与 `synth.synthesize_entity` 填名的形态**逐字节同款**（synth.py: `_vf(1,1) + _lf(11, _lf(1,name))`）。

    **空/缺时的回退**：该字段为空 → 编辑器回退显示该 aid 的**官方 prefab 名**
    （10008001 = "元件组"）。这正是"9 件导入后元件库全显示『元件组』、无法区分"的**唯一成因**——
    元件体的名字组件为空（模板 `0801 5a00` 直映带来），不是元数据的错、也不是入口 f3 的错。

    ═══ 证据链（字节级，详见 本项目内部报告）═══
      · 用户手做 0x40400007「测试2」元件体 f6[0] = `0801 5a09 <测试2>`（非空 → 库内显示对）
      · 用户手做 0x40400115「测试3」元件体 f6[0] = `0801 5a09 <测试3>`
      · 我方导入件（如 0x40400063，aid 10008001）元件体 f6[0] = `0801 5a00`（空 → 回退 "元件组"）
      · 编辑器自产 编辑器自产的 `元件组.gia` 主件体 f6[0] = `0801 5a0b <元件组>`（非空）
      · 反证：0x40400005/06（旋转判定件，成员体带名）库内显示正常；其**主件**体名空——
        而 .gia 入口 f3 明明写了名字（'旋转判定_A'）→ .gia 入口 f3 **不是**库显示名的来源。
      · prefab 10008001 的官方名 = "元件组"（official_prefab_db.json）→ 解释回退值。

    同名组件在实体方言位于 f5 槽（实体体 = 元件体槽位平移一层），同一 cid1 语义。
    """
    synth, _, parse, emit, first, varint_value, _, _ = _ensure()
    nb = name.encode("utf-8")
    newc = emit([[CID_NAME, 0, synth._wv(1)],
                 [CID_NAME_FIELD, 2, emit([[1, 2, nb]])]])
    out, done = [], False
    for fld in parse(body):
        if (not done) and fld[0] == 6 and fld[1] == 2:
            ci = parse(fld[2])
            if ci and ci[0][1] == 0 and varint_value(ci[0]) == CID_NAME:
                out.append([6, 2, newc])
                done = True
                continue
        out.append([fld[0], fld[1], fld[2]])
    if not done:
        # 模板无名字组件（未见；全部官方模板 cid1 恒居首且为 `0801 5a00`）→ 插到最前
        out.insert(0, [6, 2, newc])
    return emit(out)


def read_body_name(body):
    """读元件体名字组件（cid1→f11→f1）→ str；缺/空 → ""（供自检/交叉核对）。"""
    _, _, parse, _, first, varint_value, _, _ = _ensure()
    for fld in parse(body):
        if fld[0] != 6 or fld[1] != 2:
            continue
        ci = parse(fld[2])
        if not ci or ci[0][1] != 0 or varint_value(ci[0]) != CID_NAME:
            continue
        c11 = first(ci, CID_NAME_FIELD)
        if c11 is None or c11[1] != 2:
            return ""
        nm = first(parse(c11[2]), 1)
        return nm[2].decode("utf-8", "replace") if (nm and nm[1] == 2) else ""
    return ""


def read_body_rotation(body):
    """读元件体（成员）f7.cid1 变换消息的旋转 → {1:X°,2:Y°,3:Z°}（缺省/空 → {}）。

    只读自检/交叉核对用：把"我们写进去的旋转"从字节里读回来（供旋转后验断言与自测）。
    """
    synth, _, parse, _, first, varint_value, _, _ = _ensure()
    for fld in parse(body):
        if fld[0] != 7:
            continue
        ci = parse(fld[2])
        if not ci or ci[0][1] != 0 or varint_value(ci[0]) != 1:
            continue
        cm = first(ci, 11)
        if cm is None:
            continue
        rm = first(parse(cm[2]), 2)
        if rm is None or rm[1] != 2 or not rm[2]:
            return {}
        return {x[0]: struct.unpack("<f", x[2])[0] for x in parse(rm[2])}
    return None


def build_body_instance(aid, guid, pos=None, rot=None, scale=None, color=None, name=None):
    """实例数据路：synth 造实体体 → 槽位平移成元件体（carries 变换/缩放/染色/名）。

    平移律（本次对拍实证）：entity.f5→elem.f6（去实例态 cid19/52）、entity.f6→elem.f7、
    entity.f7→elem.f8；f2 改裸 aid（非 {f1:aid,2:1}）+ 补 f10=1。
    """
    synth, _, parse, emit, _, varint_value, _, _ = _ensure()
    x, z, y = _xyz(pos)
    rx = ry = rz = None
    if rot is not None:
        rv = [float(v) for v in (rot if isinstance(rot, (list, tuple)) else (rot,))]
        if len(rv) == 1:
            ry = rv[0]
        elif len(rv) == 3:
            rx, ry, rz = rv
        else:
            raise core.PreconditionError(f"rot 须为 (ry,) 或 (rx,ry,rz)，得到: {rot!r}")
        # 零值省略正典（P2 案例）：逐轴为 0 的轴省略（消息 = {f1:X°,f2:Y°,f3:Z°} 的子集）
        if rx == 0.0:
            rx = None
        if ry == 0.0:
            ry = None
        if rz == 0.0:
            rz = None
    eb = synth.synthesize_entity(aid, guid, x=x, z=z, y=y, scale=scale,
                                 rot_x=rx, rot_y=ry, rot_z=rz, name=name, color=color)
    src = {5: 6, 6: 7, 7: 8}
    nodes = [[1, 0, synth._wv(guid)], [2, 0, synth._wv(aid)]]
    for fld in parse(eb):
        f = fld[0]
        if f in (1, 2) or f == 8:          # 头两字段 + 实体尾 aid 丢弃
            continue
        nf = src.get(f)
        if nf is None:
            continue
        if f == 5:
            c = parse(fld[2])
            if c and varint_value(c[0]) in (19, 52):
                continue                   # 实例态组件（元件体不带）
        nodes.append([nf, fld[1], fld[2]])
    nodes.append([10, 0, synth._wv(1)])
    nodes.sort(key=lambda n: n[0])
    return emit(nodes)


def _xyz(pos):
    """pos 形态 {(x,z,y)} / (x,z)/(x,z,y) → (x, z, y|None)。"""
    if pos is None:
        return 0.0, 0.0, None
    if isinstance(pos, dict):
        return float(pos.get("x", 0.0)), float(pos.get("z", 0.0)), pos.get("y")
    if isinstance(pos, (list, tuple)) and 2 <= len(pos) <= 3:
        return (float(pos[0]), float(pos[1]),
                (float(pos[2]) if len(pos) == 3 else None))
    raise core.PreconditionError(f"member.pos 须为 (x,z)/(x,z,y) 或 {{x,z,y?}}，得到: {pos!r}")


def _can_bare(s):
    """成员能否"裸引用"（只写表记录 + aid、不建定义体）。

    判据（对拍定案 2026-10-14，见 本项目内部报告 §对拍）：成员无需承载任何
    **非默认实例数据**时，可作裸官方 prefab 引用——位置进表 f2、旋转进表 f3，官方模板即形状。
    需承载数据（非单位缩放 / 染色 / 名）者必须建定义体。

    证据：用户真实样本「测试2」主件 rec2 = `f1=f5=10009002`（裸球体，包内无该成员定义，f3 空）；
    R4 真实样本 rec1 同款。故：单位缩放(或缺省) 且 无染色 且 无名 → 可裸引用。
    """
    sc = s.get("scale")
    unit = sc is None or all(abs(float(v) - 1.0) < 1e-9 for v in sc)
    return unit and s.get("color") is None and s.get("name") is None


def _wants_bare(s):
    """成员是否作裸引用：显式 `bare` 覆盖 > 自动判据（_can_bare）。"""
    ov = s.get("bare")
    return bool(ov) if ov is not None else _can_bare(s)


def table_record_rot(comp):
    """从主件体（含 cid61 摆放表）读出每条记录 f3 的旋转 → [{轴:度}, ...]（交叉核对/自测用）。"""
    _, _, parse, _, first, varint_value, _, _ = _ensure()
    recs = None
    for fld in parse(comp):
        if fld[0] == 6 and fld[1] == 2:
            ci = parse(fld[2])
            if ci and varint_value(ci[0]) == CID_MEMBER_TABLE:
                pay = first(ci, CID_MEMBER_TABLE_FIELD)
                recs = parse(pay[2]) if pay and pay[1] == 2 else []
    out = []
    for rn in (recs or []):
        f3 = first(parse(rn[2]), 3)
        out.append({x[0]: struct.unpack("<f", x[2])[0]
                    for x in parse(f3[2]) if x[1] == 5} if (f3 and f3[1] == 2 and f3[2]) else {})
    return out


def _spec_rot(rot):
    """spec.rot（(ry,)/(rx,ry,rz)，度）→ 非零轴字典 {1:X,2:Y,3:Z}（零分量省略）。

    与 build_body_instance 的零值省略正典严格同律——用于"旋转后验守卫"的期望值。
    """
    if rot is None:
        return {}
    rv = [float(v) for v in (rot if isinstance(rot, (list, tuple)) else (rot,))]
    if len(rv) == 1:
        rv = [0.0, rv[0], 0.0]
    if len(rv) != 3:
        raise core.PreconditionError(f"rot 须为 (ry,) 或 (rx,ry,rz)，得到: {rot!r}")
    return {i + 1: rv[i] for i in range(3) if rv[i] != 0.0}


def _dedup_key(s):
    """成员定义去重键 = (aid, scale, color, name)（精确；浮点/颜色取整元组化）。

    语义（2026-10-14 定案）：成员定义体只承载"形状(aid) + 缩放 + 染色 + 名字"——这三者是
    逐成员的"身份数据"；**位置/旋转不进定义体**（逐件在摆放表 f2/f3）。
    证据：编辑器自导成员 0x40400008 体 rot={-100,100,100} 而摆放表 f3={280,280,280} 二者不同，
    渲染取表值 → 体的 pos/rot 是"元件自身创建位"，组成员实例化不取。故键相同的成员可共享定义体。
    """
    sc = tuple(round(float(v), 9) for v in s["scale"]) if s["scale"] is not None else None
    co = tuple(s["color"]) if s["color"] is not None else None
    return (s["aid"], sc, co, s["name"])


# ---------------------------------------------------------------------------
# 打包元件方言 .gia
# ---------------------------------------------------------------------------

def _ident(guid, emit, wv):
    """条目引用/身份单元: {f2:1, f3:1, f4:guid}（案例 #71：f3=1 是 7.1 值）。"""
    return emit([[2, 0, wv(1)], [3, 0, wv(1)], [4, 0, wv(guid)]])


def build_package(master_guid, master_body, members, name, map_id, out_path):
    """主件 + 成员 → 元件方言 .gia 字节（落盘）。

    members: [(guid, body, display_name), ...]（kind='single' 时为空列表，主件自引用）。
    """
    synth, _, _, emit, _, _, roundtrip, Container = _ensure()
    wv = synth._wv
    nodes = []
    me = [[1, 2, _ident(master_guid, emit, wv)]]
    for (mg, _mb, _mn) in members:
        me.append([2, 2, _ident(mg, emit, wv)])   # 主件→成员引用
    me.append([3, 2, name.encode("utf-8")])
    me.append([5, 0, wv(1)])                      # cls=1
    me.append([11, 2, emit([[1, 2, master_body]])])
    nodes.append([1, 2, emit(me)])
    for (mg, mb, mn) in members:
        ee = [[1, 2, _ident(mg, emit, wv)]]
        ee.append([2, 2, _ident(mg, emit, wv)])   # 成员自引用
        ee.append([3, 2, mn.encode("utf-8")])
        ee.append([5, 0, wv(1)])
        ee.append([11, 2, emit([[1, 2, mb]])])
        nodes.append([2, 2, emit(ee)])
    fname = name if name.endswith(".gia") else name + ".gia"
    nodes.append([3, 2, f"{ACCOUNT}-{int(time.time())}-{map_id}-\\{fname}".encode("utf-8")])
    nodes.append([5, 2, CURRENT_VERSION.encode("utf-8")])
    proto = emit(nodes)
    if not roundtrip(proto):
        raise core.ModuleRejected("元件方言 .gia 字节守恒破坏（roundtrip 失败）")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Container(3, proto).save(out_path)
    return proto


# ---------------------------------------------------------------------------
# 注册模块
# ---------------------------------------------------------------------------

@core.module("element.build")
def element_build(members, name: str, guid: int | None = None,
                  kind: str = "group", map_id: str = _DEFAULT_MAP_ID,
                  out_dir: str | None = None,
                  allow_unproven_count: bool = False,
                  dedup: bool = False,
                  member_table_rotation: bool = True) -> core.Result:
    """从零构造元件体 + 打包元件方言 .gia（元件通道固化；案例 #71）。

    参数：
        members  [{aid, pos?, rot?, scale?, color?, name?, bare?}, ...]。aid=官方 prefab id；
                 pos=(x,z)/(x,z,y)/{x,z,y?}（相对元件组中心，米）；rot=(ry,) 或 (rx,ry,rz) 度；
                 scale=(sx,sy,sz)；color=(rgb24,alpha,blend) V3 染色；name=成员显示名。
                 bare=True/False 显式指定该成员是否裸引用（缺省=自动：单位/缺省缩放 且 无染色
                 且 无名 → 裸引用，只写表记录 + aid、不建定义体）。
        name     元件名（=文件名，全局唯一语义）。
        guid     主件 guid（0x404 段）；None → P.alloc_guids 台账分配（含各成员）。
        kind     "group"=元件组（主件 10008001 + 成员）；"single"=单体元件（1 条目自引用）。
        map_id   元数据图号字段（四段尾横杠方言组成）。
        out_dir  落盘目录（缺省=状态根 state/elements/，自测零污染）；导入目录归 asset.deploy。
        allow_unproven_count  仅当唯一 SICK 是"成员数上限"（M3 未证实常数）时把包门降级为
                    WARN 放行——供 266 决定性测试用；其余 SICK 仍拦截。缺省 False（严格）。
        dedup    成员定义去重（缺省 **False**）。True 时：非裸成员按 `_dedup_key`
                    = **(aid, scale, color, name)** 精确键聚合——键相同者**共享同一 guid /
                    同一成员定义体**（定义体只写 形状+缩放+染色+名字，取原点/零旋转；
                    位置(f2)/旋转(f3) 逐件仍在摆放表）。外观逐件不变（键含全部外观要素）。
                    **仅对"带非默认实例数据"（非裸）成员生效**；裸成员本就不建定义。
                    定义体取原点/零旋转的依据：编辑器自导成员体 pos/rot 是"元件自身创建位"
                    （0x40400008 体 rot={-100,100,100} ≠ 表 f3={280,280,280}），组成员实例化取表值。
                    缺省 False = 每个非裸成员各建一条定义（与 v2 同形态，既有自测不变）。
        member_table_rotation  把成员旋转写进摆放表记录 f3（缺省 **True**）。f3=成员旋转已定案
                    （2026-10-14：真实样本「测试2」f3={280,280,280} + A/B 实验 B 转 A 不转）——
                    编辑器组成员实例化**取旋转于表 f3**；成员体旋转保留（编辑器自导体亦带，无害）。
                    传 False 仅复现旧形态（回归用）。

    减重（裸引用）：成员无需非默认实例数据（单位/缺省缩放 且 无染色 且 无名）时，**不建定义体**，
    仅写摆放表记录（f1=f5=aid）；位置(f2)/旋转(f3)本就在表里。对凯旋门 266 件实测结论 = **0 件
    可裸引用**（0/266 单位缩放、256/266 带染色）——见 本项目内部报告 §对拍。

    返回 Result：artifact=.gia 路径；value={path,count,guids,kind}；checks 含体门/包门结论。
    """
    synth, P, parse, emit, first, varint_value, roundtrip, _ = _ensure()
    from qxy import trial_gate as tg         # 只读依赖：元件体门禁函数

    # ── 前置 ──
    if not name or (set(name) & _R_NAME_ILLEGAL) or name.startswith("."):
        raise core.PreconditionError(f"name 须为单段合法文件名，得到: {name!r}")
    if kind not in ("group", "single"):
        raise core.PreconditionError(f"kind 须为 'group'|'single'，得到: {kind!r}")
    if not isinstance(members, (list, tuple)) or not members:
        raise core.PreconditionError("members 须为非空列表")
    if kind == "single" and len(members) != 1:
        raise core.PreconditionError(f"kind='single' 须恰 1 个 member，得到 {len(members)}")
    if kind == "group" and len(members) >= MEMBER_LIMIT:
        raise core.PreconditionError(
            f"成员数 {len(members)} ≥ 上限 {MEMBER_LIMIT}（案例 #50；精确值待 D5）")
    specs = []
    for i, m in enumerate(members):
        if not isinstance(m, dict) or "aid" not in m:
            raise core.PreconditionError(f"members[{i}] 非 {{aid,pos?}} 形态: {m!r}")
        aid = m["aid"]
        if not isinstance(aid, int) or isinstance(aid, bool) or aid <= 0:
            raise core.PreconditionError(f"members[{i}].aid 须为正整数: {aid!r}")
        if synth.load_template(aid) is None:
            raise core.PreconditionError(
                f"members[{i}].aid {aid} 无 prefab 模板（official_prefab_db）——先查正确资产 id")
        x, z, y = _xyz(m.get("pos"))
        specs.append({"aid": aid, "x": x, "z": z, "y": y, "rot": m.get("rot"),
                      "scale": m.get("scale"), "color": m.get("color"),
                      "name": m.get("name"), "bare": m.get("bare"), "guid": None})
    if guid is not None:
        if not isinstance(guid, int) or isinstance(guid, bool) or guid <= 0:
            raise core.PreconditionError(f"guid 须为正整数: {guid!r}")
        if not (BAND_ELEMENT[0] <= guid < BAND_ELEMENT[1]):
            raise core.PreconditionError(f"guid {hex(guid)} 不在用户元件段 0x404xxxxx")
        if BAND_LEVEL_ENTITY[0] <= guid < BAND_LEVEL_ENTITY[1]:
            raise core.PreconditionError(f"guid {hex(guid)} 落关卡实体段（避开）")

    # ── 执行 ──
    # 减重（裸引用）：无需非默认实例数据（单位/缺省缩放 且 无染色 且 无名）的成员不建定义、不占 guid。
    bare = [_wants_bare(s) for s in specs] if kind == "group" else [False]
    # 去重（dedup）：非裸成员按 (aid,scale,color,name) 精确键聚合；键相同 → 共享定义（同一 guid）。
    key_order = []          # 唯一键（首见序）
    key_guid = {}           # key → guid
    member_key = [None] * len(specs)
    if kind == "group" and dedup:
        seen = {}
        for i, s in enumerate(specs):
            if bare[i]:
                continue
            k = _dedup_key(s)
            member_key[i] = k
            if k not in seen:
                seen[k] = len(key_order)
                key_order.append(k)
        n_def = len(key_order)
    elif kind == "group":
        n_def = sum(1 for b in bare if not b)
    else:
        n_def = 0
    # guid：主件 1 + 各"需建定义"成员（group）/ 主件 1（single）；dedup 时按唯一键数计
    if guid is not None:
        # 显式主件 guid → 仅需建定义的成员走台账分配
        member_guids = P.alloc_guids(count=n_def, note=f"element.build:{name}") \
            if (kind == "group" and n_def) else []
        master_guid = guid
    else:
        need = (1 + n_def) if kind == "group" else 1
        got = P.alloc_guids(count=need, note=f"element.build:{name}")
        master_guid, member_guids = got[0], got[1:]

    if kind == "group":
        member_entries = []
        member_table = []
        if dedup:
            # 唯一键 → guid；每个唯一键建一条定义体（原点/零旋转——位置旋转进表）
            for idx, k in enumerate(key_order):
                key_guid[k] = member_guids[idx]
            body_by_key = {}
            name_by_key = {}
            for i, s in enumerate(specs):
                if bare[i]:
                    continue
                k = member_key[i]
                if k in body_by_key:
                    continue
                body_by_key[k] = build_body_instance(
                    s["aid"], key_guid[k], pos=(0.0, 0.0, 0.0), rot=None,
                    scale=s["scale"], color=s["color"], name=s["name"])
                name_by_key[k] = s["name"] or f"成员型{len(name_by_key)+1}_{name}"
            for k in key_order:
                member_entries.append((key_guid[k], body_by_key[k], name_by_key[k]))
            for i, s in enumerate(specs):
                rec_pos = (s["x"], s["y"] or 0.0, s["z"])
                want = _spec_rot(s["rot"])
                if bare[i]:
                    member_table.append((s["aid"], s["aid"], i + 1, rec_pos, want))
                else:
                    member_table.append((key_guid[member_key[i]], s["aid"], i + 1, rec_pos, want))
        else:
            gq = list(member_guids)
            for i, s in enumerate(specs):
                rec_pos = (s["x"], s["y"] or 0.0, s["z"])
                want = _spec_rot(s["rot"])
                if bare[i]:
                    # 裸官方 prefab：不建定义、不分配 guid；表记录 f1=f5=aid（对拍真实样本同款）
                    member_table.append((s["aid"], s["aid"], i + 1, rec_pos, want))
                    continue
                g = gq.pop(0)
                s["guid"] = g
                body = _member_body(s, synth, parse, varint_value)
                # ── 旋转后验守卫（防静默丢旋转：请求了旋转就必须在成员体字节里读回来）──
                if want:
                    got_body = read_body_rotation(body) or {}
                    got_r = {k: round(float(v), 3) for k, v in got_body.items()}
                    want_r = {k: round(float(v), 3) for k, v in want.items()}
                    if got_r != want_r:
                        raise core.ModuleRejected(
                            f"成员 {s['aid']} 旋转丢失：请求 {want_r} 字节读回 {got_r}"
                            "（模板变换消息形态不支持该轴？见 element.read_body_rotation）")
                member_entries.append((g, body, s["name"] or f"成员_{name}_{len(member_entries)+1}"))
                member_table.append((g, s["aid"], i + 1, rec_pos, want))
        master_body = build_body_from_template(MASTER_AID, master_guid, member_table=member_table,
                                               carry_rotation=member_table_rotation)
        # ── 摆放表 f3 旋转后验守卫（表 f3 现为"组成员旋转"权威通道，定案 2026-10-14）──
        if member_table_rotation:
            tbl_rot = table_record_rot(master_body)
            for i, s in enumerate(specs):
                want_r = {k: round(float(v), 3) for k, v in _spec_rot(s["rot"]).items()}
                got_r = ({k: round(float(v), 3) for k, v in tbl_rot[i].items()}
                         if i < len(tbl_rot) else None)
                if got_r != want_r:
                    raise core.ModuleRejected(
                        f"成员 {s['aid']} 摆放表 f3 旋转丢失：请求 {want_r} 表读回 {got_r}")
    else:  # single：1 条目自引用，主体=成员 aid
        s = specs[0]
        s["guid"] = master_guid
        master_body = _member_body(s, synth, parse, varint_value)
        member_entries = []

    # ── 名字组件（cid1）写入元件名 —— 元件库显示名的权威字段（2026-10-14 定案）──
    #   模板直映路的元件体名字组件恒为 `0801 5a00`（空）→ 库内回退显示 prefab 默认名
    #   （10008001="元件组"）。这里改写为真实元件名（set_body_name 释义/证据见其 docstring）。
    master_body = set_body_name(master_body, name)

    dest_dir = Path(out_dir) if out_dir else core.state_dir() / "elements"
    dest_dir.mkdir(parents=True, exist_ok=True)
    pkg = dest_dir / (name if name.endswith(".gia") else name + ".gia")
    proto = build_package(master_guid, master_body, member_entries, name, str(map_id), str(pkg))

    # ── 后验 ──
    checks = [("aid_has_template", "PASS"),
              ("gia_roundtrip", "PASS" if roundtrip(proto) else "FAIL")]
    # 名字组件后验：元件库显示名 = 主件体 cid1→f11→f1，必须 == 元件名（否则回退显示 prefab 名）
    got_name = read_body_name(master_body)
    if got_name != name:
        raise core.ModuleRejected(
            f"元件名未落进名字组件（cid1/f11/f1）：期望 {name!r} 读回 {got_name!r}")
    checks.append(("elem_name_component", f"PASS:{name}"))
    bodies = [(f"主件/{hex(master_guid)}", master_body)]
    bodies += [(f"成员/{hex(g)}", b) for (g, b, _) in member_entries]
    body_sick = 0
    for label, body in bodies:
        probs = tg._check_element_body(body, label)
        for lv, tag, msg in probs:
            if lv == "SICK":
                body_sick += 1
            checks.append((f"体门:{tag}", f"{lv}:{msg[:60]}"))
    checks.append(("element_body_gate", "PASS" if body_sick == 0 else "FAIL"))
    if body_sick:
        raise core.ModuleRejected(f"元件体门禁拦截 {body_sick} 项")

    verdict, gate_out = asset.run_trial_gate(pkg)
    if verdict != "TRIAL_PASS":
        sick_lines = [ln for ln in gate_out.splitlines() if "[SICK]" in ln]
        count_sick = [ln for ln in sick_lines if "成员数" in ln]
        other_sick = [ln for ln in sick_lines if "成员数" not in ln]
        if allow_unproven_count and count_sick and not other_sick:
            # "成员数上限"常数来自旧方言实测（M3 未证实，且与案例 #51 方言错误混淆）——
            # 266 决定性测试需放行：降级为 WARN（记入 checks），其余 SICK 仍拦截。
            verdict = "TRIAL_PASS"
            checks.append(("count_limit", "WARN:成员数上限常数未证实(M3)——放行(见 本项目内部报告)"))
        else:
            detail = " | ".join(ln.strip() for ln in sick_lines)
            raise core.ModuleRejected(f"trial_gate 拦截: {detail or verdict}")
    checks.append(("trial_gate", verdict))
    if dedup and kind == "group":
        checks.append(("dedup_definitions", f"{n_def} 定义（{len(specs)} 成员记录）"))

    n_members = len(specs) if kind == "group" else 1
    return core.Result(ok=True, artifact=str(pkg), checks=checks, value={
        "path": str(pkg),
        "count": 1 + len(member_entries),
        "definitions": 1 + len(member_entries),
        "members": n_members,
        "guids": [master_guid] + [g for (g, _, _) in member_entries],
        "kind": kind,
    })


def _member_body(s, synth, parse, varint_value):
    """成员体：无实例数据 → 模板直映（复现成功件）；有 → 实例数据路（槽位平移）。"""
    if s["scale"] is None and s["rot"] is None and s["color"] is None and s["name"] is None:
        return build_body_from_template(s["aid"], s["guid"], member_table=None)
    return build_body_instance(s["aid"], s["guid"], pos=(s["x"], s["z"], s["y"]),
                               rot=s["rot"], scale=s["scale"], color=s["color"],
                               name=s["name"])
