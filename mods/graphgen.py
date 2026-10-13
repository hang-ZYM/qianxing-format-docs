# -*- coding: utf-8 -*-
"""graphgen.build — 逻辑 IR → .gis。

接口（docs/30 用法原样）::

    from mods import graphgen
    from mods.graphgen import GraphLogic, Node, Exec

    r1 = graphgen.build(logic=GraphLogic(
            nodes=[Node(1, kernel=71), Node(2, kernel=1, text="[hello_loop] 圈活了")],
            edges=[Exec(1, 2)]), name="hello", guid=0x40000001)
    # r1.ok / r1.artifact=.gis 路径 / r1.checks 含官方门禁四连 / r1.version=关卡版号

契约:
  前置（违规抛 PreconditionError——不计失败、不计拒绝，编排器换路）:
    - 工具树在位（本模块执行与后验依赖本机研究工具：图装配器 + 门禁四连；
      开源仓库不附带——未配置 QXY_TOOL_ROOT 时如实前置拒绝并给指引）
    - kernel ∈ 470 宇宙（源: 工具树 kernel_universe.json，form_gate 同源；来源标注
      进 checks 的 kernel_universe 条目，找不到文件时退化已知集并如实标注）
    - kernel ∈ 标本库（宇宙≠可装配；无标本先走采集/注册工具）
    - 图非空；Node.id 不重复；Exec 两端引用的 id 必须存在
    - text ≤ 1000 字符（在册限额律）；name 非空、≤64、无路径分隔符
    - guid ∈ 0x4000 段 = 0x40000000..0x4000FFFF（地图级图波段；
      0x408xxxxx=实体图不归本模块）
  执行: 图装配器（工具树正典装配器，只 import 不改）克隆-改写-连线-出件；
        调用序与历史 build 脚本逐字节同构（add 节点 → exec 边 → set_str 文本），
        同参数产出逐字节确定（内部实证 2026-10-13）。
  后验（官方门禁四连，全 PASS 才 ok；任一不过 → ModuleRejected 不入账+计连续拒绝）:
    python -m qxfmt roundtrip / python -m qxfmt verify /
    python -m qxy.form_gate    / python -m qxy.oracle_gate --mode graph
  入账: Result(level=name, artifact=.gis) → core 包装器落 levels/<name>/v<N>.gil +
        current.json，并自动追加 commit_byte_equal 字节守恒检查。

  IR 只有 Exec 执行边；数据边/引脚直值/poly 等装配能力未入 IR（按"创作中反复
  出现的子任务"逐步收编）。kernel 有 (3,0) 引脚才能 set_str——引脚级能力未前置
  校验，错误装配时以装配器异常响亮失败。门禁失败路径的负例自测缺真实 SICK 件，
  ModuleRejected 分支由 core 基础设施自测覆盖。图 guid 只校验段位；"本档内空号"
  分配纪律归号域分配器/编排器（0x4000 池禁全局查重）。

测试分层（mods/selftest）:
  CORE  IR 前置校验负例（无工具树/无游戏目录可跑——宇宙退化已知集）
  FULL  正例构建 + 门禁四连（需工具树 QXY_TOOL_ROOT）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import config, core

# ---------------------------------------------------------------------------
# 工具树只读依赖的位置（图装配器 / 宇宙 / 标本库；经 config 解析，缺省如实降级）
# ---------------------------------------------------------------------------

_TOOL_SUBDIR = "M4_组件"                      # 图装配器 graph_asm.GraphAssembler 所在
_UNIVERSE_SUB = ("qxy", "kernel_universe.json")  # 470 kernel 宇宙（form_gate 同源）
_BANK_SUB = ("标本库", "bank.json")           # 装配可用标本


def _asm_dir() -> Path | None:
    root = config.tool_root()
    return root / _TOOL_SUBDIR if root else None


def _universe_json() -> Path | None:
    root = config.tool_root()
    return root.joinpath(*_UNIVERSE_SUB) if root else None


def _bank_json() -> Path | None:
    d = _asm_dir()
    return d.joinpath(*_BANK_SUB) if d else None


# ---------------------------------------------------------------------------
# 逻辑 IR（正式定义）
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """图节点。id=逻辑编号（IR 内唯一即可，装配器按 add 序重排为 1..N）；
    text=打印/字符串字面量（落 (3,0) 引脚）；note=纯注释，不落字节。"""
    id: int
    kernel: int
    text: str | None = None
    note: str | None = None


@dataclass
class Exec:
    """执行边 src → dst（两端引用 Node.id）。"""
    src: int
    dst: int


@dataclass
class GraphLogic:
    """图的逻辑 IR。edges 缺省空（纯节点图合法）。"""
    nodes: list
    edges: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# IR 校验依据：kernel 宇宙 + 标本库（import 时装载，来源如实标注）
# ---------------------------------------------------------------------------

TEXT_MAX = 1000          # 字符串在册限额（限额表同源纪律）
GUID_LO, GUID_HI = 0x40000000, 0x4000FFFF   # 0x4000 段 = 地图级图波段

# 已知集兜底：仅当工具树宇宙文件与 qxy.form_gate 都不可用时启用（不完整，
# 只许自测，禁止生产——来源标注会如实写进 checks，一眼可辨）。
_KNOWN_KERNELS = {1, 2, 3, 5, 6, 7, 8, 71, 200, 252, 315}


def _load_universe() -> tuple[set, str]:
    """kernel 宇宙装载。优先级: kernel_universe.json(470) > qxy.form_gate > 已知集。"""
    uj = _universe_json()
    if uj is not None:
        try:
            d = json.loads(uj.read_text(encoding="utf-8"))
            ks = {int(k) for k in (d.get("kernels") or [])}
            if ks:
                return ks, f"工具树 kernel_universe.json（{len(ks)} 个, form_gate 同源）"
        except Exception:
            pass
    try:
        from qxy.form_gate import _load_universe as _lu  # 后备：form_gate 装载器
        ks = {int(k) for k in _lu()}
        if ks:
            return ks, f"qxy.form_gate._load_universe()（{len(ks)} 个）"
    except Exception:
        pass
    return set(_KNOWN_KERNELS), "已知集兜底（不完整，仅自测可用，禁止生产）"


def _load_bank() -> tuple[set | None, str]:
    """装配可用标本集。读不出时返回 None=跳过标本前置（装配时响亮失败，不吞环境事故）。"""
    bj = _bank_json()
    if bj is not None:
        try:
            d = json.loads(bj.read_text(encoding="utf-8"))
            ks = {int(k) for k in d}
            return ks, f"标本库 bank.json（{len(ks)} 个）"
        except Exception:
            pass
    return None, "bank.json 不可读（跳过标本前置，装配时响亮失败）"


UNIVERSE, UNIVERSE_SOURCE = _load_universe()
BANK_KERNELS, BANK_SOURCE = _load_bank()


# ---------------------------------------------------------------------------
# 前置校验（PreconditionError）——全部不过装配的输入在这里拦下
# ---------------------------------------------------------------------------

def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _validate(logic: GraphLogic, name: str, guid: int) -> None:
    if not isinstance(name, str) or not name.strip():
        raise core.PreconditionError(f"name 必须是非空字符串，得到 {name!r}")
    if len(name) > 64 or any(ch in name for ch in '/\\:*?"<>|') or ".." in name:
        raise core.PreconditionError(f"name {name!r} 含路径分隔符/Windows 保留字符或超 64 字符")
    if not _is_int(guid):
        raise core.PreconditionError(f"guid 必须是 int，得到 {type(guid).__name__} "
                                     f"（字符串 guid 曾致静默错件，此处强制）")
    if not (GUID_LO <= guid <= GUID_HI):
        raise core.PreconditionError(
            f"guid {hex(guid)} 不在 0x4000 段（{hex(GUID_LO)}..{hex(GUID_HI)}，"
            f"地图级图波段；0x408xxxxx=实体图波段不归本模块）")
    if not logic.nodes:
        raise core.PreconditionError("GraphLogic 无节点（空图不构成逻辑）")

    ids: set = set()
    for n in logic.nodes:
        if not _is_int(n.id):
            raise core.PreconditionError(f"Node.id 必须是 int，得到 {n.id!r}")
        if n.id in ids:
            raise core.PreconditionError(f"Node.id 重复: {n.id}")
        ids.add(n.id)
        if not _is_int(n.kernel):
            raise core.PreconditionError(f"node {n.id} kernel 必须是 int，得到 {n.kernel!r}")
        if n.kernel not in UNIVERSE:
            raise core.PreconditionError(
                f"node {n.id} kernel {n.kernel} 不在 kernel 宇宙"
                f"（来源: {UNIVERSE_SOURCE}）——不存在的节点装出来也会被编辑器删除")
        if BANK_KERNELS is not None and n.kernel not in BANK_KERNELS:
            raise core.PreconditionError(
                f"node {n.id} kernel {n.kernel} 在宇宙但标本库无标本"
                f"（{BANK_SOURCE}）——先采集再注册标本")
        if n.text is not None:
            if not isinstance(n.text, str):
                raise core.PreconditionError(
                    f"node {n.id} text 必须是 str 或 None，得到 {type(n.text).__name__}")
            if len(n.text) > TEXT_MAX:
                raise core.PreconditionError(
                    f"node {n.id} text 长度 {len(n.text)} 超限额 {TEXT_MAX}")

    for e in logic.edges or []:
        if e.src not in ids:
            raise core.PreconditionError(f"exec 边悬空: src {e.src} 不在节点集 {sorted(ids)}")
        if e.dst not in ids:
            raise core.PreconditionError(f"exec 边悬空: dst {e.dst} 不在节点集 {sorted(ids)}")


# ---------------------------------------------------------------------------
# 执行：图装配器（调用序与历史 build 脚本逐字节同构）
# ---------------------------------------------------------------------------

def _assemble(logic: GraphLogic, name: str, guid: int):
    d = _asm_dir()
    if d is not None and str(d) not in sys.path:
        sys.path.append(str(d))  # 装配器按目录平铺 import（graph_asm.py 所在）
    from graph_asm import GraphAssembler  # 工具树正典装配器，延迟导入
    a = GraphAssembler(guid, name)
    idx = {}
    for n in logic.nodes:                      # ① 节点
        idx[n.id] = a.add(n.kernel)
    for e in logic.edges or []:                # ② 执行边
        a.exec_edge(idx[e.src], idx[e.dst])
    for n in logic.nodes:                      # ③ 文本（空串跳过，同历史脚本）
        if n.text:
            a.set_str(idx[n.id], 3, 0, n.text)
    return a


# ---------------------------------------------------------------------------
# 后验：官方门禁四连（subprocess 走各工具的官方 CLI 入口）
# ---------------------------------------------------------------------------

_GATES: list[tuple[str, list]] = [
    ("roundtrip",   ["-m", "qxfmt", "roundtrip"]),
    ("verify",      ["-m", "qxfmt", "verify"]),
    ("form_gate",   ["-m", "qxy.form_gate"]),
    ("oracle_gate", ["-m", "qxy.oracle_gate", "--mode", "graph"]),
]


def _gate_env() -> dict:
    """子进程环境：PYTHONPATH 补 工具树 / 仓库 src（qxfmt）/ 用户既有路径。"""
    env = dict(os.environ)
    parts = []
    root = config.tool_root()
    if root is not None:
        parts.append(str(root))
    parts.append(str(config.REPO_ROOT / "src"))
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONIOENCODING"] = "utf-8"  # 中文 Windows 控制台 GBK 兜底
    return env


def _four_gates(path: str, cwd: Path) -> list:
    """依次跑四连，全 PASS 才返回 checks 片段；任一不过 → ModuleRejected（不入账）。"""
    checks = []
    for gname, args in _GATES:
        cmd = [sys.executable, *args, path]
        try:
            p = subprocess.run(cmd, capture_output=True, env=_gate_env(),
                               cwd=str(cwd), timeout=120)
        except subprocess.TimeoutExpired:
            raise core.ModuleRejected(f"后验门禁 {gname} 超时(120s): {' '.join(args)}")
        out = (((p.stdout or b"") + b"\n" + (p.stderr or b""))
               .decode("utf-8", errors="replace").strip())
        if p.returncode == 0:
            checks.append((gname, "PASS"))
        else:
            raise core.ModuleRejected(
                f"后验门禁 {gname} 未过 (exit={p.returncode}): {out[-300:]}")
    return checks


# ---------------------------------------------------------------------------
# 模块注册
# ---------------------------------------------------------------------------

@core.module("graphgen.build")
def build(logic: GraphLogic, name: str, guid: int) -> core.Result:
    """逻辑 IR → .gis，后验=官方门禁四连（模块卡见本文件 docstring）。"""
    _validate(logic, name, guid)                       # 前置①：纯输入校验（零依赖）
    # 前置②：执行与后验依赖工具树（装配器 + form/oracle 门禁）——缺省如实换路
    asm_dir = _asm_dir()
    if asm_dir is None or not asm_dir.is_dir():
        config.require_tool_root("graphgen.build 需要图装配器与门禁四连")
    asm = _assemble(logic, name, guid)                 # 执行：确定性装配
    runs = config.runs_dir()
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{name}.gis"
    asm.save(str(path))                                # 装配器自带出件回读三验
    checks = [
        ("ir_validate", "PASS"),
        ("kernel_universe", f"TRIVIAL: {UNIVERSE_SOURCE}"),
        ("specimen_bank", f"TRIVIAL: {BANK_SOURCE}"),
    ]
    checks += _four_gates(str(path), asm_dir.parent)   # 后验：四连全绿，否则 ModuleRejected
    return core.Result(ok=True, artifact=str(path), level=name, checks=checks)
