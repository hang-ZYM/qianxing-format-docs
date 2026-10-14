# -*- coding: utf-8 -*-
"""assemble.py — 装配模块 v1（vendored，本仓库开源版的只读依赖副本）.

来源：内部工作区 src/assemble.py（01b_模块化架构_v4 §四/§五 重审版，
2026-10-13）。纪律：mods/level.py 只 import 包装不改其语义；本副本相对原件
的差异仅「路径抽象」三处（逐条标注 [VENDORED-DIFF]）：
  ① qxfmt 导入自举改为「直接 import，失败回退仓库 src/」；
  ② 本机游戏目录样本路径（底座/金样本）改为经 mods.config 惰性解析，
    并保留模块属性（DEFAULT_BASE/DEFAULT_GOLD）供测试注入合成件；
  ③ check_output 增加可选 base_path 参数（V6 号域校验对同一底座复核——
    原件硬编码重读默认底座，注入合成件时口径不一致）。
合成语义、校验律、扫描器与原件逐字节同构，未动。

v0（r3 时代，按 v3 §五 实现）→ v1 重审差异 17 条（D1-D17）与全部校验结果，
见内部重审报告。本版收口 v4 头条遗留：「assemble.py v0 启用前须按
§五 v4 三条校验律重审」（v4 卷首注记 + §二 装配行）。

合成策略（铁律1 从理解生成 + M5 克隆保真）：
  基座(不动) + f10 图文档(f7 信封注入) + f5 关卡实体(克隆金样本底座，原位替换 f13 挂载，
  f11/f14/f17 编辑器组件保真) + f6 资源树注册面(tab3 实体叶 + tab4 图叶)。

出口校验（v4 §四 出口等价校验 + §五 三条校验律）：
  V0 roundtrip        字节守恒（输入 .gis 与输出 .gil 双侧）
  V1 图在位           f10 文档 guid/类别 ↔ IR 双向闭合 + f7 信封旗
  V2 宿主在位         0x414 关卡实体唯一、金样本头部保真
  V3 挂载闭合         f13 单元集合 == IR；f501 ∈ 四值挂载空间且 == 图头类别；金样本形态
  V4 图叶闭合         tab4 树形态逐字段对齐金样本；叶集合 == IR；叶类别 800
  V5 实体注册面       tab3 叶 {200, 宿主 guid}（律3：实体查 f6 树 cat100/200/300）
  V6 号域校验         图 guid ∈ 0x4000 + 命名空间查重（禁全局查重——判例#71）
                      + 宿主段位 0x414 全档防撞 + 通用段扫描器（0x478 官方自动物化
                      条目纳入扫描面——S0 无该段，跳过在案）
  V7 交叉引用闭合     每个 guid 的 出现位 = 文档meta/挂载/图叶 三位在位（律1 guid 型实做）
  P1 特效器配置ID外键  kernel93 节点 f101 → 0x478 条目池 ∪ 官方小整数集（卡15）——扫描器实做
  P2 技能资源guid直引  图内 0x41C 段 guid → f15 tcode7 池（§五律2 批次4增补/卡23）——扫描器实做
  P3 能力单元名外键   发起攻击303@i5/恢复生命583@i2 字面名 → 宿主 cid23 名集 ∪ f16
                      投射物栏（卡10）——扫描器实做（锚 2026-10-13 调研三源闭环；
                      cid23 空集时发现引用即报悬空）
  P4 运动器名称外键   运动器控制 8 节点名称@i1 → 宿主运动器组件名集（卡18）——扫描器
                      实做；闭合宿主集 PENDING-HOSTSET（cid14 现判=MPActionGroup，
                      运动器组件 cid/字节待锚——卡18 未知1）
  P5 变量名引用闭合   变量族 shell_ref 对表（★泛型特化律，调研 §0.5）@i1/@i0 →
                      f35 ∪ 同文档 22 写池 ∪ 图 f6 黑板池（卡06）——扫描器实做
                      （锚 2026-10-13；局部变量 18/19 载体制排除）
  P6 容器分层资产校验 律3：资产查 f15（双写族加查 f16+f6 树）/单容器不查树——S1 接口在位

用法：
  python src/assemble.py <a.gis> [b.gis ...] --out <out.gil> --guids 0x40000001[,..]
                         [--base <base.gil>] [--gold <gold.gil>]
  python src/assemble.py --selftest          # 生成器 vs 金样本逐字节对照
"""
import argparse
import os
import sys

# [VENDORED-DIFF ①] qxfmt 导入自举：直接 import，失败回退仓库 src/
try:
    from qxfmt.container import Container                      # noqa: E402
    from qxfmt.pbtree import parse, emit                       # noqa: E402
except ImportError:
    _REPO_SRC = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "src")
    if os.path.isdir(_REPO_SRC):
        sys.path.append(_REPO_SRC)
    from qxfmt.container import Container                      # noqa: E402
    from qxfmt.pbtree import parse, emit                       # noqa: E402


# [VENDORED-DIFF ②] 游戏目录样本路径：不再硬编码本机位置，经 mods.config 惰性
# 解析（mods/config.py 的 savelevel 领域）；模块属性可被测试注入合成件覆盖。
DEFAULT_BASE = None   # 骨架底座样本路径（None=惰性解析 <savelevel>/1073742022/…）
DEFAULT_GOLD = None   # 挂载/树金样本路径（None=惰性解析 <savelevel>/1073742025/…）
GOLD_2023 = None      # tab3 最小注册面样本路径（仅 selftest ③ 对照用）
EXPORT = None         # 导入目录不在本模块领地（见 mods/config 的 export 领域）


def _resolve_sample(which: str) -> str:
    """惰性解析默认样本：模块属性注入 > 游戏目录配置（mods.config）。

    which ∈ base（骨架底座 1073742022）/ gold（挂载金样本 1073742025）/
    gold2023（tab3 最小注册面样本 1073742023，仅 selftest 对照用）。
    """
    try:  # 常规包内加载（mods._vendor.*）
        from .. import config as _config
    except ImportError:  # 按文件路径加载（mods/level.py 的 importlib 装载）→ 绝对导入
        from mods import config as _config
    mapping = {"base": ("1073742022", "DEFAULT_BASE", "骨架底座样本"),
               "gold": ("1073742025", "DEFAULT_GOLD", "挂载金样本"),
               "gold2023": ("1073742023", "GOLD_2023", "tab3 最小注册面样本")}
    map_id, attr, what = mapping[which]
    p = _config.savelevel_sample(map_id)
    if p is not None:
        return str(p)
    raise MissingSample(
        f"{what}不可得：配置游戏目录（环境变量 QXY_GAME_SAVELEVEL，见 mods/config）"
        f"或注入 assemble.{attr}")
LEVEL_HOST_GUID = 0x41400001
HOST_ASSET_ID = 10003004                                          # 金样本宿主 f2 头/f8

# ---- v4 正典常量（01b_模块化架构_v4 §四号域段位总表 / §五 校验律）----
SEG_GRAPHS = 0x4000      # 图/预设点/UI 模板多命名空间池——禁全局查重（判例#71，卡20）。
                         # 口径：id>>16==0x4000（池起于 0x4000_0000）
SEG_HOST = 0x414         # 关卡实体（f5 层；与 f15 成长曲线双命名空间，卡14）。
                         # 口径：三位前缀 id>>20==0x414（0x41400001 族）
SEG_FX_AUTO = 0x478      # 特效器：官方自动物化占用，分配须全档扫描防撞（卡15）。
                         # 口径：三位前缀 id>>20==0x478；DUAL_WRITE_SEGMENTS 同前缀口径
MOUNT_CATEGORIES = (20000, 20003, 20005, 20007)  # f501 挂载类空间四值（卡25 全档实证）
# f15/f16 双写白名单（v4 §一 批次4 版）；经济管理面 0x428+ 不入；0x450/0x454 不双写（卡25）
DUAL_WRITE_SEGMENTS = (0x404, 0x418, 0x420, 0x470, 0x478, 0x494)
SINGLE_CONTAINER_NOTE = "单容器资产（成长曲线/预设点/技能资源/技能属性组）不查树注册（卡14/20/23 负事实）"

TREE_TAB_ENTITY, TREE_TAB_GRAPH = 3, 4
TREE_CAT_ENTITY, TREE_CAT_GRAPH = 200, 800
BRANCH_NAME_TAB3 = "未分类页签".encode("utf-8")   # 金样本 2023 tab3 分支名（15B，selftest③ 逐字节证）
BRANCH_NAME_TAB4 = "未分类页签".encode("utf-8")   # 金样本 2025 tab4 分支名（15B，selftest② 逐字节证）
MOUNT_COMPONENT_CID = 3   # f6 编辑器槽挂载组件 cid=3（载荷 f13——v4 §二偏移族表 f6 槽 cid≤20→+10；
                          # 金样本 2025/2023 挂载节点 0803 6a.. 逐字节证，selftest④）


class CheckError(AssertionError):
    pass


class MissingSample(CheckError):
    """底座/金样本不可得（环境配置问题）——前置性质，非装配质量拒绝。"""


def _require(cond, msg):
    if not cond:
        raise CheckError(msg)


