# -*- coding: utf-8 -*-
"""terrain.patch — 地形产线模块（P1 第二件）。

把成熟工具 TerrainPatcher（mods/_vendor/terrain_patch.py，实战一次通过——
仓库 手册/17 地形系统）包装为四要素契约模块。纪律：**只 import 包装不改**——
set_layer/set_slope/set_material/set_water/set_path 与 save（自带往返校验）全部
原样来自 vendored 工具；本模块补的是契约层：

  前置（PreconditionError：不计失败不计拒绝，编排器换路）
    P1 格键范围    gx/gz ∈ [100,119]（grid 20×20，手册/17）
    P2 坡互斥律    同格不得坡(f6)与水(f4)/路径(f5)并存——既查本批 cells 内
                   同格冲突，也对底座现状复核（对已有水/路径的格设坡、对已
                   有坡的格加水/路径 → 拒）
    P3 层位值域    layer ∈ 1..3（1/2/3，省略=1）
    P4 字段白名单  只认 layer/slope/material/water/path；未知键一律拒（防
                   拼写错静默丢操作；旧别名 surface 不收——f4 实为水体）
    P5 值域        material ∈ 1..8（八色）；slope = 16×型+d 且 ≥16、d∈0..3
                   （型语义待编辑器判决故不设型上限）；water/path ∈ {0,1}
                   （0=显式归零值）
    P6 底座在位    关卡有当前版本、TerrainPatcher 能开（其 __init__ 自带底座
                   roundtrip 断言）、目标格全部已存在于底座 group0（包装对象
                   不支持造块——空格=虚空，见遗留 L1）

  执行：开当前版本 .gil → TerrainPatcher 定点手术 → 产出到 state/tmp 槽
  （版本域外，拒绝零污染）→ 交 core 包装器落版（字节复制/oplog/指针）。

  后验（ModuleRejected：不入账，版本指针不动，计连续拒绝）
    V1 roundtrip    输出能被 TerrainPatcher 重新装载（其 __init__ 断言往返）
    V2 块数对账     操作后总块数 == 操作前 + 新增数——「地块列表整体替换」
                    铁律的机器化：注入只写变化块=其余块全丢成虚空
    V3 组结构对账   f7 组数不变、各组块数逐组相等（group0 允许 +新增数）
    V4 键集守恒     group0 格键集合恰为「原集合 ∪ 新增键」
    V5 变更块抽查   每个目标格逐字段读回验证（层位按「省略=1」归一）
    V6 无辜块守恒   group0 全部未触碰格的五字段(f2..f6)快照逐格相等——手术
                    不许溅射到邻居

调用：
    terrain.terrain_patch(level_name="hello",
                          cells=[{"gx":107, "gz":106, "layer":1},
                                 {"gx":109, "gz":103, "water":1}])
    ok → version=新版本号；value=新版本 .gil 路径；artifact=state/tmp 槽产物

与直用 TerrainPatcher 的差异要点：
    - 直用=裸工具（信任调用者自管路径/往返/块数）；本模块=契约层（前置六条
      + 后验六条），坏调用从构造上产生不了新版本（core 版本制）
    - 直用吃 .gil 路径；本模块吃关卡域名，走版本制（levels/<名>/v<N>.gil +
      current.json 指针），天然可回滚
    - 直用 save 只验往返；本模块加 V2/V4/V6 三道整体替换铁律守卫——变更块
      抽查单靠自己是抓不住"只写变化块"事故的（变化块恰恰是对的）

遗留：L1 不支持造块/删块（虚空中落地块、拆坡删 f6 字段均超出现包装能力，
需扩 vendored 工具或包装层合成地块节点）；L2 坡型语义待编辑器判决，本模块
只做编码形校验（16×型+d）不做语义判断；L3 只手术 f7 第一组（TerrainPatcher
即如此——多笔刷岛的同键跨组堆叠不在本模块射程）；L4 水道可渡性未判，加水
不做可达性断言。

测试分层（mods/selftest）: CORE（合成地形底座，零游戏目录/零工具树可跑——
见 tests/fixtures 合成件）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from . import core  # noqa: F401  先导入 core：其自举把仓库 src/qxfmt 加入 sys.path

# ---- terrain_patch v1（vendored 只读依赖）按文件路径加载——消除包名歧义，
# 同 mods/level.py 加载 _vendor/assemble.py 的做法；纪律：只包装不改。 ----
_V1_PATH = Path(__file__).resolve().parent / "_vendor" / "terrain_patch.py"
_v1_spec = importlib.util.spec_from_file_location("qxy_terrain_patch_v1", _V1_PATH)
terrain_patch_v1 = importlib.util.module_from_spec(_v1_spec)
sys.modules["qxy_terrain_patch_v1"] = terrain_patch_v1
_v1_spec.loader.exec_module(terrain_patch_v1)

GRID_LO, GRID_HI = 100, 119        # P1 格键范围（20×20 设计网格）
LAYER_LO, LAYER_HI = 1, 3          # P3 层位值域（省略=1）
MATERIAL_LO, MATERIAL_HI = 1, 8    # P5 材质八色（1冰/4草/5混拼/6岩…）
_FIELDS = ("layer", "slope", "material", "water", "path")
# 地块字段号（手册/17）：f2 层位 / f3 材质 / f4 水 / f5 路径 / f6 坡
_FIELD_NO = {"layer": 2, "material": 3, "water": 4, "path": 5, "slope": 6}


# ---------------------------------------------------------------------------
# 前置 P1-P5：纯输入校验（先于一切文件访问，坏令零副作用）
# ---------------------------------------------------------------------------

def _norm_cells(cells):
    """校验并归一 cells → [(gx, gz, {字段: 值})]（保持首现顺序，一格一令）。"""
    if not isinstance(cells, (list, tuple)) or not cells:
        raise core.PreconditionError("cells 必须为非空列表")
    seen = {}
    for i, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise core.PreconditionError(f"cells[{i}] 不是 dict: {cell!r}")
        gx, gz = cell.get("gx"), cell.get("gz")
        for name, v in (("gx", gx), ("gz", gz)):
            if type(v) is not int or not (GRID_LO <= v <= GRID_HI):
                raise core.PreconditionError(
                    f"cells[{i}] {name}={v!r} 越界（格键范围 {GRID_LO}~{GRID_HI}）")
        if (gx, gz) in seen:
            raise core.PreconditionError(
                f"cells[{i}] 格 ({gx},{gz}) 重复出现（一格一令，合并后再来）")
        fields = {k: v for k, v in cell.items() if k not in ("gx", "gz")}
        if not fields:
            raise core.PreconditionError(f"cells[{i}] 格 ({gx},{gz}) 无任何字段可写")
        unknown = [k for k in fields if k not in _FIELDS]
        if unknown:
            raise core.PreconditionError(
                f"cells[{i}] 未知字段 {unknown}（只认 {list(_FIELDS)}；"
                f"旧别名 surface 不收——f4 实为水体）")
        for k, v in fields.items():
            if type(v) is not int:
                raise core.PreconditionError(f"cells[{i}] 字段 {k}={v!r} 非整数")
        if "layer" in fields and not (LAYER_LO <= fields["layer"] <= LAYER_HI):
            raise core.PreconditionError(
                f"cells[{i}] layer={fields['layer']} 越界（层位值域 {LAYER_LO}~{LAYER_HI}）")
        if "material" in fields and not (MATERIAL_LO <= fields["material"] <= MATERIAL_HI):
            raise core.PreconditionError(
                f"cells[{i}] material={fields['material']} 越界（八色 {MATERIAL_LO}~{MATERIAL_HI}）")
        if "slope" in fields and (fields["slope"] < 16 or fields["slope"] % 16 > 3):
            raise core.PreconditionError(
                f"cells[{i}] slope={fields['slope']} 非法（f6=16×型+d，型≥1、d∈0..3，"
                f"如东向楼梯坡=16）")
        for k in ("water", "path"):
            if k in fields and fields[k] not in (0, 1):
                raise core.PreconditionError(f"cells[{i}] {k}={fields[k]} 非法（只认 0/1）")
        if "slope" in fields and (fields.get("water") or fields.get("path")):
            raise core.PreconditionError(
                f"cells[{i}] 格 ({gx},{gz}) 坡与水/路径同格（互斥律）")
        seen[(gx, gz)] = fields
    return [(gx, gz, f) for (gx, gz), f in seen.items()]


# ---------------------------------------------------------------------------
# 字节面独立普查（不信任手术工具的内存账，一切以重读文件字节为准）
# ---------------------------------------------------------------------------

def _field_value(tl, field_no: int):
    """读地块单字段整数值；缺失=None；非 varint wire 型原样返回字节体。"""
    v1 = terrain_patch_v1
    nd = v1.first(tl, field_no)
    if nd is None:
        return None
    return v1.varint_value(nd) if nd[1] == 0 else nd[2]


def _scan(gil_path: str):
    """独立普查：返回 (stats, g0快照)。
    stats = {groups, per_group, total, g0_keys}（f7 组数/各组块数/总块数/group0 格键集）
    g0快照 = {格键: (f2,f3,f4,f5,f6)}（无辜块守恒 V6 的对照面）。"""
    v1 = terrain_patch_v1
    c = v1.Container.load(gil_path)
    f7 = v1.first(v1.parse(c.proto), 7)
    if f7 is None:
        raise ValueError("无 f7 地形组")
    groups = v1.parse(f7[2])
    per_group, g0_keys, snap = [], set(), {}
    for gi, g in enumerate(groups):
        n = 0
        for nd in v1.parse(g[2]):
            if nd[0] != 4:
                continue
            n += 1
            if gi == 0:
                tl = v1.parse(nd[2])
                k = v1.varint_value(v1.first(tl, 1))
                g0_keys.add(k)
                snap[k] = tuple(_field_value(tl, f) for f in (2, 3, 4, 5, 6))
        per_group.append(n)
    return ({"groups": len(groups), "per_group": per_group,
             "total": sum(per_group), "g0_keys": g0_keys}, snap)


# ---------------------------------------------------------------------------
# 后验 V1-V6（对产出文件独立重读）
# ---------------------------------------------------------------------------

def _verify_output(before_scan: dict, before_snap: dict, out_path: str,
                   specs: list, expected_new: int):
    """对产出做 V1-V6 六道后验。返回 (FAIL 数, checks 明细)。"""
    v1 = terrain_patch_v1
    checks: list = []
    fails = 0

    def rec(name: str, good: bool, detail: str = "") -> None:
        nonlocal fails
        checks.append((f"{name}({detail})" if detail else name,
                       "PASS" if good else "FAIL"))
        if not good:
            fails += 1

    # V1 roundtrip：输出能被 TerrainPatcher 重新装载（其 __init__ 断言往返）
    try:
        rp = v1.TerrainPatcher(out_path)
    except Exception as e:  # noqa: BLE001  装载失败=V1 FAIL，后续无从做起
        rec("roundtrip_output", False, repr(e))
        return fails, checks
    rec("roundtrip_output", True)

    after_scan, after_snap = _scan(out_path)
    patched = {(gx << 16) | gz for gx, gz, _ in specs}
    new_keys = patched - before_scan["g0_keys"]

    # V2 块数对账——整体替换铁律的机器化（操作后总块数 == 操作前 + 新增数）
    rec("tile_count_reconcile",
        after_scan["total"] == before_scan["total"] + expected_new,
        f"{after_scan['total']}=={before_scan['total']}+{expected_new}")

    # V3 组结构对账：组数不变；group0 块数 = 原值+新增数；其余组逐组相等
    rec("group_structure_reconcile",
        after_scan["groups"] == before_scan["groups"]
        and after_scan["per_group"][0] == before_scan["per_group"][0] + expected_new
        and after_scan["per_group"][1:] == before_scan["per_group"][1:],
        f"{after_scan['per_group']} vs {before_scan['per_group']}")

    # V4 键集守恒：group0 格键集恰为「原集合 ∪ 新增键」
    rec("tile_keys_preserved",
        after_scan["g0_keys"] == before_scan["g0_keys"] | new_keys,
        f"|g0|={len(after_scan['g0_keys'])} vs {len(before_scan['g0_keys'])}")

    # V5 变更块抽查：逐格逐字段读回；层位按「省略=1」归一（缺失字段读 None）
    bad = []
    for gx, gz, fields in specs:
        tl = rp.tiles[(gx << 16) | gz]
        for name, want in fields.items():
            got = _field_value(tl, _FIELD_NO[name])
            good = (got == want) or (want == LAYER_LO and got is None) \
                if name == "layer" else (got == want) or (want == 0 and got is None)
            if not good:
                bad.append(f"({gx},{gz}).{name} 期望{want} 实得{got}")
    rec("changed_cells_spotcheck", not bad,
        f"{len(specs)}格" + ("; " + "; ".join(bad[:4]) if bad else ""))

    # V6 无辜块守恒：未触碰格五字段快照逐格相等（手术不许溅射邻居）
    drift = [k for k, v in before_snap.items()
             if k not in patched and after_snap.get(k) != v]
    rec("untouched_cells_unchanged", not drift,
        f"{len(before_snap)}格快照" + (f"; 漂移{len(drift)}格" if drift else ""))
    return fails, checks


# ---------------------------------------------------------------------------
# 模块本体
# ---------------------------------------------------------------------------

@core.module("terrain.patch")
def terrain_patch(level_name: str, cells: list) -> core.Result:
    """对关卡地形做定点手术（层位/坡/材质/水/路径），产出版本制新 .gil。

    cells 形如 [{"gx":107, "gz":106, "layer":1}, {"gx":109, "gz":103, "water":1}]，
    每格一令；格必须已存在于底座（空格=虚空，不支持造块——遗留 L1）。
    前置 P1-P6 / 后验 V1-V6 见模块 docstring。失败语义：
    前置不过=PreconditionError（换路）；后验不过=ModuleRejected（不入账）。
    """
    specs = _norm_cells(cells)  # P1-P5（纯输入，先于一切 IO）

    v = core.current_version(level_name)
    if v <= 0:
        raise core.PreconditionError(
            f"关卡 {level_name} 无当前版本（先 level.mount/level.checkpoint 入库）")
    src = core.version_path(level_name, v)
    if not src.exists():
        raise core.PreconditionError(f"当前版本文件缺失: {src}")

    v1 = terrain_patch_v1
    try:
        p = v1.TerrainPatcher(str(src))  # P6：开底座（__init__ 自带 roundtrip 断言）
    except (RuntimeError, ValueError) as e:
        raise core.PreconditionError(f"底座打不开（{src}）: {e}") from e

    try:
        before_scan, before_snap = _scan(str(src))
    except (ValueError, IndexError) as e:
        raise core.PreconditionError(f"底座普查失败（{src}）: {e}") from e
    if before_scan["g0_keys"] != set(p.tiles.keys()):
        raise core.ModuleRejected("底座普查与手术工具账面不一致（group0 格键集合不等）")

    # P6 续：目标格必须已存在（包装对象不支持造块，空格=虚空——遗留 L1）
    missing = [f"({gx},{gz})" for gx, gz, _ in specs
               if (gx << 16) | gz not in p.tiles]
    if missing:
        raise core.PreconditionError(
            f"目标格不在底座 group0（空格=虚空，不支持造块）: {', '.join(missing)}")

    # P2 续：互斥律对底座现状复核（本批内冲突已由 _norm_cells 拦下）
    for gx, gz, fields in specs:
        tl = p.tiles[(gx << 16) | gz]
        cur = {f: _field_value(tl, no) or 0 for f, no in _FIELD_NO.items()}
        if "slope" in fields and (cur["water"] or cur["path"]):
            raise core.PreconditionError(
                f"格 ({gx},{gz}) 底座已有水(f4={cur['water']})/路径(f5={cur['path']})，"
                f"不得设坡（互斥律）")
        for k in ("water", "path"):
            if k in fields and fields[k] and cur["slope"]:
                raise core.PreconditionError(
                    f"格 ({gx},{gz}) 底座已有坡(f6={cur['slope']})，不得设{k}（互斥律）")

    # P6 已保证目标格全存在 → 新增数恒 0；保留一般式让 V2 公式完整
    expected_new = sum(1 for gx, gz, _ in specs
                       if (gx << 16) | gz not in before_scan["g0_keys"])

    checks = [
        ("cells_input_gate(P1-P5)", "PASS"),
        ("base_load+roundtrip(P6)", "PASS"),
        ("base_scan_consistent", "PASS"),
        ("tiles_exist(P6)", "PASS"),
        ("mutex_vs_base(P2)", "PASS"),
    ]

    # 执行：定点手术 → state/tmp 槽（版本域外，拒绝零污染）
    tmp = core.state_dir() / "tmp" / "terrain_patch.gil"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    for gx, gz, fields in specs:
        if "layer" in fields:
            p.set_layer(gx, gz, fields["layer"])
        if "slope" in fields:
            p.set_slope(gx, gz, fields["slope"])
        if "material" in fields:
            p.set_material(gx, gz, fields["material"])
        if "water" in fields:
            p.set_water(gx, gz, fields["water"])
        if "path" in fields:
            p.set_path(gx, gz, fields["path"])
    try:
        p.save(str(tmp))  # vendored save 自带输出往返断言（失败抛 RuntimeError）
    except RuntimeError as e:
        raise core.ModuleRejected(f"输出往返验证失败: {e}") from e

    # 后验 V1-V6（独立重读产出字节）
    fails, post = _verify_output(before_scan, before_snap, str(tmp), specs, expected_new)
    checks += post
    if fails:
        bad = " | ".join(n for n, s in post if s == "FAIL")
        raise core.ModuleRejected(f"后验 {fails} 项 FAIL: {bad}")

    # 全过 → 交 core 包装器落版（字节复制/oplog/版本号由包装器负责）
    return core.Result(
        ok=True, artifact=str(tmp), level=level_name,
        value=str(core.version_path(level_name, core.current_version(level_name) + 1)),
        checks=checks)
