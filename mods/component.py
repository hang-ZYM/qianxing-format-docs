# -*- coding: utf-8 -*-
"""component.attach — 向关卡现有实体的组件槽追加/替换一个组件（M4 步 2a 前置件，2026-10-14）。

═══ 为什么需要（能力缺口）═══
entity.place 的实体组件来自 prefab 模板（P.entity 合成时带着），**我们的模块此前没有
"往实体槽里加一个组件"的能力**。本模块补这一环：在任一现有关卡版本的 f5 实体上，
向其 f5/f6/f7/f8 组件槽追加（或替换）一个组件条目。

═══ 组件槽字节形态（手册/12 组件全典 + 本轮全档 311 图实证）═══
实体的 body = 顶层字段序列；组件槽 = **repeated** 顶层字段 f5(行为)/f6(编辑器)/f7(资源)/
f8(表现·引用)，每一次出现 = 一个组件条目：
    组件条目 = { f1: cid(组件号), f2: 1, f<载荷字段号>: 载荷 }
- **组件号 cid = 槽内条目首子字段 f1 的 varint**（与载荷字段号是两套编号）。
- 载荷字段号 = cid + 偏移（按 (槽, cid) 分族，模块化架构 v4 §二 偏移族全表）：
  f6/f7/f8 槽 cid≥21 → **+11**（例：f7 槽 cid38 光源 → 载荷 f49；见本轮字节）。
- f8 之上另有一个 **varint 尾字段 f8 = aid**（官方 prefab 实例的尾标；放置即有此字段）。
本模块只追加**组件条目**（f5/f6/f7/f8 repeated 消息），不碰尾 aid varint。

═══ 光源组件定案（M4 步 2a，字节证据链）═══
全档 311 图扫描（用户 41 存档 + 商城 270）得 f7 槽 cid38 共 223 实例/335 光源条目/
16 文件（2D跑酷/星辰共跃空间站/魔王激战/幽域残垣/石制挂灯图…）。载荷 schema（字段号→含义）：
    f49                       ← 载荷（cid38 + 11）
      f1 ×N                   ← 光源条目（**一个组件可生效多个光源**，实测 1..10）
        f1                    ← 光源序号（1 基，列表序；开关实体光源节点据此寻址）
        f2 = 1                ← 结构标志（首条目携带）
        f3                    ← 序号/计数器（值 2..，含义待锚）
        f501                  ← 光源配置
          f2 = str            ← **光源名称**（"光源1"…，官方默认按序命名）
          f3 = "GI_RootNode"  ← 挂接点（次，129 例）
          f4                  ← 参数组
            f1 = 1
            f2 = f32          ← **半径**（10/35/50/100/1000 实测）
            f3 = vec3         ← **位置**（相对挂接点偏移，{f1:x,f2:y,f3:z}，零省略）
            f4 = vec3         ← **旋转**
            f5 = 1            ← 标志（143 例恒 1）
            f51 | f52         ← **互斥**参数组（335 条目全恰有其一二选一：f51 206 / f52 129）
              f2 = f32        ← 强度/范围（30/3/26.33…）
              f3 = f32        ← 范围/强度（1.5/3/5…）
              f4/(f5) = varint← **颜色 ARGB**（-1=默认；实测 0xFF9B0CD2/0xFF41A2BD 等）
          f5                  ← 序号（= 条目 f3）
          f6 = "GI_RootNode"  ← **挂接点**（243 例；默认根节点）
        f502 = 1              ← 结构标志
未锚项（如实）：f51 vs f52 二选一的分界（疑 点光源/聚光灯 或 单色/模式）——本轮取
多数派 f51；f3 语义；f501.f3。构造默认值全部取自真实样本实见值（禁猜：不造未见值）。

═══ component.attach 契约（四要素）═══
前置：关卡有当前版本 / slot∈{5,6,7,8} / target_guid 实体在位（f5 命中）/ payload 形态合法
      （字节可解析、首字段 f1==cid）/ **不超该组件限额**（同槽同 cid 计数 < max_same，
      除非 replace=True 走替换）。
执行：向目标实体 body 的槽位追加一个组件条目（replace 命中则替换该条目的载荷字节）。
后验：产物 roundtrip / 目标实体该槽 cid 条目**读回在位**且**载荷字节与请求逐字节一致** /
      实体数不变 / trial_gate 非 SICK。（坏产物在落版前拦截 → 不产新版本。）
日志与版本：core 包装器自动落 oplog + 版本 levels/<关卡>/v<N>.gil。

自测：mods/test_component.py（QXYV2_ROOT 重定向 + 台账 monkeypatch，零污染；正例=挂
已知形态组件 cid5 触发器/ cid38 光源；负例=重复挂/超限额/坏 cid/实体不在位）。
"""
from __future__ import annotations