def enc(n):
    out = bytearray()
    while True:
        b7 = n & 0x7F
        n >>= 7
        out.append(b7 | (0x80 if n else 0))
        if not n:
            return bytes(out)


def viv(b):
    v = 0
    for i, x in enumerate(b):
        v |= (x & 0x7F) << (7 * i)
        if not x & 0x80:
            break
    return v


def _fields(tree, field):
    return [x for x in tree if isinstance(x, list) and x[0] == field]


def _walk_varints(node, path="root", hits=None):
    """深度优先收集全部 varint 叶 (path, value)——号域扫描与引用闭合的底座。"""
    if hits is None:
        hits = []
    f, wt, body = node
    if wt == 0:
        hits.append((f"{path}.f{f}", viv(body)))
    elif wt == 2:
        try:
            for i, ch in enumerate(parse(body)):
                _walk_varints(ch, f"{path}.f{f}[{i}]", hits)
        except Exception:
            pass
    return hits


# ---------- 从理解生成的件（铁律1；形态逐字段对齐金样本） ----------

def mount_unit_inner(graph_guid, category):
    """挂载条目内芯 13B：{f1:1, f2:图guid, f501:类别}。
    金样本 2025 宿主 f13 四单元逐字节同构（0801 10<guid> a81f a09c01）。"""
    return emit([[1, 0, enc(1)], [2, 0, enc(graph_guid)], [501, 0, enc(category)]])


def mount_f6_node(mounts):
    """宿主 f6 挂载节点：{f1:cid3, f13:{ 单元×N }}，单元 = f1{f1{内芯}}。
    金样本形态：f1=挂载组件 cid3（2025 `0803 6a44..` 72B/2023 空挂载 `0803 6a00` 逐字节证）；
    单 f13 节点内重复单元（2025 四图 68B 实证）。mounts = [(guid, category)]。"""
    units = [[1, 2, emit([[1, 2, mount_unit_inner(g, c)]])] for g, c in mounts]
    body = emit([[1, 0, enc(MOUNT_COMPONENT_CID)], [13, 2, emit(units)]])
    return [6, 2, body]


def _tree_entry(tab, branch_name, leaves):
    """f6 资源树容器条目：{f1:页签, f2:{f1:"root",f3:1}, f3:{f1:页签名,f3:2,f5:[叶×N]}}。
    形态=金样本 2025 全部 43 条目同构（selftest 与 tab3/tab4 金样本逐字节对照）。"""
    name_msg = emit([[1, 2, b"root"], [3, 0, enc(1)]])
    branch = emit([[1, 2, branch_name], [3, 0, enc(2)]]
                  + [[5, 2, leaf] for leaf in leaves])
    tree = emit([[1, 0, enc(tab)], [2, 2, name_msg], [3, 2, branch]])
    return [1, 2, tree]


def graph_tab_entry(graph_guids):
    """tab4 图域注册条目：叶 {f1:800, f2:图guid}（金样本 2025 tab4 四图逐字节同构）。"""
    leaves = [emit([[1, 0, enc(TREE_CAT_GRAPH)], [2, 0, enc(g)]]) for g in graph_guids]
    return _tree_entry(TREE_TAB_GRAPH, BRANCH_NAME_TAB4, leaves)


def entity_tab_entry(host_guid):
    """tab3 实体注册条目：叶 {f1:200, f2:宿主guid}（金样本 2023 tab3 单叶同构——律3 实体注册面）。"""
    leaf = emit([[1, 0, enc(TREE_CAT_ENTITY)], [2, 0, enc(host_guid)]])
    return _tree_entry(TREE_TAB_ENTITY, BRANCH_NAME_TAB3, [leaf])


def _doc_graphs(tree):
    """产出 f10 文档内全部图树。嵌套：f10 → 信封 f1(载荷) → 载荷 f1(图体) → 图体。"""
    for nd in _fields(tree, 10):
        for pay in _fields(parse(nd[2]), 1):
            for gh in _fields(parse(pay[2]), 1):
                yield parse(gh[2])


def load_graph_doc(gis_path):
    """读 .gis → (f10 文档节点, guid, 类别)。f7 信封注入（r2 已证导入器保留）。
    图 guid 取自图头 id 块 f5（唯一权威源）；类别取 id 块 f2。"""
    c = Container.load(gis_path)
    _require(emit(parse(c.proto)) == c.proto, f"{gis_path}: 输入 .gis roundtrip 失败")
    t = parse(c.proto)
    f10 = _fields(t, 10)
    _require(len(f10) == 1, f"{gis_path}: 期望 1 个 f10 图文档节，得 {len(f10)}")
    env = parse(f10[0][2])
    payloads = _fields(env, 1)
    _require(len(payloads) == 1, f"{gis_path}: S0 期望单图载荷，得 {len(payloads)}")
    graphs = list(_doc_graphs(t))
    _require(len(graphs) == 1, f"{gis_path}: S0 期望单图，得 {len(graphs)}")
    idb_nodes = _fields(graphs[0], 1)
    _require(len(idb_nodes) == 1, f"{gis_path}: 图头 id 块缺失")
    idb = parse(idb_nodes[0][2])
    guid = next((viv(x[2]) for x in idb if x[0] == 5), None)
    cat = next((viv(x[2]) for x in idb if x[0] == 2), None)
    _require(guid is not None, f"{gis_path}: 图头 id 块无 f5 guid")
    _require(cat is not None, f"{gis_path}: 图头 id 块无 f2 类别")
    if not any(isinstance(x, list) and x[0] == 7 for x in env):
        env = env + [[7, 0, b"\x01"]]
    return [10, 2, emit(env)], guid, cat


# ---------- 克隆金样本的件（M5：语义未全解字段保真） ----------

def clone_level_host(gold_path=None, host_guid=LEVEL_HOST_GUID):
    """从金样本克隆关卡实体底座：保 f1/f2/f5/f7/f8 与 f6 槽的 f11/f14/f17（保真），
    仅摘除 f13 挂载节点（旧图引用悬空）——v0 整槽切除的过度手术收窄为定点替换。
    返回 (实体树, f13 原插入位)。gold_path=None 时经 _resolve_sample 惰性解析
    （测试可注入合成金样本路径）。"""
    gold_path = gold_path or DEFAULT_GOLD or _resolve_sample("gold")
    c = Container.load(gold_path)
    t = parse(c.proto)
    f5 = _fields(t, 5)
    _require(len(f5) == 1, f"{gold_path}: f5 容器缺失")
    for e in parse(f5[0][2]):
        if not (isinstance(e, list) and e[0] == 1):
            continue
        tree = parse(e[2])
        g = next((viv(x[2]) for x in tree if x[0] == 1 and x[1] == 0), None)
        if g != host_guid:
            continue
        pos = None
        for i, x in enumerate(tree):
            if x[0] == 6 and x[1] == 2 and any(s[0] == 13 for s in parse(x[2])):
                pos = i
                break
        _require(pos is not None, f"{gold_path}: 宿主无 f13 挂载节点")
        return tree[:pos] + tree[pos + 1:], pos
    raise CheckError(f"{gold_path}: 未找到关卡实体 0x{host_guid:x}")


def insert_sorted(tree, nodes):
    """按字段号升序插入顶层节点（编辑器全档 38 图顶层均升序；导入器规范化实证：2026）。"""
    out = list(tree)
    for nd in nodes:
        k = nd[0]
        idx = len(out)
        for i, x in enumerate(out):
            if x[0] > k:
                idx = i
                break
        out.insert(idx, nd)
    return out


# ---------- 号域分配校验（v4 §四 第一器件；S0 显式传 guid + 校验） ----------

def validate_number_domain(base_tree, graph_guids, host_guid, doc_metas, report):
    """①图 guid 段位 0x4000；②IR 自查重；③与基座图命名空间查重（禁全局查重——判例#71：
    只对同命名空间（图↔图）比对，不与 map id/UI 模板等其他 0x4000 命名空间比对——
    金样本 2025 同段共存实证：map id 0x400000C9 ∥ 图 0x40000001-04 ∥ UI 模板 0x40000010）；
    ④宿主段位 0x414；⑤通用段扫描器（0x478 官方自动物化条目纳入扫描面，卡15）。"""
    for g in graph_guids:
        _require(g >> 16 == SEG_GRAPHS,
                 f"图 guid 0x{g:x} 不在 0x{SEG_GRAPHS:x} 段（号域三律#69：图 0x4000）")
    _require(len(set(graph_guids)) == len(graph_guids), "IR 图 guid 自身撞号")

    base_graph_ids = set()
    for gt in _doc_graphs(base_tree):
        idb = _fields(gt, 1)
        if idb:
            for y in parse(idb[0][2]):
                if y[0] == 5:
                    base_graph_ids.add(viv(y[2]))
        if isinstance(nd, list) and nd[0] == 6:
            for e in parse(nd[2]):
                if not (isinstance(e, list) and e[0] == 1):
                    continue
                tr = parse(e[2])
                tab = next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None)
                if tab != TREE_TAB_GRAPH:
                    continue
                for x in tr:
                    if x[0] == 3 and x[1] == 2:
                        for b in parse(x[2]):
                            if b[0] == 5 and b[1] == 2:
                                for y in parse(b[2]):
                                    if y[0] == 2:
                                        base_graph_ids.add(viv(y[2]))
    clash = base_graph_ids & set(graph_guids)
    _require(not clash,
             f"图 guid 与基座图命名空间撞号（判例#71 口径）：{[hex(x) for x in clash]}")
    _require(host_guid >> 20 == SEG_HOST, f"宿主 guid 0x{host_guid:x} 不在 0x{SEG_HOST:x} 段")
    bad = [(g, c) for g, c in doc_metas if c not in MOUNT_CATEGORIES]
    _require(not bad, f"图类别不在 f501 四值挂载空间（卡25）: {bad}")
    report.append(f"号域: 图 {len(graph_guids)} 枚举全在 0x{SEG_GRAPHS:x} 段、无自查重、"
                  f"与基座图命名空间（{len(base_graph_ids)} 枚）无撞；宿主 0x{host_guid:x} 段位合法")


