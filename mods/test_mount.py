# -*- coding: utf-8 -*-
"""level.mount 模块自测（CORE 合成夹具 + FULL 游戏目录样本）。

运行：python -m mods.test_mount（仓库根；mods.selftest 编排其一）
CORE（无游戏目录/无工具树）：
  ① 13B 挂载内芯格式常量对照（生成器 vs 在册正典 hex，逐字节）；
  ② 负例：category 与图头不符 / graph_guid 不符 → ModuleRejected 且版本不变；
    host 传错段/错 id、缺文件 → PreconditionError；垃圾图件 → REJECTED（输入门）；
  ③ 合成正例：合成底座 + 合成宿主样本 + 最小图件（tests/fixtures/synth）→
    挂载 PASS、V0-V7 出口校验全过、产物 13B 内芯 == 正典 hex、幂等再挂字节全同；
  ④ level_name 缺省取 .gis 主干。
FULL（游戏目录关卡样本在位时）：
  ⑤ 真实链路：同一最小图件挂到真实骨架底座+真实挂载金样本，产物内芯与金样本
    同 guid 单元逐字节对照（生成=金样本的终验）。
状态根经 QXYV2_ROOT 重定向到临时目录（版本/日志零污染）；游戏样本只读。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 任意 cwd 可运行

GOLD_INNER_HEX = "0801108180808004a81fa09c01"  # 挂载内芯 13B 格式常量（正典）


def _host_mount_inners(gil_path: str, host_guid: int):
    """读 .gil → {图guid: 挂载内芯 bytes}（宿主 f6 cid3 槽 f13 单元的最内层 13B）。"""
    from mods.level import assemble  # 复用其解析器，不另引 qxfmt
    t = assemble.parse(assemble.Container.load(gil_path).proto)
    out = {}
    for x in t:
        if not (isinstance(x, list) and x[0] == 5):
            continue
        for e in assemble.parse(x[2]):
            if not (isinstance(e, list) and e[0] == 1):
                continue
            tr = assemble.parse(e[2])
            g = next((assemble.viv(y[2]) for y in tr if y[0] == 1 and y[1] == 0), None)
            if g != host_guid:
                continue
            for y in tr:
                if not (y[0] == 6 and y[1] == 2):
                    continue
                for s in assemble.parse(y[2]):
                    if s[0] != 13:
                        continue
                    for u in assemble.parse(s[2]):
                        inner = assemble.parse(u[2])[0][2]  # f1{内芯} 的内芯原始字节
                        ug = next(assemble.viv(z[2]) for z in assemble.parse(inner)
                                  if z[0] == 2)
                        out[ug] = inner
    return out


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    tmp = tempfile.mkdtemp(prefix="qxy_mods_mount_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：版本/日志零污染
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from fixtures import synth

    from mods import core, state
    from mods import level
    from mods.level import assemble

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        layer = "FULL" if getattr(ok, "full", False) else "CORE"
        print(f"PASS [{layer}] {len(passes):02d}  {name}")

    GUID = 0x40000001
    HOST = 0x41400001
    core.reset_rejections()

    # ---- 合成夹具（CORE 面的全部依赖）----
    fx = Path(tmp) / "fixtures"
    synth_base = synth.write_base_gil(fx / "base.gil")
    synth_gold = synth.write_gold_like_gil(fx / "gold_like.gil")
    gis = synth.write_min_gis(fx / "hello_fixture.gis", GUID, 20000,
                              b"hello", "[hello_fixture] 圈活了".encode("utf-8"))

    # ---- 0. 格式常量与注册 ----
    ok("模块已注册 level.mount", "level.mount" in core.list_modules())
    ok("13B 挂载内芯 == 在册正典 hex（生成器=格式常量）",
       synth.mount_unit_inner(GUID, 20000).hex() == GOLD_INNER_HEX
       == synth.GOLD_INNER_HEX)

    # ---- ① 合成正例（CORE）：注入合成底座/金样本 → 挂载全链 ----
    assemble.DEFAULT_BASE = str(synth_base)
    assemble.DEFAULT_GOLD = str(synth_gold)
    r2 = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=GUID,
                           category=20000, level_name="hello")
    ok("合成正例 PASS 且附 module 名", r2.ok and r2.module == "level.mount")
    ok("版本=1 且域名=hello", r2.version == 1 and r2.level == "hello")
    ok("value=新版本 .gil 路径且在盘", r2.value == str(core.version_path("hello", 1))
       and os.path.exists(r2.value))
    ok("临时产物字节 == 版本字节（commit 守恒）",
       Path(r2.artifact).read_bytes() == Path(r2.value).read_bytes())
    ok("包装器附 commit_byte_equal=PASS",
       ("commit_byte_equal", "PASS") in [tuple(c) for c in r2.checks])
    names = " ".join(n for n, _ in r2.checks)
    ok("出口校验 V0-V7 全在 checks", all(f"V{i}" in names for i in range(8)))
    ok("checks 无 FAIL", all(st_ != "FAIL" for _, st_ in r2.checks))

    ours = _host_mount_inners(r2.value, HOST)
    ok("产物挂载 0x40000001 单元在位", GUID in ours)
    ok("13B 内芯 == 任务指定正典 hex（逐字节）", ours[GUID].hex() == GOLD_INNER_HEX)
    ok("13B 内芯 == assemble 生成器输出（生成=常量）",
       ours[GUID] == synth.mount_unit_inner(GUID, 20000))

    # ---- ② 负例：拒绝语义 + 版本不变 ----
    v1 = core.current_version("hello")
    rn = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=GUID,
                           category=20007, level_name="hello")
    ok("负例① category=20007 与图头 20000 不符 → REJECTED",
       (not rn.ok) and (rn.error or "").startswith("REJECTED"))
    ok("负例① 版本不变、无 v2 文件", core.current_version("hello") == v1
       and not core.version_path("hello", 2).exists())
    last = core.read_oplog()[-1]
    ok("负例① 日志记 rejected（含类别复核详情）",
       last["kind"] == "rejected" and "20007" in (last["error"] or ""))

    rg = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=0x40000002,
                           category=20000, level_name="hello")
    ok("负例② graph_guid 与图头不符 → REJECTED",
       (not rg.ok) and (rg.error or "").startswith("REJECTED"))

    rh = level.level_mount(graph_gis=str(gis), host_guid=0x41500001, graph_guid=GUID,
                           category=20000, level_name="hello")
    ok("负例③ host 传错段(0x415) → PRECONDITION",
       (not rh.ok) and (rh.error or "").startswith("PRECONDITION"))
    rh2 = level.level_mount(graph_gis=str(gis), host_guid=0x41400002, graph_guid=GUID,
                            category=20000, level_name="hello")
    ok("负例④ host 同段错 id(0x41400002) → PRECONDITION",
       (not rh2.ok) and (rh2.error or "").startswith("PRECONDITION"))
    rm = level.level_mount(graph_gis=str(fx / "no_such.gis"), host_guid=HOST,
                           graph_guid=GUID, category=20000, level_name="hello")
    ok("负例⑤ 图件不存在 → PRECONDITION",
       (not rm.ok) and (rm.error or "").startswith("PRECONDITION"))
    garbage = fx / "garbage.gis"
    garbage.write_bytes(b"\x00\x01\x02\x03 not a container")
    rga = level.level_mount(graph_gis=str(garbage), host_guid=HOST,
                            graph_guid=GUID, category=20000, level_name="hello")
    ok("负例⑥ 垃圾图件 → REJECTED（输入门，不响亮崩）",
       (not rga.ok) and (rga.error or "").startswith("REJECTED"))
    ok("全部负例后版本仍不变", core.current_version("hello") == v1)
    ok("拒绝与前置均落 oplog（ok=False 可查）",
       len(state.log_query(module="level.mount", ok=False).value) >= 2)

    # ---- ③ 幂等再挂（确定性装配对照）----
    r3b = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=GUID,
                            category=20000, level_name="hello")
    ok("hello 域幂等再挂 → v2 且字节与 v1 全同（确定性装配）",
       r3b.ok and r3b.version == 2
       and core.read_current("hello") == Path(r2.value).read_bytes())
    rows_m = state.log_query(module="level.mount", ok=True).value
    ok("log.query 按 module 过滤 level.mount 入账（2 条：v1/v2）",
       len(rows_m) == 2 and [x["version"] for x in rows_m] == [1, 2])

    # ---- ④ level_name 缺省：取 .gis 文件名主干 ----
    r4 = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=GUID,
                           category=20000)
    ok("level_name 缺省 → 域名=.gis 主干（hello_fixture）",
       r4.ok and r4.level == "hello_fixture" and r4.version == 1
       and os.path.exists(r4.value))

    # ---- ⑤ FULL：真实游戏目录样本（在位时）——生成 vs 金样本逐字节 ----
    g_ok, g_reason = st.game_ready()
    ok.full = True  # 以下断言按 FULL 标注
    if gate.ready("mount_full_gold", g_ok, g_reason):
        # 撤注入：走 mods/config 的游戏目录样本解析
        assemble.DEFAULT_BASE = None
        assemble.DEFAULT_GOLD = None
        from mods import config
        gold_real = str(config.gold_level_path())
        rf = level.level_mount(graph_gis=str(gis), host_guid=HOST, graph_guid=GUID,
                               category=20000, level_name="hello_full")
        ok("FULL 正例：真实底座+金样本挂载 PASS",
           rf.ok and rf.version == 1 and rf.level == "hello_full")
        ourf = _host_mount_inners(rf.value, HOST)
        goldf = _host_mount_inners(gold_real, HOST)
        ok("FULL：产物 13B 内芯 == 正典 hex", ourf[GUID].hex() == GOLD_INNER_HEX)
        ok("FULL：产物 13B 内芯 == 金样本同 guid 单元（逐字节，生成=金样本）",
           GUID in goldf and ourf[GUID] == goldf[GUID])
    ok.full = False

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
