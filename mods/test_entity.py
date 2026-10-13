# -*- coding: utf-8 -*-
"""entity.place 自测（FULL——需工具树；底座=合成关卡，零游戏目录依赖）。

运行：python -m mods.test_entity（仓库根；mods.selftest 编排其一）
环境前置：QXY_TOOL_ROOT（合成模板库 + trial_gate，见 mods/config）——缺则整组
SKIP 如实报告（mods.selftest --full 模式下判失败）。
状态根经 QXYV2_ROOT 重定向到临时目录；关卡底座 = 合成夹具挂载产物（CORE 链：
合成底座 + 合成宿主样本 + 最小图件，零游戏资产）；工具树台账经 monkeypatch
重定向到临时文件（分配路径验证不写真实台账）。trial_gate 走真实产线
（subprocess python -m qxy.trial_gate，cwd=工具树根）——门禁本身不在替换范围，
它是被验对象的一部分。

在线/游戏侧验收（真实导入+试玩）不在本自测范围——导入与试玩是用户白名单动作。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行

AID = 20001018          # 木质箱子（official_prefab_db：placeable、type 1402 机关族、有模板）
AID_MON = 30003006      # 木盾丘丘暴徒（type 1405 怪物族——验 0x408 段位律与双注册）
AID_NP = 30001010       # 火深渊法师（placeable=False——验非可放置拦截）
GUID1 = 0x40460001      # 显式 guid（0x404 机关段）


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    t_ok, t_reason = st.tool_ready()
    if not gate.ready("entity_full_place", t_ok, t_reason):
        print("SKIP [FULL] mods.test_entity 整组（工具树未配置，见 mods/config）")
        return st.finish([], gate)

    tmp = tempfile.mkdtemp(prefix="qxy_mods_entity_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：levels/、state/、oplog 全落临时目录
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from fixtures import synth

    from mods import core, state  # noqa: E402  env 先设，core 动态读根
    from mods import level

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS [FULL] {len(passes):02d}  {name}")

    def pairs(checks) -> list[tuple[str, str]]:
        return [(str(c[0]), str(c[1])) for c in checks]

    def level_bytes() -> bytes:
        """当前版本 .gil 的 proto 段（容器头 + proto + 尾，取 proto）。"""
        from mods.entity import assemble
        c = assemble.Container.load(
            str(core.version_path("hello", core.current_version("hello"))))
        return c.proto

    def f5_guids(b: bytes) -> list[int]:
        from mods.entity import assemble, parse
        t = parse(b)
        f5 = assemble._fields(t, 5)[0]
        return [assemble.viv(parse(e[2])[0][2]) for e in parse(f5[2])
                if isinstance(e, list) and e[0] == 1]

    def tab3_leaf_guids(b: bytes) -> set[int]:
        from mods.entity import assemble, parse, TREE_TAB_ENTITY
        t = parse(b)
        out = set()
        for e in parse(assemble._fields(t, 6)[0][2]):
            if not (isinstance(e, list) and e[0] == 1):
                continue
            tr = parse(e[2])
            tab = next((assemble.viv(x[2]) for x in tr
                        if x[0] == 1 and x[1] == 0), None)
            if tab != TREE_TAB_ENTITY:
                continue
            for x in tr:
                if not (x[0] == 3 and x[1] == 2):
                    continue
                for lf in parse(x[2]):
                    if lf[0] == 5 and lf[1] == 2:
                        lt = parse(lf[2])
                        out.add(next(assemble.viv(z[2]) for z in lt if z[0] == 2))
        return out

    # ==== 0. 建版：合成夹具挂载产物只读拷入临时版本域为 v1 ====
    from mods import entity
    fx = Path(tmp) / "fixtures"
    assemble_defaults = (entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD)
    entity.assemble.DEFAULT_BASE = str(synth.write_base_gil(fx / "base.gil"))
    entity.assemble.DEFAULT_GOLD = str(synth.write_gold_like_gil(fx / "gold_like.gil"))
    gis = synth.write_min_gis(fx / "hello_fixture.gis", 0x40000001, 20000,
                              b"hello", "[hello_fixture] 圈活了".encode("utf-8"))
    rm = level.level_mount(graph_gis=str(gis), host_guid=0x41400001,
                           graph_guid=0x40000001, category=20000, level_name="hello")
    entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD = assemble_defaults
    assert rm.ok, f"合成底座挂载失败: {rm.error}"
    ok("底座建版 v1（合成挂载产物）", core.current_version("hello") == 1)
    ok("底座实体数=1（宿主 0x41400001）", f5_guids(level_bytes()) == [0x41400001])
    ok("底座 tab3 叶=宿主一叶", tab3_leaf_guids(level_bytes()) == {0x41400001})

    # 台账重定向（alloc_guids 分配即记台账是产线机制；自测不污染真实台账）
    P, _ = entity._ensure_qxy()
    ledger_tmp = Path(tmp) / "guid_ledger.json"
    P._LEDGER = str(ledger_tmp)

    # ==== 1. 正例①：箱子显式 guid → v2、实体数+1、注册叶在位 ====
    r1 = entity.entity_place(aid=AID, pos=(5.0, 5.0), guid=GUID1)
    ok("place 返回 ok 且 version=2", r1.ok and r1.version == 2)
    ok("value 载荷 guid/aid/实体数对账",
       r1.value["guid"] == GUID1 and r1.value["aid"] == AID
       and r1.value["entity_count"] == 2)
    ch = pairs(r1.checks)
    ok("后验 roundtrip/闭合/注册叶全 PASS",
       ("roundtrip", "PASS") in ch
       and any(n == "closure_guid_occurrences" and v.startswith("PASS")
               for n, v in ch)
       and any(n == "tab3_leaf_registered" and v.startswith("PASS") for n, v in ch)
       and ("trial_gate", "TRIAL_PASS") in ch)
    ok("包装器 commit_byte_equal 在账", ("commit_byte_equal", "PASS") in ch)
    ok("f5 实体=[宿主, 箱子]（尾部追加序）", f5_guids(level_bytes()) == [0x41400001, GUID1])
    ok("tab3 叶={宿主, 箱子}（宿主叶保真+新叶追加）",
       tab3_leaf_guids(level_bytes()) == {0x41400001, GUID1})

    # ==== 2. 正例②③：guid=None 台账分配（机关 0x404 带 / 怪 0x408 带）====
    r2 = entity.entity_place(aid=AID, pos=(0.0, 0.0))          # 机关 → 台账带 0x40460001+
    g2 = r2.value["guid"]
    ok("机关 guid=None → 0x40460001+ 分配带", r2.ok and 0x40460001 <= g2 < 0x40500000)
    ok("台账文件落了一条分配记录",
       ledger_tmp.exists() and "allocations" in ledger_tmp.read_text(encoding="utf-8"))
    r3 = entity.entity_place(aid=AID_MON, pos=(-5.0, 10.0))    # 怪 → 0x40810000+ 分配带
    g3 = r3.value["guid"]
    ok("怪物 guid=None → 0x40810000+ 分配带（段位律）",
       r3.ok and 0x40810000 <= g3 < 0x40900000 and r3.value["monster"] is True)
    ok("怪物叶注册（双注册律闭合）",
       any(n == "tab3_leaf_registered" and v.startswith("PASS")
           for n, v in pairs(r3.checks)))

    # ==== 3. 连续放置对账：v1 底座 + 3 次放置 → current=4、日志 3 条 ok ====
    ok("三次放置后 current=4（v1+3）", core.current_version("hello") == 4
       and core.version_path("hello", 4).exists())
    ok("f5 实体数=4（宿主+箱+箱+怪）", len(f5_guids(level_bytes())) == 4)
    ok("三 guid 全档互异", len({GUID1, g2, g3}) == 3)
    ok("tab3 叶=4 枚", len(tab3_leaf_guids(level_bytes())) == 4)
    rows = state.log_query(module="entity.place", ok=True)
    ok("oplog entity.place ok 恰 3 条", len(rows.value) == 3
       and all(x["version"] == i + 2 for i, x in enumerate(rows.value)))

    # ==== 4. 负例：全部 PRECONDITION（换路，不计拒绝）====
    v_before = core.current_version("hello")
    r_bad = entity.entity_place(aid=999999999, pos=(0, 0))
    ok("不存在的 aid → PRECONDITION",
       (not r_bad.ok) and (r_bad.error or "").startswith("PRECONDITION"))
    r_np = entity.entity_place(aid=AID_NP, pos=(0, 0))
    ok("placeable=False 资产 → PRECONDITION",
       (not r_np.ok) and (r_np.error or "").startswith("PRECONDITION"))
    r_seg = entity.entity_place(aid=AID_MON, pos=(0, 0), guid=0x40000001)
    ok("怪物 aid 给 0x400 段 guid → PRECONDITION（段位律）",
       (not r_seg.ok) and (r_seg.error or "").startswith("PRECONDITION")
       and "段位律" in (r_seg.error or ""))
    r_x = entity.entity_place(aid=AID, pos=(0, 0), guid=0x40820001)
    ok("机关 aid 给 0x408 段 guid → PRECONDITION",
       (not r_x.ok) and (r_x.error or "").startswith("PRECONDITION"))
    r_dup = entity.entity_place(aid=AID, pos=(0, 0), guid=0x41400001)
    ok("与关卡宿主撞号 → PRECONDITION（全档扫描）",
       (not r_dup.ok) and (r_dup.error or "").startswith("PRECONDITION"))
    r_dup2 = entity.entity_place(aid=AID, pos=(0, 0), guid=GUID1)
    ok("与已放置实体撞号 → PRECONDITION",
       (not r_dup2.ok) and (r_dup2.error or "").startswith("PRECONDITION"))
    r_host = entity.entity_place(aid=10003004, pos=(0, 0))
    ok("关卡实体(1401) → PRECONDITION（宿主归 level.mount）",
       (not r_host.ok) and (r_host.error or "").startswith("PRECONDITION"))
    r_lv = entity.entity_place(aid=AID, pos=(0, 0), level_name="no_such_level")
    ok("不存在的关卡 → PRECONDITION",
       (not r_lv.ok) and (r_lv.error or "").startswith("PRECONDITION"))
    r_pos = entity.entity_place(aid=AID, pos="北偏东")
    ok("非法 pos → PRECONDITION", (not r_pos.ok)
       and (r_pos.error or "").startswith("PRECONDITION"))
    r_sc = entity.entity_place(aid=AID, pos=(0, 0), scale=(1.0, 2.0))
    ok("非法 scale → PRECONDITION", (not r_sc.ok)
       and (r_sc.error or "").startswith("PRECONDITION"))
    ok("全部负例后版本不动（无 v5）", core.current_version("hello") == v_before
       and not core.version_path("hello", v_before + 1).exists())
    negs = state.log_query(module="entity.place", ok=False)
    ok("负例全落日志且都是 precondition 态",
       len(negs.value) == 10 and all(x["kind"] == "precondition" for x in negs.value))

    # ==== 5. 产物字节级终验：v4 roundtrip + 每 guid 恰 2 合法位 ====
    from mods.entity import _guid_occurrences, parse, emit  # noqa: E402
    b4 = level_bytes()
    t4 = parse(b4)
    ok("v4 roundtrip 守恒", emit(parse(b4)) == b4)
    for g in (GUID1, g2, g3):
        good, stranger = _guid_occurrences(t4, g)
        ok(f"0x{g:x} 全档恰 2 合法位（身份位+注册叶）", good == 2 and not stranger)

    # ==== 6. 注册确认与日志可审计 ====
    ok("registry 含 entity.place", "entity.place" in core.list_modules())
    ok("log.query 可查 entity.place", len(state.log_query(module="entity.place").value) == 13)

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