def scan_foreign_segments(out_tree, host_guid, report):
    """全档扫描防撞：宿主 guid 在产物中只允许出现在 实体身份位 + tab3 注册叶位（=2 次）；
    0x478 等资产段的条目撞号扫描随 f15/f16 接入即生效（S0 无该段——跳过在案，卡15）。"""
    hits = []
    for i, nd in enumerate(out_tree):
        if isinstance(nd, list):
            for path, v in _walk_varints(nd, f"top[{i}]"):
                if v == host_guid:
                    hits.append(path)
    _require(len(hits) == 2,
             f"宿主 guid 全档出现 {len(hits)} 次（合法位=实体身份+tab3 注册叶，应恰 2）: {hits}")
    segs = set()
    for nd in out_tree:
        if isinstance(nd, list) and nd[0] in (15, 16):
            try:
                for e in parse(nd[2]):
                    for y in parse(e[2]):
                        if y[0] == 1:
                            segs.add(viv(y[2]) >> 20)
            except Exception:
                pass
    auto_hit = sorted(segs & {SEG_FX_AUTO})
    report.append("全档防撞: 宿主 guid 恰 2 处合法位；"
                  + (f"0x{SEG_FX_AUTO:x} 自动物化段条目在册 {len(auto_hit)}——已入扫描面"
                     if auto_hit else
                     f"0x{SEG_FX_AUTO:x} 自动物化段 S0 无条目——扫描面在位，跳过在案"))


# ---------- 可插拔检查位（§五律2 名字/配置ID/guid 外键；S0 如实报实例数） ----------

KERNEL_FX_CFG = 93        # kernel93 节点数据引脚 f101={f1:特效器配置ID}（卡15 引用面）
SEG_SKILL_RES = 0x41C     # 技能资源段 guid 直引（§五律2 批次4增补/卡23：80 处/60 图）


def _iter_doc_payloads(out_tree):
    """产出 f10 文档内全部图树（与 _doc_graphs 同层；供扫描器遍历节点）。"""
    return _doc_graphs(out_tree)


def _node_kernel(node):
    for sig_f in (2, 3):
        for sig in _fields(node, sig_f):
            k = next((viv(y[2]) for y in parse(sig[2]) if y[0] == 5), None)
            if k is not None:
                return k
    return None


def scan_fx_cfgid_refs(out_tree):
    """P1 热侧扫描器（实做）：kernel93 节点子树内 f101 引脚的配置ID。"""
    refs = []
    for graph in _iter_doc_payloads(out_tree):
        for node in _fields(graph, 3):
            if _node_kernel(node) != KERNEL_FX_CFG:
                continue
            for path, v in _walk_varints(node, "node"):
                if path.endswith(".f101.f1") or ".f101[" in path and path.endswith(".f1"):
                    refs.append((path, v))
    return refs


def scan_fx_cfgid_pool(out_tree):
    """P1 冷侧池：f15 tcode32@0x478 条目 guid（官方小整数 id 空间另见卡15——同引脚混用）。"""
    pool = set()
    for nd in out_tree:
        if isinstance(nd, list) and nd[0] == 15:
            for e in parse(nd[2]):
                tr = parse(e[2])
                g = next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None)
                tc = next((viv(x[2]) for x in tr if x[0] == 2 and x[1] == 0), None)
                if g is not None and tc == 32:
                    pool.add(g)
    return pool


def scan_skill_guid_refs(out_tree):
    """P2 热侧扫描器（实做）：图载荷内全部 0x41C 段 varint（技能资源 guid 直引）。"""
    refs = []
    for gi, graph in enumerate(_iter_doc_payloads(out_tree)):
        for ni, node in enumerate(graph):
            for path, v in _walk_varints(node, f"doc[{gi}].n[{ni}]"):
                if (v >> 20) == SEG_SKILL_RES:
                    refs.append((path, v))
    return refs


def scan_skill_guid_pool(out_tree):
    """P2 冷侧池：f15 tcode7@0x41C 条目 guid（卡23 终判）。"""
    pool = set()
    for nd in out_tree:
        if isinstance(nd, list) and nd[0] == 15:
            for e in parse(nd[2]):
                tr = parse(e[2])
                g = next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None)
                tc = next((viv(x[2]) for x in tr if x[0] == 2 and x[1] == 0), None)
                if g is not None and tc == 7:
                    pool.add(g)
    return pool


# ---- P3/P4/P5 热侧锚（runs/调研_P3P4P5锚点.md 2026-10-13：目录+标本+311 图语料三源闭环；
#      字节形态=该调研 §0.2 NodeInstance / §0.3 PinInstance / §0.4 TypedValue 正典）----

# P3 能力单元名（卡10 收口）：调用节点 kernel_ref → 能力单元名引脚 (kind=3 数据入, index)。
#   303 发起攻击@i5（语料 256/260 槽位稳定）/ 583 恢复生命@i2（13/13）。非引用面排除：
#   698 直接恢复生命无能力单元脚（k3i6=治疗标签非能力名，勿混——防假阳性）。
P3_ANCHORS = {303: (3, 5), 583: (3, 2)}
# P4 运动器名称（卡18 收口）：控制 8 节点名称引脚统一 @IN k3 i1（语料 2702 例）。
P4_NAME_PIN = (3, 1)
K_MOTION_DYNAMIC = frozenset({84, 85, 520, 775})   # 动态添加族——名称由节点入参自带，闭合豁免
K_MOTION_REF = frozenset({267, 86, 87, 88})        # 组件引用族——名称须 ∈ 宿主运动器组件名集
# P5 变量族（卡06 收口）：★泛型特化律（调研 §0.5）——按 shell_ref(f2/f5) 对家族表。
#   kernel_ref=特化 id（23-28/51-59/339-349/325/328/334/353/354…全部不在 467 目录），
#   按 kernel 对表必漏；kernel_ref 空缺=泛型未决议（结构体变量语料 400 例）——shell 口径全捕获。
P5_ENTITY_SHELLS = frozenset({22, 50, 3360})       # 实体自定义变量 写/读/快照——名字@i1
P5_BLACKBOARD_SHELLS = frozenset({323, 337})       # 图黑板变量 写/读——名字@i0（0 基省略 f2→None→0）
P5_EVENT_SHELLS = frozenset({36, 351})             # 变更事件——名字 OUT k4 i2 流出（无字面，计数）
P5_ENTITY_WRITE_SHELLS = frozenset({22})           # 动态创建池写者（官方 mhso1b9wjica：22 可为实体
                                                   # 动态创建新变量须不重名；323 黑板写仍须对 f6 声明池）
K_LOCALVAR = frozenset({18, 19})                   # 局部变量——LocalVarRef(16) 载体寻址无名字串
                                                   # （bank[18] 实证），显式排除出名字扫描
# 动态名一跳解析白名单（调研 §1.3：名字脚带 f5 边 → 对端为变量家族时取其变量名作引用名
# 近似——变量链；其余 getter 类按需扩展）。客户端图族 200016 等 200xxx 分身不在 S0 服务器图域。
_DYNAMIC_NAME_PEER = {22: 1, 50: 1, 3360: 1, 323: 0, 337: 0}
_DYNAMIC_CHAIN_MAX = 4                             # 变量链深度上限（防手造环图无限递归）


def _iter_graphs_grouped(out_tree):
    """产出 (doc序号, 图序号, 图树)——与 _doc_graphs 同路径（f10→f1→f1→图体），保留
    文档/图分组边界（P5 按文档立 22 写池、按图立 f6 黑板池需要分组）。"""
    for di, nd in enumerate(_fields(out_tree, 10)):
        try:
            payloads = _fields(parse(nd[2]), 1)
        except Exception:
            continue
        for pay in payloads:
            try:
                heads = _fields(parse(pay[2]), 1)
            except Exception:
                continue
            for gi, gh in enumerate(heads):
                try:
                    yield di, gi, parse(gh[2])
                except Exception:
                    continue


def _node_shell_id(node):
    """shell_ref(f2/f5)——UI 外壳=节点「长什么样」（=558 目录 id）。泛型节点族（P5 变量
    全家）识别的唯一合法口径：shell 恒=目录 id，特化只改 kernel（调研 §0.5 特化律）。"""
    try:
        for sig in _fields(node, 2):
            return next((viv(y[2]) for y in parse(sig[2]) if y[0] == 5), None)
    except Exception:
        pass
    return None