import struct
from pathlib import Path

from . import asset, core, entity, level

# ---- 既有件（只读依赖，禁改）----
# entity 模块已按文件路径装载 assemble v1 并暴露 parse/emit/enc/viv/_fields/_walk_varints
assemble = entity.assemble
parse, emit, enc, viv = assemble.parse, assemble.emit, assemble.enc, assemble.viv
Container = assemble.Container
_ensure_qxy = asset._ensure_qxy

SLOTS = (5, 6, 7, 8)                # 组件槽顶层字段号
LIGHT_CID = 38                      # 光源组件 cid（**限 f7 槽**；f5 槽 cid38=缩放系数，同号不同物）
LIGHT_PAYLOAD_FIELD = 49            # 光源载荷字段号（f7 槽 cid≥21 +11）
LIGHT_ATTACH_DEFAULT = "GI_RootNode"


# ---------------------------------------------------------------------------
# proto 构造小件（组件消息由调用方以字段级生成，禁克隆整件）
# ---------------------------------------------------------------------------

def _fl(f: int, v: int) -> list:
    """varint 字段 [f, 0, 字节]。"""
    return [f, 0, enc(v)]


def _fm(f: int, kids) -> list:
    """消息字段 [f, 2, 字节]（kids = 子节点列表）。"""
    return [f, 2, emit(kids)]


def _f32(f: int, v: float) -> list:
    """fixed32 浮点字段 [f, 5, 4B]。"""
    return [f, 5, struct.pack("<f", float(v))]


def _fstr(f: int, s: str) -> list:
    """字符串字段 [f, 2, utf8]。"""
    return [f, 2, str(s).encode("utf-8")]


def _vec3(f: int, x=None, y=None, z=None) -> list:
    """三维向量字段（零分量省略；全 None → 空消息）。"""
    kids = []
    if x:
        kids.append(_f32(1, x))
    if y:
        kids.append(_f32(2, y))
    if z:
        kids.append(_f32(3, z))
    return _fm(f, kids)


# ---------------------------------------------------------------------------
# 光源组件生成器（schema 见模块 docstring；默认值全取真实样本实见值）
# ---------------------------------------------------------------------------

