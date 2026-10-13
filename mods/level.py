# -*- coding: utf-8 -*-
"""level.mount — 关卡挂载模块。

把装配器 assemble v1（mods/_vendor/assemble.py：出口校验 V0-V7）包装成模块库
单元，挂到 mods/core.py 基础设施上（@module / Result / 版本制 / 异常语义）。
本模块只编排不实现：装配与校验全部来自 assemble v1（vendored 只读依赖）。

调用（docs/30 竖线第二步）：
    r2 = level.level_mount(graph_gis=r1.artifact, host_guid=0x41400001,
                           graph_guid=0x40000001, category=20000)  # 可选 level_name
    # r2.version = 关卡新版本号；r2.value = 新版本 .gil 路径
    # r2.level  = 版本域名（core 包装器语义：版本落点 levels/<域名>/v<N>.gil；
    #            「.gil 路径」放 value——包装器用 level 字段定位版本目录，不能存路径）

执行链（与 core 包装器的交接）：
    前置检查 → assemble.assemble 组装到临时槽（state/tmp，版本域外零副作用）
    → assemble.check_output 出口校验（V0-V7 结构项 + P 位如实报）
    → 全过后交 core 包装器落版：包装器负责字节复制（commit_version）/ oplog
    日志 / 版本号（current.json）。拒绝发生在落盘之前，坏调用天然不产生新版本
    =「回滚由构造保证」。

异常语义映射（core.py 三分支）：
    PreconditionError（前置不过，不计拒绝，换路）：
      - graph_gis 不存在
      - host_guid != 0x41400001（S0 唯一关卡宿主）
      - category 不在 f501 四值挂载空间 {20000,20003,20005,20007}
      - 底座/金样本不可得（游戏目录未配置——见 mods/config 的 savelevel 配置）
    ModuleRejected（后验不过，不入账 + 计连续拒绝，4 次 → Voyager 换路信号）：
      - 输入 .gis 门禁不过（roundtrip/单图/图头 id 块，assemble.load_graph_doc）
      - graph_guid 或 category 与图头 id 块（f5/f2 唯一权威源）不符
        （模块层复核；挂错宿主类型=永聋 #65）
      - 装配过程 CheckError / 出口校验 FAIL>0（FAIL 明细进异常消息）

测试分层（mods/selftest）:
  CORE  前置负例 + 合成底座/金样本/图件的离线正例（tests/fixtures 合成件）
  FULL  真实链路：graphgen 产物挂载 + 游戏目录样本逐字节对照
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import core  # noqa: F401  先导入 core：其自举把仓库 src/qxfmt 加入 sys.path

# ---- assemble v1（vendored 只读依赖）按文件路径加载。
# 不用包名 import：消除 sys.path 上同名模块歧义（v2 既有纪律），并让本模块
# 与 vendored 副本一一对应。路径适配差异（相对 v2 原件）见 _vendor 内注记。
_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
_assemble_spec = importlib.util.spec_from_file_location(
    "qxy_assemble_v1", _VENDOR_DIR / "assemble.py")
assemble = importlib.util.module_from_spec(_assemble_spec)
sys.modules["qxy_assemble_v1"] = assemble
_assemble_spec.loader.exec_module(assemble)

S0_HOST_GUID = assemble.LEVEL_HOST_GUID        # 0x41400001——S0 唯一关卡宿主
MOUNT_CATEGORIES = assemble.MOUNT_CATEGORIES   # f501 四值挂载空间
DEFAULT_CATEGORY = 20000


def _tmp_slot() -> Path:
    """装配临时产物槽：state/tmp 下单文件复用（每次挂载先清槽再写，不累积）。
    在状态根内、版本域（levels/）之外——拒绝/崩溃不污染关卡版本。"""
    return core.state_dir() / "tmp" / "level_mount.gil"


def _parse_check_lines(lines: list) -> list:
    """把 check_output 的「[状态] 文本」行解析成 Result.checks 的 (名, 状态) 对。
    [INFO] 归 TRIVIAL（纯信息）；其余状态（PASS/FAIL/TRIVIAL/PENDING-ANCHOR/
    PENDING-S1）如实透传，不美化。"""
    out = []
    for ln in lines:
        if not (ln.startswith("[") and "]" in ln):
            continue
        status, _, text = ln[1:].partition("]")
        status, text = status.strip(), text.strip()
        if not text:
            continue
        out.append((text, "TRIVIAL" if status == "INFO" else status))
    return out


@core.module("level.mount")
def level_mount(graph_gis: str, host_guid: int, graph_guid: int,
                category: int = DEFAULT_CATEGORY,
                level_name: str | None = None) -> core.Result:
    """把一张已过门禁的 .gis 图挂到关卡宿主，产出版本制 .gil。

    S0 单图签名：graph_gis/graph_guid 均为单值（多图合成形态未定，assemble 遗留
    L3）。level_name 缺省取 .gis 文件名主干（hello_loop.gis → 域 hello_loop）。

    返回 Result：
      artifact = 装配临时产物路径（state/tmp 槽；包装器把它复制成新版本字节）
      level    = 版本域名
      value    = 新版本 .gil 路径（落版前按 current+1 预测；包装器随后按同值落盘）
      checks   = 模块层前检 + 装配器 V0-V7 / P 位明细 + 包装器 commit_byte_equal
      version  = 包装器落版后自动附填的新版本号
    """
    src = Path(graph_gis)
    if not src.exists():
        raise core.PreconditionError(f"graph_gis 不存在: {graph_gis}")
    if host_guid != S0_HOST_GUID:
        raise core.PreconditionError(
            f"host_guid 0x{host_guid:x} 非 S0 唯一宿主 0x{S0_HOST_GUID:x}")
    if category not in MOUNT_CATEGORIES:
        raise core.PreconditionError(
            f"category {category} 不在 f501 四值挂载空间 {list(MOUNT_CATEGORIES)}")

    name = level_name or src.stem

    # 模块层复核：读图头。load_graph_doc 内含输入 .gis roundtrip 硬门禁；
    # guid/类别权威源 = 图头 id 块 f5/f2（assemble v1 D14 定案）。
    # CheckError（含容器格式断言）= 输入件不合规 → 拒绝（坏输入不入账，不响亮崩）。
    try:
        _, hdr_guid, hdr_cat = assemble.load_graph_doc(str(src))
    except assemble.CheckError as e:
        raise core.ModuleRejected(f"输入 .gis 门禁不过: {e}") from e
    except AssertionError as e:  # 容器格式硬断言（非本格式/畸形件）
        raise core.ModuleRejected(f"输入 .gis 门禁不过（格式断言）: {e}") from e
    if hdr_guid != graph_guid:
        raise core.ModuleRejected(
            f"graph_guid 0x{graph_guid:x} 与图头 guid 0x{hdr_guid:x} 不符（图头=唯一权威源）")
    if category != hdr_cat:
        raise core.ModuleRejected(
            f"category {category} 与图头类别 {hdr_cat} 不符（挂错宿主类型=永聋 #65）")

    checks = [
        ("host_guid==S0唯一宿主", "PASS"),
        ("category∈f501四值空间", "PASS"),
        ("gis_input_gate(roundtrip+单图+图头id块)", "PASS"),
        ("recheck graph_guid==图头f5", "PASS"),
        ("recheck category==图头f2", "PASS"),
    ]

    # 执行①：组装到临时槽（先清槽；拒绝前零版本域副作用）
    tmp = _tmp_slot()
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    try:
        assemble.assemble([str(src)], str(tmp), [graph_guid])
    except assemble.MissingSample as e:
        raise core.PreconditionError(str(e)) from e  # 样本不可得=环境前置，非质量拒绝
    except assemble.CheckError as e:
        raise core.ModuleRejected(f"装配被拒: {e}") from e

    # 执行②：出口等价校验 V0-V7（结构项 FAIL 即败）+ P 位（如实报状态）
    try:
        fails, lines = assemble.check_output(str(tmp), [graph_guid])
    except assemble.MissingSample as e:
        raise core.PreconditionError(str(e)) from e
    except assemble.CheckError as e:
        raise core.ModuleRejected(f"出口校验中断: {e}") from e
    checks += _parse_check_lines(lines)
    if fails > 0:
        bad = " | ".join(ln for ln in lines if ln.startswith("[FAIL]"))
        raise core.ModuleRejected(f"出口校验 {fails} 项 FAIL: {bad}")

    # 全过 → 交 core 包装器落版（字节复制/日志/版本号由包装器负责）
    return core.Result(
        ok=True, artifact=str(tmp), level=name,
        value=str(core.version_path(name, core.current_version(name) + 1)),
        checks=checks)