def _node_kernel_id(node):
    """kernel_ref(f3/f5)——逻辑内核=节点「怎么跑」（泛型节点=特化 id）。P3/P4 目标节点
    全部非泛型（语料 100% shell==kernel），按 kernel_ref 对表=按 shell 对表（调研 §0.5）。"""
    try:
        for sig in _fields(node, 3):
            return next((viv(y[2]) for y in parse(sig[2]) if y[0] == 5), None)
    except Exception:
        pass
    return None


def _node_index(node):
    """NodeInstance.f1 节点 index（边的寻址键）。"""
    try:
        return next((viv(x[2]) for x in node if x[0] == 1 and x[1] == 0), None)
    except Exception:
        return None


def _node_pins(node):
    """NodeInstance.f4[] → [(kind, index, TypedValue|None, edge|None)]（调研 §0.3：
    f1=shell_sig{f1:kind,f2:index}，f3=TypedValue，f5=边）。sig.index 0 基、=0 时省略
    f2 → 解析 None→0（手册/03 [J]）。kind：1=流程入 2=流程出 3=数据入 4=数据出。
    解析失败返回 None（与空引脚列表区分）。"""
    out = []
    try:
        for p in _fields(node, 4):
            body = parse(p[2])
            kind = idx = None
            sigs = _fields(body, 1)
            if sigs:
                s = parse(sigs[0][2])
                kind = next((viv(x[2]) for x in s if x[0] == 1), None)
                idx = next((viv(x[2]) for x in s if x[0] == 2), 0)
            tv = next((parse(x[2]) for x in _fields(body, 3)), None)
            edge = next((parse(x[2]) for x in _fields(body, 5)), None)
            out.append((kind, idx, tv, edge))
    except Exception:
        return None
    return out


def _typedvalue_string(tv):
    """TypedValue → f105{f1:utf8} 字符串字面（三锚的名字都在这，调研 §0.4）；无则 None。"""
    if tv is None:
        return None
    try:
        for s in _fields(tv, 105):
            for y in parse(s[2]):
                if y[0] == 1:
                    return y[2].decode("utf-8")
    except Exception:
        pass
    return None


def _graph_nodes_indexed(graph):
    """图体 → (节点树列表, {f1 index: 节点树})。回查用节点自己的 f1 字段索引（非画布
    序——调研 §0.3 动态值判别式踩坑注记）。"""
    nodes, by_idx = [], {}
    for e in _fields(graph, 3):
        try:
            nd = parse(e[2])
        except Exception:
            continue
        nodes.append(nd)
        i = _node_index(nd)
        if i is not None:
            by_idx[i] = nd
    return nodes, by_idx


def _pin_name_ref(node, slot, by_idx, depth=0):
    """数据入脚 (kind=3, index=slot) 的名字引用 → (name|None, prov)。
    判别式（调研 §0.3）：有 f5=动态（连边覆写默认值，边优先判）；有 f3 无 f5=静态字面
    （f105 直读）；两者皆无=空脚。prov ∈ static / dynamic-var-chain / dynamic:* /
    empty-pin / no-pin / pins-unparseable——非 static 一律不冒充解析成功。"""
    pins = _node_pins(node)
    if pins is None:
        return None, "pins-unparseable"
    for kind, idx, tv, edge in pins:
        if kind != 3 or idx != slot:
            continue
        if edge is not None:
            return _resolve_dynamic_name(edge, by_idx, depth)
        name = _typedvalue_string(tv)
        if name is not None:
            return name, "static"
        return None, "empty-pin"
    return None, "no-pin"


def _resolve_dynamic_name(edge, by_idx, depth=0):
    """动态名一跳解析（调研 §1.3/§2.3）：数据边存目的脚，f5={f1:对端节点index}——
    按对端节点自己的 f1 字段回查（_graph_nodes_indexed 的表）。对端 ∈ 变量家族
    （shell 对表 _DYNAMIC_NAME_PEER）→ 递归取其变量名（变量链：值语义近似=变量名；
    链深 _DYNAMIC_CHAIN_MAX 防环）；取不到如实返回 (None, 原因)。"""
    if depth >= _DYNAMIC_CHAIN_MAX:
        return None, "dynamic:chain-too-deep"
    try:
        peer_i = next((viv(y[2]) for y in edge if y[0] == 1), None)
    except Exception:
        peer_i = None
    if peer_i is None:
        return None, "dynamic:no-peer-index"
    peer = by_idx.get(peer_i)
    if peer is None:
        return None, "dynamic:peer-not-found"
    slot = _DYNAMIC_NAME_PEER.get(_node_shell_id(peer))
    if slot is None:
        return None, "dynamic:peer-not-whitelisted"
    name, _ = _pin_name_ref(peer, slot, by_idx, depth + 1)
    return (name, "dynamic-var-chain") if name else (None, "dynamic:chain-unresolved")


def scan_kernel_name_refs(out_tree, anchors):
    """P3/P4 共用热侧扫描器（kernel_ref 口径——两族目标节点全部非泛型，语料 100%
    shell==kernel，调研 §0.5 对照）。anchors={kernel: (kind, index)}。
    返回 refs 列表 {doc, graph, node, kernel, name, prov, where}：name=None 的实例
    （空脚/动态未解析/引脚形态异常）一并如实计数，不冒充解析成功。"""
    refs = []
    for di, gi, graph in _iter_graphs_grouped(out_tree):
        nodes, by_idx = _graph_nodes_indexed(graph)
        for nd in nodes:
            k = _node_kernel_id(nd)
            want = anchors.get(k)
            if want is None:
                continue
            name, prov = _pin_name_ref(nd, want[1], by_idx)   # want=(kind,index)，kind 恒 3 数据入
            refs.append({"doc": di, "graph": gi, "node": _node_index(nd), "kernel": k,
                         "name": name, "prov": prov,
                         "where": f"doc{di}#g{gi}@node{_node_index(nd)}"})
    return refs


def scan_var_name_refs(out_tree):
    """P5 热侧扫描器（实做·★泛型特化律口径）：shell_ref(f2/f5) 对家族表——变量全家=
    泛型节点，kernel_ref=特化 id 对表必漏、空缺=未决议（调研 §0.5/§三）。
    返回 {"writes": {doc: 名集（22 静态写=动态创建豁免池）}, "reads": [50/3360 实体变量读],
    "blackboard": [323/337 图变量读写], "events": 事件族 36/351 计数}。
    局部变量 18/19 显式排除（LocalVarRef(16) 载体寻址无名字串）。"""
    writes, reads, bb, events = {}, [], [], 0
    for di, gi, graph in _iter_graphs_grouped(out_tree):
        nodes, by_idx = _graph_nodes_indexed(graph)
        for nd in nodes:
            shell = _node_shell_id(nd)
            if shell is None or shell in K_LOCALVAR:
                continue
            if shell in P5_EVENT_SHELLS:
                events += 1                     # 名字 OUT k4 i2 流出，无字面可扫（调研 §3.1）
                continue
            if shell in P5_ENTITY_SHELLS:
                slot, is_entity = 1, True
            elif shell in P5_BLACKBOARD_SHELLS:
                slot, is_entity = 0, False      # index=0 正典省略 f2
            else:
                continue
            name, prov = _pin_name_ref(nd, slot, by_idx)
            rec = {"doc": di, "graph": gi, "shell": shell, "name": name, "prov": prov,
                   "where": f"doc{di}#g{gi}@shell{shell}"}
            if is_entity:
                if shell in P5_ENTITY_WRITE_SHELLS and prov == "static":
                    writes.setdefault(di, set()).add(name)   # 22 写=动态创建池（同文档豁免）
                else:
                    reads.append(rec)                        # 50/3360 读=闭合对象
            else:
                bb.append(rec)               # 323/337 读写都须对 f6 声明池（黑板无动态创建）
    return {"writes": writes, "reads": reads, "blackboard": bb, "events": events}


def _collect_utf8_leaves(nodes, hits):
    """消息子树内全部 utf8 字符串叶（parse 失败且 utf8 可解码的字节叶=字符串叶）。"""
    for nd in nodes:
        if not (isinstance(nd, list) and len(nd) == 3 and isinstance(nd[0], int)):
            continue
        if nd[1] != 2:
            continue
        try:
            _collect_utf8_leaves(parse(nd[2]), hits)
        except Exception:
            try:
                hits.add(nd[2].decode("utf-8"))
            except Exception:
                pass


def _collect_strings_under(nodes, fieldno, hits=None):
    """字段号==fieldno 的消息子树内全部 utf8 字符串叶。冷侧池过近似口径：只放宽不收紧
    （闭合校验宁可漏报、不误报悬空）。"""
    if hits is None:
        hits = set()
    for nd in nodes:
        if not (isinstance(nd, list) and len(nd) == 3 and isinstance(nd[0], int)):
            continue
        f, wt, body = nd
        if wt != 2:
            continue
        try:
            ch = parse(body)
        except Exception:
            if f == fieldno:
                try:
                    hits.add(body.decode("utf-8"))
                except Exception:
                    pass
            continue
        if f == fieldno:
            _collect_utf8_leaves(ch, hits)
        else:
            _collect_strings_under(ch, fieldno, hits)
    return hits