def light_component(name: str = "光源1", radius: float = 9.0,
                    intensity: float = 30.0, effect_range: float = 3.0,
                    color: int = 0xFFFFB347, attach: str = LIGHT_ATTACH_DEFAULT,
                    pos=None, rot=None, seq: int = 2, group: str = "f51") -> bytes:
    """生成一个光源组件条目字节（cid38，f7 槽用）。

    参数：
        name          光源名称（f501.f2）
        radius        半径（f501.f4.f2，f32）
        intensity     强度（f51.f2 / f52.f2）
        effect_range  生效范围（f51.f3 / **f52.f4**——见下方「f52 组内字段序」）
        color         颜色 ARGB int（f51.f4 / f52.f5；默认暖琥珀 0xFFFFB347）
        attach        挂接点（f501.f6，默认 GI_RootNode）
        pos/rot       相对挂接点偏移 (x,y,z) 或 None（None=原点/不旋转）
        seq           条目 f3 与 f501.f5（真实样本单光源实见 2..4；默认 2）
        group         "f51"（多数派，206 例）或 "f52"（129 例）——互斥参数组

    返回：组件消息字节 = {f1:38, f2:1, f49:{...}}，可直接交 component.attach。

    ═══ f52 组内字段序（2026-10-14 修，M4 点光源任务；字节证据）═══
    f51 = {f2:强度, f3:生效范围, f4:颜色}（3 字段）。
    f52 = {f2:强度, **f3:半径**, f4:生效范围, f5:颜色}（4 字段）——**旧代码把 f4 当半径是错的**。
    依据：①真实样本 aid10005018 的 f52 为 {f2:22.0, f3:48.41, f4:3.35}，其**外层半径=50.0**
    → f3(48.41)≈外层半径，f4(3.35) 才是生效范围；②全档 f52 语料：f4∈[1.4,5.0] 与外层半径
    **无关**（=生效范围），f3∈[20,88] 随外层半径走（=半径）。f51 无对应字段，半径只在外层 f4.f2。
    """
    if group not in ("f51", "f52"):
        raise core.PreconditionError(f"group 须为 'f51'/'f52'，得到: {group!r}")
    if not isinstance(name, str) or not name:
        raise core.PreconditionError(f"name 须为非空字符串，得到: {name!r}")
    if radius <= 0:
        raise core.PreconditionError(f"radius 须为正数，得到: {radius!r}")
    if not (0 <= int(color) <= 0xFFFFFFFF):
        raise core.PreconditionError(f"color 须为 0..0xFFFFFFFF 的 ARGB 整数，得到: {color!r}")

    if group == "f51":
        pgroup = _fm(51, [_f32(2, intensity), _f32(3, effect_range), _fl(4, int(color))])
    else:
        # f52 = {f2:强度, f3:半径, f4:生效范围, f5:颜色}（见 docstring「f52 组内字段序」）
        pgroup = _fm(52, [_f32(2, intensity), _f32(3, float(radius)),
                          _f32(4, effect_range), _fl(5, int(color))])

    p = pos if isinstance(pos, (list, tuple)) and len(pos) == 3 else (None, None, None)
    r = rot if isinstance(rot, (list, tuple)) and len(rot) == 3 else (None, None, None)

    entry = _fm(1, [                        # f49.f1 = 光源条目
        _fl(1, 1),                          # 光序号（1 基）
        _fl(2, 1),                          # 结构标志
        _fl(3, int(seq)),                   # 序号/计数器
        _fm(501, [                          # 光源配置
            _fstr(2, name),                 # 光源名称
            _fm(4, [                        # 参数组
                _fl(1, 1),
                _f32(2, radius),            # 半径
                _vec3(3, *p),               # 位置（相对挂接点）
                _vec3(4, *r),               # 旋转
                _fl(5, 1),
                pgroup,                     # 强度/范围/颜色（f51 | f52 互斥）
            ]),
            _fl(5, int(seq)),               # 序号
            _fstr(6, attach),               # 挂接点
        ]),
        _fl(502, 1),                        # 结构标志
    ])
    return emit([_fl(1, LIGHT_CID), _fl(2, 1), _fm(LIGHT_PAYLOAD_FIELD, [entry])])


# ---------------------------------------------------------------------------
# 可见性组件生成器（M4 步 2b 前置件，2026-10-15）
# ---------------------------------------------------------------------------
#
# ═══ 「默认隐身」的字节输出路径定案（本件采用；证据链见下）═══
# 实体侧让一个单位**不可见**的**唯一有字节实证**的开关 =
#   **f6 槽 cid8（PropertyStaticVisible / 模型静态可见性）→ 载荷字段 f18**，
#   把 f18 内的 **f1 删掉** ⇒ 不可见；f1=1 在场 ⇒ 可见。
#
# 证据（三源，均为用户实测/字节级，非推断）：
#  ① 正误对照表：「不可见案例 | 组件8/f18 = PropertyStaticVisible，**用户"不可见实体"diff 实锤**」
#     「字节层 | …不可见=comp8/f18 删 f1:1」；勘误③「可见性字段 = **f18.f1 + f501**（非 f503）」
#  ② 08_属性与组件手册 §二 速查#13 / §三.3：「f6#8 可见性 f18：{f1:1=可见, f501:1}；**删 f1=隐身**」
#  ③ 本档字节：长方体的 f6 槽 cid8 载荷 f18 = `{f1:1, f501:1}`（5B：08 01 C8 1F 01）——
#     与 ① 描述逐位吻合（f6 槽组件条目**不带 f2**，与同槽兄弟组件同形）。
#
# ═══ 为什么不用「单位状态·隐藏角色」（设计稿原定机制）═══
# 官方确有单位状态「隐藏角色」（官方语料原文），且**单位状态组件是"所有单位的默认挂载
# 组件"**（官方语料 ⇒ 不是"只有怪物能挂"）；但：
#   ① 该组件的**编辑器序列化 cid 未知**（单位状态域未知清单#4）；
#   ② 全档 41 个存档扫描：**零个"配置了状态的单位状态组件"实例**（唯一含状态资产的图 1073741954
#      里，状态 guid 只出现在关卡实体/镜头的 f7 cid1 变量层，从未出现在实体组件载荷上）；
#   ⇒ 字节面**不可构造**（禁猜 cid）→ 本模块走 f6#8 路。
# 语义差异（如实记录）：f6#8 = **模型不可见**（渲染层）；单位状态「角色隐藏」还含屏蔽特效/音频、
# 半透明档、以及"状态存在性"（可被节点查询/移除）。本件只验"看不见"，f6#8 足够。

