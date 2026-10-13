# -*- coding: utf-8 -*-
"""terrain.patch 模块自测（CORE——合成地形底座，零游戏目录/零工具树）。

运行：python -m mods.test_terrain（仓库根；mods.selftest 编排其一）
① 正例：给临时域 hello（合成地形底座 10 块）patch 3 格（层位/水/材质）→
   roundtrip 过 + 块数对账过 + 变更块逐字段读回验证 + 同 cells 二次 patch 字节
   全同（幂等，值覆盖不增块）+ 坡正例；
② 负例：格键越界 / 非法层位 / 坡水同格 / 未知字段 / 底座无 f7 / 目标格不在
   底座 / 对有水格设坡 / 对有坡格加水 → 各 PRECONDITION（不计拒绝）；
③ 铁律事故重现（docs/17「地块列表整体替换」教训）：猴子补丁把 save 换成
   「只写变化块」版 → 后验块数对账拦截 → ModuleRejected、版本不变；
④ 回归：mods.test_core 子进程仍全绿。
状态根经 QXYV2_ROOT 重定向到临时目录（版本/日志零污染）；夹具全部由
tests/fixtures/synth 合成（格式常量，零游戏资产）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 任意 cwd 可运行

# 合成底座 10 块（覆盖测试面全部格键；值=测试断言的对照面）
TILES = [
    {"gx": 100, "gz": 100, "layer": 3, "material": 3},   # 无辜远格对照
    {"gx": 101, "gz": 100, "layer": 1},
    {"gx": 101, "gz": 101, "layer": 2, "material": 1},
    {"gx": 107, "gz": 106, "layer": 2},                  # 正例①：2→1
    {"gx": 109, "gz": 103, "layer": 1},                  # 正例②：加水
    {"gx": 110, "gz": 103, "layer": 1},                  # 正例③：材质
    {"gx": 100, "gz": 102, "layer": 2},                  # 坡正例：平格设坡
    {"gx": 102, "gz": 103, "layer": 1, "water": 1},      # 底座已有水（设坡负例）
    {"gx": 100, "gz": 111, "layer": 2, "slope": 17},     # 底座已有坡（加水/路负例）
    {"gx": 118, "gz": 119, "layer": 1},
]

CELLS_A = [{"gx": 107, "gz": 106, "layer": 1},     # 原 L2 岸块 → 铲平 L1
           {"gx": 109, "gz": 103, "water": 1},     # 平格挖水
           {"gx": 110, "gz": 103, "material": 4}]  # 材质 → 草
CELL_B_SLOPE = [{"gx": 100, "gz": 102, "slope": 16}]  # 东向楼梯坡（原 L2 平格）


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()  # 本模块纯 CORE

    tmp = tempfile.mkdtemp(prefix="qxy_mods_terrain_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：版本/日志零污染
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import core, state
    from mods import terrain
    v1 = terrain.terrain_patch_v1
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from fixtures import synth

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS [CORE] {len(passes):02d}  {name}")

    def tile_fields(gil_path: str, gx: int, gz: int):
        """独立字节面读回（测试自带解析，不走模块内部函数）：格的五字段 dict。"""
        c = v1.Container.load(gil_path)
        f7 = v1.first(v1.parse(c.proto), 7)
        want = (gx << 16) | gz
        for nd in v1.parse(v1.parse(f7[2])[0][2]):
            if nd[0] != 4:
                continue
            tl = v1.parse(nd[2])
            if v1.varint_value(v1.first(tl, 1)) == want:
                out = {}
                for f in (2, 3, 4, 5, 6):
                    n = v1.first(tl, f)
                    out[f] = v1.varint_value(n) if n else None
                return out
        return None

    def pre(fn, *args, **kwargs) -> bool:
        """调用并断言 PRECONDITION 语义，返回是否确为前置拒绝。"""
        r = fn(*args, **kwargs)
        return (not r.ok) and (r.error or "").startswith("PRECONDITION")

    core.reset_rejections()

    # ---- 0. 播种合成底座 + 模块注册 ----
    fx = Path(tmp) / "fixtures"
    base_gil = synth.write_terrain_gil(fx / "terrain_base.gil", TILES)
    bare_gil = synth.write_base_gil(fx / "bare.gil")          # 无 f7 负例底座
    partial_gil = synth.write_terrain_gil(fx / "partial.gil", TILES[:5])  # 缺格底座

    ok("模块已注册 terrain.patch", "terrain.patch" in core.list_modules())

    # 播种三个临时域（字节来自合成夹具）：
    #   hello         ← 合成 10 块地形（正例底座）
    #   hello_bare    ← 无 f7 骨架（地形前置负例）
    #   hello_partial ← 5 块缺格件（缺格负例）
    for name, src in (("hello", base_gil), ("hello_bare", bare_gil),
                      ("hello_partial", partial_gil)):
        rs = state.level_checkpoint(level_name=name, source_gil=str(src))
        assert rs.ok, f"播种 {name} 失败: {rs.error}"
    base_scan, _ = terrain._scan(str(base_gil))
    ok("播种完成：hello v1 = 10 块合成地形",
       core.current_version("hello") == 1 and base_scan["total"] == 10)

    # ---- 1. 负例·纯输入前置（P1-P5，不碰文件、不计拒绝） ----
    bad_inputs = [
        ("gx 下越界 99", [{"gx": 99, "gz": 106, "layer": 1}]),
        ("gx 上越界 120", [{"gx": 120, "gz": 106, "layer": 1}]),
        ("gz 下越界 99", [{"gx": 107, "gz": 99, "layer": 1}]),
        ("gz 上越界 120", [{"gx": 107, "gz": 120, "layer": 1}]),
        ("层位 0", [{"gx": 107, "gz": 106, "layer": 0}]),
        ("层位 4", [{"gx": 107, "gz": 106, "layer": 4}]),
        ("材质 0", [{"gx": 107, "gz": 106, "material": 0}]),
        ("材质 9", [{"gx": 107, "gz": 106, "material": 9}]),
        ("坡 型0(15)", [{"gx": 107, "gz": 106, "slope": 15}]),
        ("坡 d=5(21)", [{"gx": 107, "gz": 106, "slope": 21}]),
        ("水值 2", [{"gx": 107, "gz": 106, "water": 2}]),
        ("坡水同格", [{"gx": 107, "gz": 106, "slope": 16, "water": 1}]),
        ("坡路同格", [{"gx": 107, "gz": 106, "slope": 16, "path": 1}]),
        ("未知字段", [{"gx": 107, "gz": 106, "color": 3}]),
        ("旧别名 surface 拒收", [{"gx": 107, "gz": 106, "surface": 1}]),
        ("空 cells", []),
        ("cells 非 list", {"gx": 107, "gz": 106}),
        ("cell 非 dict", [(107, 106)]),
        ("无字段格", [{"gx": 107, "gz": 106}]),
        ("同格重复令", [{"gx": 107, "gz": 106, "layer": 1},
                       {"gx": 107, "gz": 106, "water": 1}]),
        ("gx 浮点", [{"gx": 107.0, "gz": 106, "layer": 1}]),
        ("gx 布尔", [{"gx": True, "gz": 106, "layer": 1}]),
    ]
    all_pre = all(pre(terrain.terrain_patch, "hello", c) for _, c in bad_inputs)
    ok("输入负例 22 条全 PRECONDITION（越界/值域/坡水同格/白名单/形制）", all_pre)
    ok("输入负例不产生任何版本", core.current_version("hello") == 1)
    n_pre = len(core.query_oplog(module="terrain.patch", ok=False))
    ok("前置拒绝全部落日志且 kind=precondition、不计拒绝",
       n_pre == len(bad_inputs)
       and all(e["kind"] == "precondition" for e in core.read_oplog()
               if e["module"] == "terrain.patch"))

    # ---- 2. 负例·底座前置（P2/P6 对底座现状） ----
    ok("底座无 f7（骨架形态）→ PRECONDITION",
       pre(terrain.terrain_patch, "hello_bare", CELLS_A))
    ok("目标格不在底座（缺格件 (101,106)）→ PRECONDITION",
       pre(terrain.terrain_patch, "hello_partial",
           [{"gx": 101, "gz": 106, "layer": 1}]))
    ok("对有水格设坡（底座 (102,103) 已有 f4）→ PRECONDITION",
       pre(terrain.terrain_patch, "hello", [{"gx": 102, "gz": 103, "slope": 16}]))
    ok("对有坡格加水（底座 (100,111) 已有 f6=17）→ PRECONDITION",
       pre(terrain.terrain_patch, "hello", [{"gx": 100, "gz": 111, "water": 1}]))
    ok("对有坡格加路径 → PRECONDITION",
       pre(terrain.terrain_patch, "hello", [{"gx": 100, "gz": 111, "path": 1}]))
    ok("关卡不存在（无当前版本）→ PRECONDITION",
       pre(terrain.terrain_patch, "no_such_lv", CELLS_A))
    ok("底座负例仍不产生新版本", core.current_version("hello") == 1)

    # ---- 3. 正例：3 格手术 → v2，roundtrip + 块数对账 + 变更块读回 ----
    r = terrain.terrain_patch(level_name="hello", cells=CELLS_A)
    ok("正例 PASS 且附 module 名", r.ok and r.module == "terrain.patch")
    ok("版本=2 且 value=新版本 .gil 路径", r.version == 2
       and r.value == str(core.version_path("hello", 2))
       and os.path.exists(r.value))
    ok("artifact=state/tmp 槽产物且字节与版本一致",
       r.artifact and str(Path(r.artifact)).replace("\\", "/").startswith(
           str(core.state_dir() / "tmp").replace("\\", "/"))
       and Path(r.artifact).read_bytes() == Path(r.value).read_bytes())
    names = " ".join(n for n, _ in r.checks)
    ok("后验六项全在 checks（roundtrip/块数对账/组结构/键集/抽查/无辜块）",
       all(k in names for k in ("roundtrip_output", "tile_count_reconcile",
                                "group_structure_reconcile", "tile_keys_preserved",
                                "changed_cells_spotcheck", "untouched_cells_unchanged")))
    ok("checks 无 FAIL 且含包装器 commit_byte_equal",
       all(s != "FAIL" for _, s in r.checks)
       and ("commit_byte_equal", "PASS") in [tuple(c) for c in r.checks])
    v2 = tile_fields(str(core.version_path("hello", 2)), 107, 106)
    ok("变更块① (107,106) 层位 2→1（独立字节读回）",
       v2 == {2: 1, 3: None, 4: None, 5: None, 6: None})
    w = tile_fields(str(core.version_path("hello", 2)), 109, 103)
    ok("变更块② (109,103) 加水 f4=1（独立字节读回）",
       w == {2: 1, 3: None, 4: 1, 5: None, 6: None})
    m = tile_fields(str(core.version_path("hello", 2)), 110, 103)
    ok("变更块③ (110,103) 材质 f3=4 草（独立字节读回）",
       m == {2: 1, 3: 4, 4: None, 5: None, 6: None})
    g = tile_fields(str(core.version_path("hello", 2)), 100, 100)
    ok("无辜远格 (100,100) L3/f3=3 原样", g == {2: 3, 3: 3, 4: None, 5: None, 6: None})
    ok("块数对账事实：v2 仍 10 块",
       terrain._scan(str(core.version_path("hello", 2)))[0]["total"] == 10)
    e_ok = [e for e in core.query_oplog(module="terrain.patch") if e["ok"]]
    ok("oplog 入账（kind=ok/version=2/checks 明细随条）",
       len(e_ok) == 1 and e_ok[0]["version"] == 2
       and any("tile_count_reconcile" in c[0] for c in e_ok[0]["checks"]))

    # ---- 4. 幂等冒烟：同 cells 二次 patch → 值覆盖不增块，字节全同 ----
    r2 = terrain.terrain_patch(level_name="hello", cells=CELLS_A)
    ok("幂等二次 patch PASS → v3", r2.ok and r2.version == 3)
    ok("幂等产物字节与 v2 全同（值覆盖不增块，不产生新差异）",
       core.read_current("hello") == Path(core.version_path("hello", 2)).read_bytes())
    ok("幂等后块数仍 10", terrain._scan(str(core.version_path("hello", 3)))[0]["total"] == 10)

    # ---- 5. 坡正例：单独一令 set_slope → v4，f6 读回=16 ----
    r3 = terrain.terrain_patch(level_name="hello", cells=CELL_B_SLOPE)
    ok("坡正例 PASS → v4", r3.ok and r3.version == 4)
    s = tile_fields(str(core.version_path("hello", 4)), 100, 102)
    ok("坡块 (100,102) f6=16（东向楼梯坡，独立字节读回）",
       s == {2: 2, 3: None, 4: None, 5: None, 6: 16})

    # ---- 6. 铁律事故重现：整体替换 save → 块数对账拦截 → ModuleRejected ----
    real_tp = v1.TerrainPatcher
    _patched_keys = {(c["gx"] << 16) | c["gz"] for c in CELLS_A}

    class _Sabotage(real_tp):  # noqa: F811  事故重现：只写变化块，其余块全丢成虚空
        def save(self, out_path):
            kids = [x for x in v1.parse(self.group[2]) if x[0] != 4]  # 组头保留
            for nd, k in self.order:
                nd[2] = v1.emit(self.tiles[k])
                if k in _patched_keys:
                    kids.append(nd)                    # ← 整体替换事故点：只留变化块
            self.group[2] = v1.emit(kids)
            self.f7[2] = v1.emit(self.f7_children)
            v1.Container(self.c.file_type, v1.emit(self.proto)).save(out_path)

    v1.TerrainPatcher = _Sabotage
    try:
        r_bad = terrain.terrain_patch(level_name="hello", cells=CELLS_A)
    finally:
        v1.TerrainPatcher = real_tp
    ok("铁律事故被拦：REJECTED 且点名 tile_count_reconcile",
       (not r_bad.ok) and (r_bad.error or "").startswith("REJECTED")
       and "tile_count_reconcile" in (r_bad.error or ""))
    ok("拒绝不入账：版本仍 v4、无 v5 文件", core.current_version("hello") == 4
       and not core.version_path("hello", 5).exists())
    last = core.read_oplog()[-1]
    ok("拒绝落日志（kind=rejected）", last["kind"] == "rejected"
       and last["module"] == "terrain.patch")
    core.reset_rejections()  # 清 Voyager 计数，给后续测试干净起算

    # ---- 7. 回归：mods.test_core 子进程仍全绿 ----
    repo_root = Path(__file__).resolve().parent.parent
    reg = subprocess.run([sys.executable, "-X", "utf8", "-m", "mods.test_core"],
                         cwd=str(repo_root), capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    ok("回归 mods.test_core 全绿（rc=0）",
       reg.returncode == 0 and "条 PASS" in (reg.stdout or ""))

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