def _host_cid23_names(out_tree):
    """P3 冷侧池①：f5 实体的 cid23 能力单元容器组件名集（卡10 已立形态：组件体
    {f1:序号, f23:{f1:{f3:"能力单元名"}}} 仅名字形态在档）。cid23 参数体落点未实证
    （卡10 未知1）——名集取组件体内 f23 子树字符串过近似。S0 宿主无 cid23 → 空集；
    空集时发现引用即报悬空（v4 §五律2 P3 闭合口径）。"""
    names = set()
    for nd in _fields(out_tree, 5):
        try:
            ents = parse(nd[2])
        except Exception:
            continue
        for e in ents:
            if not (isinstance(e, list) and e[0] == 1):
                continue
            try:
                tr = parse(e[2])
            except Exception:
                continue
            for x in tr:
                if not (x[0] == 6 and x[1] == 2):
                    continue
                try:
                    comp = parse(x[2])
                except Exception:
                    continue
                cid = next((viv(y[2]) for y in comp if y[0] == 1 and y[1] == 0), None)
                if cid == 23:
                    _collect_strings_under(comp, 23, names)
    return names


def _projectile_ability_names(out_tree):
    """P3 冷侧池②：f16 投射物域条目的段 21 能力单元栏名集（卡10；f16 归卡25 双写族）。
    S0 无 f16 → 空集；条目内精确嵌套待 f16 域接入（S1）时按金样本校准——过近似同上。"""
    names = set()
    for nd in _fields(out_tree, 16):
        try:
            entries = parse(nd[2])
        except Exception:
            continue
        for e in entries:
            if not (isinstance(e, list) and e[0] == 1):
                continue
            try:
                names |= _collect_strings_under(parse(e[2]), 21)
            except Exception:
                continue
    return names


def _f35_names(out_tree):
    """P5 冷侧池①：地图 f35 变量注册表名集（卡06：名字即契约）。S0 基座无 f35 → 空集。
    记录精确形态归卡06 域——此处取子树全字符串叶过近似。f35 本体不可字节写（卡06 硬
    约束），新增变量名走 E 线模型级 RepeatedField.Add；扫描器只报「引用 ∩ 声明=∅」。"""
    names = set()
    for nd in _fields(out_tree, 35):
        try:
            _collect_utf8_leaves(parse(nd[2]), names)
        except Exception:
            continue
    return names


def _blackboard_pools(out_tree):
    """P5 冷侧池②：图内 f6 黑板声明池 {(doc,graph): 名集}（调研 §三：图 f6=
    {f2:变量名, f3:base_type, f4:初始值, f5:is_public, f7/f8:容器子型}；官方限额单图 ≤100）。"""
    pools = {}
    for di, gi, graph in _iter_graphs_grouped(out_tree):
        names = set()
        for e in _fields(graph, 6):
            try:
                for y in parse(e[2]):
                    if y[0] == 2:
                        try:
                            names.add(y[2].decode("utf-8"))
                        except Exception:
                            continue
            except Exception:
                continue
        pools[(di, gi)] = names
    return pools


def pluggable_checks(out_tree, report):
    """返回 [(名称, 状态, 说明)]。状态：PASS（实做校验通过）/ TRIVIAL（0 实例平凡通过，
    扫描器实做）/ PENDING-ANCHOR（结构在位，热侧字节锚未定位——如实报，不冒充 0 实例）/
    PENDING-HOSTSET（热侧扫描器实做、冷侧宿主名集取法未钉）/ PENDING-S1（接口在位待
    资产 layer）/ FAIL（悬空引用拦截）。"""
    rows = []
    # P1 特效器配置ID（实做扫描器）
    refs = scan_fx_cfgid_refs(out_tree)
    pool = scan_fx_cfgid_pool(out_tree)
    if not refs:
        rows.append(("P1 特效器配置ID外键(kernel93 f101)", "TRIVIAL",
                     "0 实例平凡通过（扫描器实做）；冷侧 0x478 池 0 条目"))
    else:
        missing = sorted({v for _, v in refs} - pool)
        rows.append(("P1 特效器配置ID外键(kernel93 f101)",
                     "PASS" if not missing else "FAIL",
                     f"{len(refs)} 处引用；冷侧池 {len(pool)} 条目"
                     + (f"；缺 {['0x%x' % x for x in missing]}" if missing else "")))
    # P2 技能资源 guid 直引（实做扫描器）
    refs = scan_skill_guid_refs(out_tree)
    pool = scan_skill_guid_pool(out_tree)
    if not refs:
        rows.append(("P2 技能资源guid直引(0x41C)", "TRIVIAL",
                     "0 实例平凡通过（扫描器实做）；冷侧 tcode7 池 0 条目"))
    else:
        missing = sorted({v for _, v in refs} - pool)
        rows.append(("P2 技能资源guid直引(0x41C)",
                     "PASS" if not missing else "FAIL",
                     f"{len(refs)} 处引用；冷侧池 {len(pool)} 条目"
                     + (f"；缺 {['0x%x' % x for x in missing]}" if missing else "")))
    # P3 能力单元名外键（扫描器实做，锚 2026-10-13：kernel303@i5/583@i2，三源闭环）
    refs = scan_kernel_name_refs(out_tree, P3_ANCHORS)
    host_names = _host_cid23_names(out_tree)
    proj_names = _projectile_ability_names(out_tree)
    if not refs:
        rows.append(("P3 能力单元名外键(发起攻击/恢复生命→cid23 名集)", "TRIVIAL",
                     "0 实例平凡通过（扫描器实做：kernel303@i5/583@i2 f105 字面＋f5 动态边判别）；"
                     f"冷侧池 cid23 {len(host_names)} 枚 ∪ 投射物栏 {len(proj_names)} 枚"))
    else:
        named = {r["name"] for r in refs if r["name"] is not None}
        unresolved = sum(1 for r in refs if r["name"] is None)
        missing = sorted(named - host_names - proj_names)
        detail = (f"{len(refs)} 处引用（静态/变量链 {len(named)} 名，未解析动态/形态异常 "
                  f"{unresolved} 处）；冷侧池 cid23 {len(host_names)} ∪ 投射物栏 "
                  f"{len(proj_names)} 枚")
        if missing:
            rows.append(("P3 能力单元名外键(发起攻击/恢复生命→cid23 名集)", "FAIL",
                         detail + f"；悬空 {missing[:8]}"
                         + (f" 等 {len(missing)} 名" if len(missing) > 8 else "")
                         + "（cid23 空集=引用即悬空；参数体落点卡10 未知1 待验）"))
        else:
            rows.append(("P3 能力单元名外键(发起攻击/恢复生命→cid23 名集)", "PASS",
                         detail + (f"（未解析动态 {unresolved} 处不判，白名单外）"
                                   if unresolved else "")))
    # P4 运动器名称外键（扫描器实做，锚 2026-10-13：控制 8 节点名称统一@i1，语料 2702 例）
    refs = scan_kernel_name_refs(
        out_tree, {k: P4_NAME_PIN for k in (K_MOTION_DYNAMIC | K_MOTION_REF)})
    if not refs:
        rows.append(("P4 运动器名称外键(运动器控制节点→宿主组件名集)", "TRIVIAL",
                     "0 实例平凡通过（扫描器实做：84/85/520/775/267/86/87/88 名称@i1，"
                     "动态添加/组件引用两分类）"))
    else:
        comp = [r for r in refs if r["kernel"] in K_MOTION_REF]
        dyn = [r for r in refs if r["kernel"] in K_MOTION_DYNAMIC]
        # 闭合目标（宿主运动器组件名集）取法 PENDING：卡18 的「cid14=运动器」已被审计推翻，
        # cid14 现判=MPActionGroup（mods/entity.py 修正语境）；运动器组件的 cid 与字节形态
        # 未钉（卡18 未知1）——引用清单先行出件、组件引用类闭合待锚。动态添加类官方豁免
        # （名称由节点入参自带、不需宿主预配置——调研 §2.1 语料实证：魔林境 k84 该图 cid14 零）。
        rows.append(("P4 运动器名称外键(运动器控制节点→宿主组件名集)", "PENDING-HOSTSET",
                     f"{len(refs)} 处引用（组件引用类 {len(comp)}："
                     f"{sorted({r['name'] for r in comp if r['name']})[:6]}"
                     f"{' 等' if len({r['name'] for r in comp if r['name']}) > 6 else ''}；"
                     f"动态添加类 {len(dyn)} 豁免）；宿主名集取法 PENDING-HOSTSET"
                     "（cid14 现判=MPActionGroup，运动器组件 cid/字节待锚——卡18 未知1）"))
    # P5 变量名引用闭合（扫描器实做，★泛型特化律 shell 口径，锚 2026-10-13）
    vr = scan_var_name_refs(out_tree)
    pools = _blackboard_pools(out_tree)
    f35 = _f35_names(out_tree)
    ent_refs, bb_refs = vr["reads"], vr["blackboard"]
    if not ent_refs and not bb_refs and vr["events"] == 0:
        rows.append(("P5 变量名引用闭合(图→f35 ∪ 黑板池 ∪ 宿主变量组件池)", "TRIVIAL",
                     "0 实例平凡通过（扫描器实做：变量族 shell 对表 22/50/3360@i1＋323/337@i0，"
                     "事件 36/351 计数，局部变量 18/19 载体制排除）；f35 0 条目"))
    else:
        writes_all = set().union(*vr["writes"].values()) if vr["writes"] else set()
        ent_missing = sorted({r["name"] for r in ent_refs if r["name"] is not None}
                             - f35 - writes_all)
        bb_missing = sorted({r["name"] for r in bb_refs if r["name"] is not None
                             and r["name"] not in pools.get((r["doc"], r["graph"]), set())})
        unresolved = sum(1 for r in ent_refs + bb_refs if r["name"] is None)
        detail = (f"实体变量读 {len(ent_refs)}（22 写池/文档 "
                  f"{ {d: len(s) for d, s in vr['writes'].items()} }）∪ f35 {len(f35)} 枚；"
                  f"图变量 {len(bb_refs)}（f6 池合计 {sum(len(p) for p in pools.values())} 枚）；"
                  f"事件族 {vr['events']} 例（名字 OUT k4i2 流出无字面）")
        missing = [("实体变量", n) for n in ent_missing] + [("图变量", n) for n in bb_missing]
        if missing:
            rows.append(("P5 变量名引用闭合(图→f35 ∪ 黑板池 ∪ 宿主变量组件池)", "FAIL",
                         detail + f"；悬空 {missing[:8]}"
                         + (f" 等 {len(missing)} 名" if len(missing) > 8 else "")))
        else:
            rows.append(("P5 变量名引用闭合(图→f35 ∪ 黑板池 ∪ 宿主变量组件池)", "PASS",
                         detail + (f"（未解析动态 {unresolved} 处不判）" if unresolved else "")))
    # P6 容器分层资产校验（律3；S1 资产 layer 接口）
    f15 = _fields(out_tree, 15)
    n_entries = 0
    if f15:
        try:
            n_entries = len(parse(f15[0][2]))
        except Exception:
            n_entries = -1
    if n_entries == 0:
        rows.append(("P6 容器分层资产校验(律3)", "TRIVIAL",
                     f"0 资产平凡通过；双写族 {['0x%x' % s for s in DUAL_WRITE_SEGMENTS]} 与"
                     f"单容器规则在位（{SINGLE_CONTAINER_NOTE}）"))
    else:
        rows.append(("P6 容器分层资产校验(律3)", "PENDING-S1",
                     f"f15 条目 {n_entries}——S1 资产 layer 接入后按双写族查 f15+f16+f6 树"))
    return rows