VISIBLE_CID = 8                 # 模型可见性组件 cid（**限 f6 槽**）
VISIBLE_PAYLOAD_FIELD = 18      # 载荷字段号 = cid + 10（08_属性与组件手册 §一 定律；本档字节实见）


def visible_component(visible: bool = True) -> bytes:
    """生成 f6 槽 cid8「模型可见性」组件条目字节（步 2b 隐身用）。

    参数：
        visible  True → `{f1:8, f18:{f1:1, f501:1}}`（可见，= 出厂形态）
                 False → `{f1:8, f18:{f501:1}}`（**删 f1** = 不可见）

    返回：组件消息字节，可直接交 component.attach(slot=6, replace=True)。
    注意：f6 槽组件条目不携带 f2（与 f7 槽的 `{f1,f2,载荷}` 三字段形不同）——按同槽兄弟对齐。
    """
    if not isinstance(visible, bool):
        raise core.PreconditionError(f"visible 须为 bool，得到: {visible!r}")
    kids = [_fl(1, VISIBLE_CID)]
    inner = ([_fl(1, 1)] if visible else []) + [_fl(501, 1)]
    kids.append(_fm(VISIBLE_PAYLOAD_FIELD, inner))
    return emit(kids)


def set_visible(level_name: str, target_guid: int, visible: bool = True) -> core.Result:
    """把目标实体的「模型可见性」（f6 槽 cid8）置为 visible。

    前置：目标实体 f6 槽**已有** cid8 组件（出厂 prefab 默认自带；缺失=换路）。
    执行：component_attach(slot=6, cid=8, replace=True)。
    后验：roundtrip + 读回在位 + 载荷逐字节一致 + 实体数不变 + trial_gate。
    """
    return component_attach(level_name, target_guid, VISIBLE_CID,
                            visible_component(visible), slot=6, replace=True)


# ---------------------------------------------------------------------------
# 实体定位与组件计数
# ---------------------------------------------------------------------------

def _f5_entities(tree):
    """返回 [(f5容器节点, entries列表), ...]（f5 顶层字段；通常恰 1 个容器）。"""
    out = []
    for nd in tree:
        if isinstance(nd, list) and nd[0] == 5 and nd[1] == 2:
            ents = parse(nd[2])
            if ents is not None:
                out.append((nd, ents))
    return out


def _entity_bodies(tree):
    """遍历所有实体的 (f5容器节点, entries, entry节点, body节点列表)。"""
    for container, ents in _f5_entities(tree):
        for e in ents:
            if isinstance(e, list) and e[0] == 1 and e[1] == 2:
                body = parse(e[2])
                if body is not None:
                    yield container, ents, e, body


def _body_guid(body) -> int | None:
    for nd in body:
        if isinstance(nd, list) and nd[0] == 1 and nd[1] == 0:
            return viv(nd[2])
    return None


def _slot_components(body, slot: int):
    """返回 body 内 slot 槽的组件条目节点列表（顶层 repeated 字段 slot）。"""
    return [nd for nd in body if isinstance(nd, list) and nd[0] == slot and nd[1] == 2]


def _component_cid(comp_node) -> int | None:
    sub = parse(comp_node[2])
    if sub and sub[0][0] == 1 and sub[0][1] == 0:
        return viv(sub[0][2])
    return None


def _scan_used_guids(tree):
    used: dict[int, list[str]] = {}
    for i, nd in enumerate(tree):
        if not isinstance(nd, list):
            continue
        for path, v in assemble._walk_varints(nd, f"top[{i}]"):
            used.setdefault(v, []).append(path)
    return used


# ---------------------------------------------------------------------------
# 注册模块
# ---------------------------------------------------------------------------