# ---------- 出口等价校验（v4 §四 + §五三律） ----------

def assemble(gis_paths, out_path, graph_guids, base_path=None, gold_path=None,
             host_guid=LEVEL_HOST_GUID, categories=None):
    """基座 + 图文档(f10) + 关卡实体(f5, 原位挂载) + 资源树注册面(f6 tab3+tab4) → .gil。
    graph_guids：显式传参（S0 单一权威来源）；categories：缺省从各 .gis 图头读取。
    base_path/gold_path：None=模块属性注入 > mods.config 游戏目录样本（[VENDORED-DIFF ②]）。"""
    base_path = base_path or DEFAULT_BASE or _resolve_sample("base")
    gold_path = gold_path or DEFAULT_GOLD or _resolve_sample("gold")
    docs, metas = [], []
    for g in gis_paths:
        doc, guid, cat = load_graph_doc(g)
        docs.append(doc)
        metas.append((guid, cat))
    _require(set(graph_guids) == {g for g, _ in metas},
             f"--guids {['0x%x' % x for x in graph_guids]} 与 .gis 图头 guid "
             f"{['0x%x' % g for g, _ in metas]} 不一致")
    cat_of = {g: (categories or {}).get(g, c) for g, c in metas}

    base = Container.load(base_path)
    t = parse(base.proto)
    report = []
    validate_number_domain(t, graph_guids, host_guid, [(g, cat_of[g]) for g in graph_guids], report)

    host, pos = clone_level_host(gold_path, host_guid)
    host = host[:pos] + [mount_f6_node([(g, cat_of[g]) for g in graph_guids])] + host[pos:]
    f5_field = [5, 2, emit([[1, 2, emit(host)]])]
    f6_field = [6, 2, emit([entity_tab_entry(host_guid)] + [graph_tab_entry(graph_guids)])]
    t = insert_sorted(t, [f5_field, f6_field] + docs)

    out = Container(base.file_type, emit(t))
    out.save(out_path)
    scan_foreign_segments(parse(out.proto), host_guid, report)
    return out_path, metas, report


def check_output(out_path, graph_guids, host_guid=LEVEL_HOST_GUID, base_path=None):
    """出口等价校验。返回 (fail_count, lines)。结构项 FAIL 即失败；可插拔位如实报状态。
    base_path：V6 号域校验的复核底座；None=模块属性注入 > 游戏目录默认样本
    （[VENDORED-DIFF ③]——原件此处硬编码重读默认底座，注入合成件时口径不一致）。"""
    lines, fails = [], 0
    c = Container.load(out_path)
    t = parse(c.proto)

    def ok(name, detail=""):
        lines.append(f"[PASS] {name} {detail}")

    def fail(name, detail=""):
        nonlocal fails
        fails += 1
        lines.append(f"[FAIL] {name} {detail}")

    # V0 roundtrip（输出侧）
    try:
        _require(emit(parse(c.proto)) == c.proto, "roundtrip 失败")
        ok("V0 roundtrip", f"{len(c.proto)}B proto")
    except CheckError as e:
        fail("V0 roundtrip", str(e))

    # V1 图在位：文档 guid/类别 ↔ IR 双向 + f7 信封旗
    try:
        docs = _fields(t, 10)
        got = []
        for d in docs:
            env = parse(d[2])
            _require(any(x[0] == 7 and x[2] == b"\x01" for x in env), "信封 f7 旗缺失")
            for gt in _doc_graphs([d]):
                idb = parse(_fields(gt, 1)[0][2])
                got.append((next(viv(x[2]) for x in idb if x[0] == 5),
                            next(viv(x[2]) for x in idb if x[0] == 2)))
        _require({g for g, _ in got} == set(graph_guids) and len(got) == len(graph_guids),
                 f"文档 guid 集 {['0x%x' % g for g, _ in got]} != IR")
        ok("V1 图在位", f"{len(docs)} 文档 / {len(got)} 图，f7 信封旗在位")
    except CheckError as e:
        fail("V1 图在位", str(e))

    # V2+V3 宿主在位 + 挂载闭合
    try:
        f5 = _fields(t, 5)
        _require(len(f5) == 1, "f5 容器缺失")
        ents = parse(f5[0][2])
        hosts = []
        for e in ents:
            if not (isinstance(e, list) and e[0] == 1):
                continue
            tr = parse(e[2])
            g = next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None)
            if g == host_guid:
                hosts.append(tr)
        _require(len(hosts) == 1, f"宿主 0x{host_guid:x} 出现 {len(hosts)} 次")
        host = hosts[0]
        head = _fields(host, 2)
        _require(head and viv(parse(head[0][2])[0][2]) == HOST_ASSET_ID,
                 "宿主 f2 头 asset_id 与金样本不符")
        f6s = [x for x in host if x[0] == 6 and x[1] == 2]
        _require(len(f6s) == 4, f"宿主 f6 节点数 {len(f6s)} != 金样本 4（f11/f13/f14/f17）")
        f7s = [x for x in host if x[0] == 7]
        _require(f7s and host.index(f6s[-1]) < host.index(f7s[0]),
                 "实体字段序违背金样本（f6 应先于 f7）")
        f13_nodes = [x for x in f6s if any(s[0] == 13 for s in parse(x[2]))]
        _require(len(f13_nodes) == 1, f"f13 载体 f6 节点数 {len(f13_nodes)} != 1")
        mt = parse(f13_nodes[0][2])
        cid = next((viv(s[2]) for s in mt if s[0] == 1), None)
        _require(cid == MOUNT_COMPONENT_CID,
                 f"挂载组件 cid {cid} != {MOUNT_COMPONENT_CID}（金样本 0803 前缀）")
        f13 = [s for s in mt if s[0] == 13]
        _require(len(f13) == 1, f"f13 节点数 {len(f13)} != 1（金样本=单 f13 重复单元）")
        units = []
        for u in parse(f13[0][2]):
            inner = parse(parse(u[2])[0][2])
            units.append((next(viv(y[2]) for y in inner if y[0] == 2),
                          next(viv(y[2]) for y in inner if y[0] == 501),
                          next(viv(y[2]) for y in inner if y[0] == 1)))
        _require(sorted(g for g, _, _ in units) == sorted(graph_guids),
                 f"挂载闭合失败: {['0x%x' % g for g, _, _ in units]}")
        doc_cat = {}
        for gt in _doc_graphs(t):
            idb = parse(_fields(gt, 1)[0][2])
            doc_cat[next(viv(x[2]) for x in idb if x[0] == 5)] = \
                next(viv(x[2]) for x in idb if x[0] == 2)
        for g, cat, flag in units:
            _require(cat in MOUNT_CATEGORIES, f"挂载 f501={cat} 不在四值空间")
            _require(cat == doc_cat.get(g),
                     f"挂载 0x{g:x} f501={cat} != 图头类别 {doc_cat.get(g)}（挂错宿主类型=永聋 #65）")
            _require(flag == 1, f"挂载 0x{g:x} 内芯 f1 {flag} != 1")
        ok("V2 宿主在位", f"0x{host_guid:x} 唯一，f2/f8={HOST_ASSET_ID}，字段序 f6<f7")
        ok("V3 挂载闭合", f"{len(units)} 单元金样本形态（cid3+f13 单元），f501 四值空间内")
    except CheckError as e:
        fail("V2/V3 宿主/挂载", str(e))

    # V4 图叶闭合（tab4 结构逐字段） + V5 实体注册面（tab3）
    try:
        f6 = _fields(t, 6)
        _require(len(f6) == 1, "f6 容器缺失")
        entries = [parse(e[2]) for e in parse(f6[0][2]) if isinstance(e, list) and e[0] == 1]
        by_tab = {}
        for tr in entries:
            tab = next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None)
            by_tab[tab] = tr
        tr4 = by_tab.get(TREE_TAB_GRAPH)
        _require(tr4 is not None, "tab4 图域注册条目缺失")
        nm = _fields(tr4, 2)
        _require(nm and parse(nm[0][2]) == [[1, 2, b"root"], [3, 0, enc(1)]],
                 "tab4 root 名消息形态不符金样本")
        brs = _fields(tr4, 3)
        _require(len(brs) == 1, "tab4 分支数 != 1")
        br = parse(brs[0][2])
        bname = next((x[2] for x in br if x[0] == 1), None)
        _require(bname == BRANCH_NAME_TAB4, f"tab4 分支名 {bname!r} != 金样本「未分类页签」")
        _require(any(x[0] == 3 and viv(x[2]) == 2 for x in br), "tab4 分支 f3 != 2")
        leaves = []
        for b in br:
            if b[0] == 5 and b[1] == 2:
                lt = parse(b[2])
                leaves.append((next(viv(y[2]) for y in lt if y[0] == 2),
                               next(viv(y[2]) for y in lt if y[0] == 1)))
        _require(sorted(g for g, _ in leaves) == sorted(graph_guids),
                 f"图叶闭合失败: {['0x%x' % g for g, _ in leaves]}")
        _require(all(c == TREE_CAT_GRAPH for _, c in leaves), "图叶类别 != 800")
        ok("V4 图叶闭合", f"tab4 金样本形态（root/未分类页签/f3=2），{len(leaves)} 叶类别 800")
        tr3 = by_tab.get(TREE_TAB_ENTITY)
        _require(tr3 is not None, "tab3 实体注册条目缺失（律3 实体注册面）")
        leaf3 = []
        for x in tr3:
            if x[0] == 3 and x[1] == 2:
                for b in parse(x[2]):
                    if b[0] == 5 and b[1] == 2:
                        lt = parse(b[2])
                        leaf3.append((next(viv(y[2]) for y in lt if y[0] == 2),
                                      next(viv(y[2]) for y in lt if y[0] == 1)))
        _require((host_guid, TREE_CAT_ENTITY) in leaf3,
                 f"tab3 无宿主注册叶 {{200, 0x{host_guid:x}}}")
        ok("V5 实体注册面", f"tab3 叶 {{200, 0x{host_guid:x}}} 在位（金样本 2023 同构）")
    except CheckError as e:
        fail("V4/V5 资源树", str(e))

    # V6 号域 + V7 交叉引用闭合
    try:
        rep = []
        v6_base = base_path or DEFAULT_BASE or _resolve_sample("base")
        validate_number_domain(parse(Container.load(v6_base).proto),
                               graph_guids, host_guid,
                               [(g, MOUNT_CATEGORIES[0]) for g in graph_guids], rep)
        ok("V6 号域校验", rep[0] if rep else "")
    except CheckError as e:
        fail("V6 号域校验", str(e))
    try:
        for g in graph_guids:
            regions = {"doc": 0, "mount": 0, "tree": 0}
            stranger = []
            for i, nd in enumerate(t):
                if not isinstance(nd, list):
                    continue
                for p, v in _walk_varints(nd, f"top[{i}]"):
                    if v != g:
                        continue
                    # 路径段名滞后一层（父字段号+子序号），按父节点标记分区
                    if ".f13[" in p:
                        regions["mount"] += 1
                    elif ".f10[" in p:
                        regions["doc"] += 1
                    elif ".f6[" in p:
                        regions["tree"] += 1
                    else:
                        stranger.append(p)
            _require(not stranger,
                     f"0x{g:x} 出现在闭合三位之外（悬空引用嫌疑）: {stranger}")
            _require(regions["doc"] >= 1 and regions["mount"] >= 1 and regions["tree"] >= 1,
                     f"0x{g:x} 三位闭合缺: {dict(regions)}")
        ok("V7 交叉引用闭合",
           f"{len(graph_guids)} guid 全档三位在位（图文档/挂载/图叶），无三位外悬空出现")
    except CheckError as e:
        fail("V7 交叉引用闭合", str(e))

    # 可插拔位
    rep2 = []
    scan_foreign_segments(t, host_guid, rep2)
    lines.append(f"[INFO] {rep2[1] if len(rep2) > 1 else ''}")
    for name, status, detail in pluggable_checks(t, []):
        lines.append(f"[{status}] {name} — {detail}")
        if status == "FAIL":
            fails += 1
    return fails, lines


# ---------- 扫描器负向自测（纪律：手工病图必须拦截；锚 2026-10-13 接入） ----------

def _hand_pin(kind, index, text=None, edge_peer=None):
    """手工 PinInstance：sig{f1:kind, f2:index(0 省略)} + TypedValue{f1:5 字符串槽,
    f4:{f1:1,f100:{f1:6}}, f105:{f1:"text"}} 或边 f5={f1:peer}（调研 §0.3/§0.4 正典）。"""
    sig = [[1, 0, enc(kind)]] + ([[2, 0, enc(index)]] if index else [])
    body = [[1, 2, emit(sig)]]
    if edge_peer is not None:
        body.append([5, 2, emit([[1, 0, enc(edge_peer)]])])
    elif text is not None:
        body.append([3, 2, emit([
            [1, 0, enc(5)],
            [4, 2, emit([[1, 0, enc(1)], [100, 2, emit([[1, 0, enc(6)]])]])],
            [105, 2, emit([[1, 2, text.encode("utf-8")]])]])])
    return emit(body)


def _hand_node(index, kernel, pins, shell=None):
    """手工 NodeInstance：{f1:index, f2:shell_ref{f5:shell}, f3:kernel_ref{f5:kernel},
    f4:[pin×N]}（调研 §0.2；f5/f6 画布坐标省略——扫描器不读坐标）。"""
    shell = kernel if shell is None else shell
    return emit([[1, 0, enc(index)],
                 [2, 2, emit([[5, 0, enc(shell)]])],
                 [3, 2, emit([[5, 0, enc(kernel)]])]]
                + [[4, 2, p] for p in pins])


def _hand_doc(graph_bodies):
    """手工 f10 图文档：f10 → f1 信封载荷 → f1 图头 → 图体（_doc_graphs 同路径）。"""
    return [10, 2, emit([[1, 2, emit([[1, 2, g] for g in graph_bodies])]])]