@core.module("component.attach")
def component_attach(level_name: str, target_guid: int, cid: int,
                     payload_spec, slot: int = 7, replace: bool = False,
                     max_same: int = 1) -> core.Result:
    """向关卡当前版本的目标实体追加/替换一个组件条目（M4 步 2a 前置件）。

    参数：
        level_name   版本域名（须已有当前版本）
        target_guid  目标实体 guid（f5 命中的实体身份位）
        cid          组件号（组件条目首子字段 f1）
        payload_spec 组件条目字节：**完整组件消息体**（含 {f1:cid,...}）——bytes；
                     或可调用对象（返回 bytes）；或 dict（键=字段号，值=已编码字节）——
                     由调用方（如 light_component）以字段级生成，禁克隆整件
        slot         组件槽（5/6/7/8；默认 7=资源槽——光源组件所在槽）
        replace      True=同槽同 cid 已存在时替换其载荷；False=存在即前置不过
        max_same     同槽同 cid 允许的最大条数（超额=前置不过；默认 1）

    返回 Result：artifact=产物（core 复制成新版本）；level=版本域名；
    value={guid, cid, slot, action, component_bytes, count_after}。
    """
    # ---- 前置①：cid / slot / guid 形态 ----
    if not isinstance(cid, int) or isinstance(cid, bool) or cid <= 0:
        raise core.PreconditionError(f"cid 须为正整数，得到: {cid!r}")
    if slot not in SLOTS:
        raise core.PreconditionError(f"slot 须∈{SLOTS}，得到: {slot!r}")
    if not isinstance(target_guid, int) or isinstance(target_guid, bool) or target_guid <= 0:
        raise core.PreconditionError(f"target_guid 须为正整数，得到: {target_guid!r}")
    if not isinstance(max_same, int) or max_same < 1:
        raise core.PreconditionError(f"max_same 须为 ≥1 的整数，得到: {max_same!r}")
    checks = []

    # ---- 前置②：payload 形态（字节可解析 + 首字段 f1==cid）----
    if callable(payload_spec):
        payload_spec = payload_spec()
    if isinstance(payload_spec, dict):
        try:
            payload_spec = emit([[int(k), 2, bytes(v)] for k, v in payload_spec.items()])
        except Exception as e:
            raise core.PreconditionError(f"payload dict 无法编码: {e!r}")
    if not isinstance(payload_spec, (bytes, bytearray)) or not payload_spec:
        raise core.PreconditionError(
            "payload_spec 须为组件消息字节（非空）或可编码 dict，得到: "
            f"{type(payload_spec).__name__}")
    comp_bytes = bytes(payload_spec)
    comp_fields = parse(comp_bytes)
    if not comp_fields or not (comp_fields[0][0] == 1 and comp_fields[0][1] == 0):
        raise core.PreconditionError("payload 组件字节首字段须为 varint f1(cid)")
    if viv(comp_fields[0][2]) != cid:
        raise core.PreconditionError(
            f"payload 首字段 f1={viv(comp_fields[0][2])} 与 cid={cid} 不一致")
    checks.append(("payload_wellformed", "PASS"))

    # ---- 前置③：关卡当前版本 ----
    cur_ver = core.current_version(level_name)
    cur = core.read_current(level_name)
    if cur is None:
        raise core.PreconditionError(
            f"关卡 {level_name!r} 无当前版本（levels/ 下无 v<N>.gil）——先建版")
    map_gil = str(core.version_path(level_name, cur_ver))
    c_cur = Container.load(map_gil)
    t_cur = parse(c_cur.proto)

    # ---- 前置④：目标实体在位 + 限额 ----
    hit = None
    for container, ents, e, body in _entity_bodies(t_cur):
        if _body_guid(body) == target_guid:
            hit = (container, ents, e, body)
            break
    if hit is None:
        raise core.PreconditionError(
            f"目标实体 0x{target_guid:x} 不在关卡 {level_name} 当前版本 f5 中")
    checks.append(("target_entity_present", "PASS"))

    _container, _ents, _e, body = hit
    comps = _slot_components(body, slot)
    cids = [c for c in (_component_cid(x) for x in comps) if c is not None]
    same = [x for x in comps if _component_cid(x) == cid]
    if same and not replace:
        raise core.PreconditionError(
            f"目标实体 0x{target_guid:x} 的 f{slot} 槽已有 cid={cid} 组件"
            f"（{len(same)} 条；限额 max_same={max_same}）——要覆盖须 replace=True")
    if same and replace and len(same) != 1:
        raise core.PreconditionError(
            f"f{slot} 槽 cid={cid} 有 {len(same)} 条，replace 只支持唯一命中")
    if not same and len(same) >= max_same:
        raise core.PreconditionError(f"f{slot} 槽 cid={cid} 计数 {len(same)} ≥ 限额 {max_same}")
    checks.append((f"slot_f{slot}_cid{cid}_within_limit",
                   f"PASS (现有{len(same)}/限额{max_same})"))

    # ---- 执行：body 就地插入/替换组件条目 ----
    t_new = parse(c_cur.proto)
    # 重新定位目标 body（在新树上就改）：container/ents/e/body 全链引用
    target_body = target_e = target_container = target_ents = None
    for container2, ents2, e2, body2 in _entity_bodies(t_new):
        if _body_guid(body2) == target_guid:
            target_container, target_ents, target_e, target_body = container2, ents2, e2, body2
            break
    if target_body is None:
        raise core.ModuleRejected("新树中目标实体消失（不应发生）")

    action = "appended"
    same_new = [x for x in target_body
                if isinstance(x, list) and x[0] == slot and x[1] == 2
                and _component_cid(x) == cid]
    if replace and same_new:
        same_new[0][2] = comp_bytes
        action = "replaced"
    else:
        # 追加：插到**尾 aid 字段 f8(varint) 之前**（= 组件条目区末尾，真实样本同序）；无则追加末
        ins = len(target_body)
        for i, nd in enumerate(target_body):
            if isinstance(nd, list) and nd[0] == 8 and nd[1] == 0:
                ins = i
                break
        target_body.insert(ins, [slot, 2, comp_bytes])
    # body → 实体 entry → ents → container（逐层重编码，否则改动不进字节）
    target_e[2] = emit(target_body)
    target_container[2] = emit(target_ents)

    tmp = core.state_dir() / "tmp" / "component_attach.gil"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    Container(c_cur.file_type, emit(t_new)).save(str(tmp))

    # ---- 后验（产物读回作证据）----
    c_out = Container.load(str(tmp))
    if not c_out or not Path(tmp).exists():
        raise core.ModuleRejected("产物不存在或不可读")
    checks.append(("roundtrip", "PASS" if emit(parse(c_out.proto)) == c_out.proto else "FAIL"))
    t_out = parse(c_out.proto)

    # 实体数不变
    n_before = len(list(_entity_bodies(t_cur)))
    n_after = len(list(_entity_bodies(t_out)))
    checks.append(("entity_count_audit",
                   f"PASS ({n_before}->{n_after})" if n_after == n_before
                   else f"FAIL ({n_before}->{n_after})"))

    # 读回：目标实体 f{slot} 槽 cid 条目在位且载荷字节 == 请求
    read_back = None
    for _c3, _e3, _e4, body3 in _entity_bodies(t_out):
        if _body_guid(body3) == target_guid:
            for x in body3:
                if (isinstance(x, list) and x[0] == slot and x[1] == 2
                        and _component_cid(x) == cid):
                    read_back = x
                    break
            break
    ok_present = read_back is not None
    ok_bytes = ok_present and parse(read_back[2]) is not None and read_back[2] == comp_bytes
    checks.append(("component_readback_present",
                   f"PASS (f{slot} cid{cid})" if ok_present else "FAIL 读回缺失"))
    checks.append(("payload_byte_equal",
                   "PASS 逐字节一致" if ok_bytes
                   else f"FAIL 载荷不一致(len {len(comp_bytes)})"))

    verdict, gate_out = asset.run_trial_gate(str(tmp))
    checks.append(("trial_gate", verdict))
    detail = next((ln.strip() for ln in gate_out.splitlines()
                   if "[SICK]" in ln or "[WARN]" in ln), "")
    if detail:
        checks.append(("gate_detail", detail[:120]))

    bad = [name for name, st in checks if isinstance(st, str) and st.startswith("FAIL")]
    if bad:
        raise core.ModuleRejected(f"后验不过: {bad}")
    if verdict != "TRIAL_PASS":
        sick = " | ".join(ln.strip() for ln in gate_out.splitlines() if "[SICK]" in ln)
        raise core.ModuleRejected(f"trial_gate 拦截: {sick or verdict}")

    n_same_after = 1 if action == "replaced" else len(same) + 1
    value = {"guid": target_guid, "cid": cid, "slot": slot, "action": action,
             "component_bytes": len(comp_bytes), "count_after": n_same_after}
    return core.Result(ok=True, artifact=str(tmp), level=level_name,
                       value=value, checks=checks)


def attach_light(level_name: str, target_guid: int, **light_kwargs) -> core.Result:
    """便捷封装：给目标实体挂一个光源组件（cid38，f7 槽）。"""
    comp = light_component(**light_kwargs)
    return component_attach(level_name, target_guid, LIGHT_CID, comp, slot=7)