def scanner_selftest():
    """P3/P4/P5 扫描器自测（2026-10-13 锚接入）。①平凡对照（无锚引用图→三行全 TRIVIAL，
    S0 预期形态）②P3 病图必拦截 ③P5 黑板病图必拦截（特化律：kernel=特化 id/shell=目录
    id）④P5 22 动态创建豁免＋读未声明名拦截 ⑤P4 引用出件＋闭合 PENDING 如实报
    ⑥动态边判别（f5 边→变量链解析→入集拦截）。返回 (fails, lines)。"""
    lines, fails = [], []

    def run(graph_bodies):
        return pluggable_checks([_hand_doc(graph_bodies)], [])

    def row(rows, key):
        return next(r for r in rows if r[0].startswith(key))

    def expect(name, cond, detail=""):
        ok = bool(cond)
        lines.append(f"[{'PASS' if ok else 'FAIL'}] 扫描自测 {name} {detail}")
        if not ok:
            fails.append(name)

    # ① 平凡对照：无锚引用图（kernel71/1 常规节点）→ P3/P4/P5 全 TRIVIAL
    plain = emit([[3, 2, _hand_node(1, 71, [_hand_pin(2, 0)])],
                  [3, 2, _hand_node(2, 1, [_hand_pin(1, 0), _hand_pin(3, 0, "普通文本")])]])
    rows = run([plain])
    expect("① 无锚引用图 P3/P4/P5 全 TRIVIAL（S0 预期形态）",
           row(rows, "P3")[1] == "TRIVIAL" and row(rows, "P4")[1] == "TRIVIAL"
           and row(rows, "P5")[1] == "TRIVIAL")

    # ② P3 病图：kernel303 + 能力单元脚 k3i5「攻击盒」字面（bank[303] 同构）
    #    宿主 cid23 空集 → 引用即悬空 → 必须 FAIL 拦截
    sick303 = emit([[3, 2, _hand_node(1, 303,
                                      [_hand_pin(1, 0), _hand_pin(3, 5, "攻击盒")])]])
    r3 = row(run([sick303]), "P3")
    expect("② P3 病图(kernel303@i5 字面·cid23 空集)被拦截 FAIL",
           r3[1] == "FAIL" and "攻击盒" in r3[2], f"got {r3[1]}")

    # ③ P5 黑板病图：337 读未声明图变量 @i0（特化律：kernel=339 特化 id / shell=337 目录 id
    #    ——按 kernel 对表必漏、按 shell 对表命中，正是调研 §0.5 钉的铁律）→ f6 池空 → FAIL
    sick337 = emit([[3, 2, _hand_node(1, 339, [_hand_pin(3, 0, "未声明变量")], shell=337)]])
    r5 = row(run([sick337]), "P5")
    expect("③ P5 病图(337 特化 kernel339@i0 读未声明黑板名)被拦截 FAIL",
           r5[1] == "FAIL" and "未声明变量" in r5[2], f"got {r5[1]}")

    # ④ P5 动态创建豁免：22(特化23)写「分数」＋50(特化51)读「分数」同文档 → 不悬空 PASS；
    #    ④b 读无 22 写池且 f35 空的名 → FAIL
    exempt = emit([[3, 2, _hand_node(1, 23, [_hand_pin(3, 1, "分数")], shell=22)],
                   [3, 2, _hand_node(2, 51, [_hand_pin(3, 1, "分数")], shell=50)]])
    expect("④ P5 实体变量：同文档 22 写池豁免 50 读 → PASS",
           row(run([exempt]), "P5")[1] == "PASS")
    sick50 = emit([[3, 2, _hand_node(1, 51, [_hand_pin(3, 1, "没人写过")], shell=50)]])
    expect("④b P5 实体变量读未声明名（无 f35/无 22 写池）→ FAIL",
           row(run([sick50]), "P5")[1] == "FAIL")

    # ⑤ P4：267 组件引用类引用被扫描出件；闭合宿主集 PENDING-HOSTSET（cid14=MPActionGroup
    #    修正语境）——不冒充闭合、也不冒充 0 实例
    sick267 = emit([[3, 2, _hand_node(1, 267, [_hand_pin(3, 1, "向外-50度")])]])
    r4 = row(run([sick267]), "P4")
    expect("⑤ P4 病图(267@i1)引用出件且状态=PENDING-HOSTSET（不冒充闭合）",
           r4[1] == "PENDING-HOSTSET" and "向外-50度" in r4[2], f"got {r4[1]}")

    # ⑥ 动态边判别（调研 §0.3）：303 名字脚带 f5 边（无 f3）→ 对端 50 变量链解析出名字
    #    → 入引用集 → cid23 空集 → FAIL 拦截
    dyn = emit([[3, 2, _hand_node(1, 303,
                                  [_hand_pin(1, 0), _hand_pin(3, 5, edge_peer=2)])],
                [3, 2, _hand_node(2, 51, [_hand_pin(3, 1, "动态名")], shell=50)]])
    r6 = row(run([dyn]), "P3")
    expect("⑥ P3 动态名(f5 边→50 变量链)解析入集 → 悬空拦截",
           r6[1] == "FAIL" and "动态名" in r6[2], f"got {r6[1]}")

    return len(fails), lines


def selftest():
    """自证两件：①-③ 生成器 vs 金样本逐字节对照（铁律1 从理解生成可复现金样本字节）
    ④ P3/P4/P5 扫描器自测（2026-10-13 锚接入：手工病图必拦截＋平凡对照，scanner_selftest）。
    金样本经 _resolve_sample 惰性解析（GOLD_2023 缺省=游戏目录 2023 样本；测试可注入）。"""
    gold = Container.load(DEFAULT_GOLD or _resolve_sample("gold"))
    gt = parse(gold.proto)
    lines, fails = [], 0

    # ① 挂载 f13 节点体（4 图 20000）
    gold_f13_body = None
    for x in parse(gold.proto):
        if isinstance(x, list) and x[0] == 5:
            for e in parse(x[2]):
                if not (isinstance(e, list) and e[0] == 1):
                    continue
                tr = parse(e[2])
                if next((viv(y[2]) for y in tr if y[0] == 1 and y[1] == 0), None) != LEVEL_HOST_GUID:
                    continue
                for y in tr:
                    if y[0] == 6 and y[1] == 2:
                        for s in parse(y[2]):
                            if s[0] == 13:
                                gold_f13_body = s[2]
    ours_f13_body = emit([[1, 2, emit([[1, 2, mount_unit_inner(0x40000001 + i, 20000)]])]
                          for i in range(4)])
    same = gold_f13_body == ours_f13_body
    lines.append(f"[{'PASS' if same else 'FAIL'}] ① f13 挂载节点体 vs 金样本 2025"
                 f"（{len(ours_f13_body)}B）\n      金: {gold_f13_body.hex()}\n      仿: {ours_f13_body.hex()}")
    fails += 0 if same else 1

    # ①b 整个 f6 挂载节点（含 cid3 前缀）
    gold_f6_node = None
    for x in parse(gold.proto):
        if isinstance(x, list) and x[0] == 5:
            for e in parse(x[2]):
                if not (isinstance(e, list) and e[0] == 1):
                    continue
                tr = parse(e[2])
                if next((viv(y[2]) for y in tr if y[0] == 1 and y[1] == 0), None) != LEVEL_HOST_GUID:
                    continue
                for y in tr:
                    if y[0] == 6 and y[1] == 2 and any(s[0] == 13 for s in parse(y[2])):
                        gold_f6_node = y[2]
    ours_f6_node = mount_f6_node([(0x40000001 + i, 20000) for i in range(4)])[2]
    same = gold_f6_node == ours_f6_node
    lines.append(f"[{'PASS' if same else 'FAIL'}] ①b f6 挂载节点整体（cid3 前缀）vs 金样本 2025"
                 f"（{len(ours_f6_node)}B）\n      金: {gold_f6_node.hex()}\n      仿: {ours_f6_node.hex()}")
    fails += 0 if same else 1

    # ② tab4 图域注册条目（4 图）
    gold_tab4 = None
    for e in parse(_fields(gt, 6)[0][2]):
        if not (isinstance(e, list) and e[0] == 1):
            continue
        tr = parse(e[2])
        if next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None) == TREE_TAB_GRAPH:
            gold_tab4 = e[2]
    ours_tab4 = graph_tab_entry([0x40000001 + i for i in range(4)])[2]
    same = gold_tab4 == ours_tab4
    lines.append(f"[{'PASS' if same else 'FAIL'}] ② tab4 图域条目 vs 金样本 2025"
                 f"（{len(ours_tab4)}B）\n      金: {gold_tab4.hex()}\n      仿: {ours_tab4.hex()}")
    fails += 0 if same else 1

    # ③ tab3 实体注册条目 vs 金样本 2023（最小注册面）
    m23 = parse(Container.load(
        GOLD_2023 or _resolve_sample("gold2023")).proto)
    gold_tab3 = None
    for e in parse(_fields(m23, 6)[0][2]):
        if not (isinstance(e, list) and e[0] == 1):
            continue
        tr = parse(e[2])
        if next((viv(x[2]) for x in tr if x[0] == 1 and x[1] == 0), None) == TREE_TAB_ENTITY:
            gold_tab3 = e[2]
    ours_tab3 = entity_tab_entry(LEVEL_HOST_GUID)[2]
    same = gold_tab3 == ours_tab3
    lines.append(f"[{'PASS' if same else 'FAIL'}] ③ tab3 实体条目 vs 金样本 2023"
                 f"（{len(ours_tab3)}B）\n      金: {gold_tab3.hex()}\n      仿: {ours_tab3.hex()}")
    fails += 0 if same else 1

    # ④ P3/P4/P5 扫描器自测（2026-10-13 锚接入）：病图必拦截＋平凡对照＋特化律/豁免律/动态边
    nf, nl = scanner_selftest()
    lines.extend(nl)
    fails += nf

    for ln in lines:
        print(ln)
    print(f"selftest: {'ALL PASS' if fails == 0 else f'{fails} FAIL'}")
    return fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="装配模块 v1（v4 §四/§五 重审版）")
    ap.add_argument("gis", nargs="*", help="输入 .gis 图件")
    ap.add_argument("--out", help="输出 .gil 路径")
    ap.add_argument("--guids", help="图 guid 逗号分隔（挂载/叶引用；须与 .gis 图头一致）")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--gold", default=DEFAULT_GOLD)
    ap.add_argument("--selftest", action="store_true", help="生成器 vs 金样本逐字节对照")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(1 if selftest() else 0)
    _require(a.gis and a.out and a.guids, "需要 <gis...> --out --guids（或 --selftest）")
    guids = [int(x, 0) for x in a.guids.split(",")]
    p, metas, report = assemble(a.gis, a.out, guids, base_path=a.base, gold_path=a.gold)
    for r in report:
        print("[INFO]", r)
    n_fail, out_lines = check_output(p, guids)
    for ln in out_lines:
        print(ln)
    print("assembled:", p, "| checks:", "ALL GREEN" if n_fail == 0 else f"{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)
