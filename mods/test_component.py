# -*- coding: utf-8 -*-
"""component.attach 自测（FULL——需工具树；M4 步 2a 前置件）。

运行：python -m mods.test_component（仓库根；mods.selftest 编排其一）
环境前置：QXY_TOOL_ROOT（合成模板库 + trial_gate，见 mods/config）——缺则整组 SKIP。
状态根经 QXYV2_ROOT 重定向到临时目录；底座 = 合成夹具挂载产物（CORE 链：合成底座 +
合成宿主样本 + 最小图件，零游戏资产）**只读**建版为 v1；工具树 guid_ledger.json 经
monkeypatch 重定向（分配路径不写真实台账）；trial_gate 走真实产线。

覆盖：光源组件生成器形态（含判别律：外层 f501.f4 带 f1 ⇔ 聚光灯、不带 ⇔ 点光源）/ 正例挂载（cid38 光源，f7 槽）/ 读回逐字节一致 /
负例（重复挂 / cid 与载荷不符 / 实体不在位 / slot 非法）/ replace 替换路径 / 底座只读。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SPHERE = 10009002          # 球体（灯头基元）
GUID_T = 0x40470001        # 显式 guid（0x404 机关段）


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    t_ok, t_reason = st.tool_ready()
    if not gate.ready("component_full_attach", t_ok, t_reason):
        print("SKIP [FULL] mods.test_component 整组（工具树未配置，见 mods/config）")
        return st.finish([], gate)

    tmp = tempfile.mkdtemp(prefix="qxy_mods_component_")
    os.environ["QXYV2_ROOT"] = tmp
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from fixtures import synth

    from mods import asset, component, core, entity, level, state  # noqa: E402

    P, _ = asset._ensure_qxy()
    P._LEDGER = str(Path(tmp) / "guid_ledger.json")

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS {len(passes):02d}  {name}")

    # ==== 0. 建版（合成夹具挂载产物读入临时版本域为 v1）====
    fx = Path(tmp) / "fixtures"
    dft = (entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD)
    base_path = synth.write_base_gil(fx / "base.gil")
    entity.assemble.DEFAULT_BASE = str(base_path)
    entity.assemble.DEFAULT_GOLD = str(synth.write_gold_like_gil(fx / "gold_like.gil"))
    gis = synth.write_min_gis(fx / "hello_fixture.gis", 0x40000001, 20000,
                              b"hello", "[hello_fixture] 圈活了".encode("utf-8"))
    rm = level.level_mount(graph_gis=str(gis), host_guid=0x41400001,
                           graph_guid=0x40000001, category=20000, level_name="hello")
    entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD = dft
    ok("底座建版 v1（合成夹具挂载产物）", rm.ok and core.current_version("hello") == 1)
    base_bytes = base_path.read_bytes()

    # ==== 1. 光源组件生成器形态 ====
    comp = component.light_component(name="光源1", radius=9.0, intensity=30.0,
                                     effect_range=3.0, color=0xFFFFB347)
    from mods.component import parse, viv
    f = parse(comp)
    ok("光源组件首字段 f1=38（cid）", f[0][0] == 1 and viv(f[0][2]) == 38)
    ok("光源组件含 f2=1 与载荷 f49", any(x[0] == 2 for x in f) and any(x[0] == 49 for x in f))
    f49 = next(x for x in f if x[0] == 49)
    p = parse(f49[2])
    ok("f49 首子字段 f1=光源条目", p[0][0] == 1)
    entry = parse(p[0][2])
    f501 = next(x for x in entry if x[0] == 501)
    lp = parse(f501[2])
    nm = next(x for x in lp if x[0] == 2)[2].decode("utf-8")
    ok("光源名称=f501.f2", nm == "光源1")
    f4 = next(x for x in lp if x[0] == 4)
    l4 = parse(f4[2])
    import struct as _s
    eff = _s.unpack("<f", next(x for x in l4 if x[0] == 2)[2])[0]
    ok("生效范围落外层 f501.f4.f2（非半径）", abs(eff - 3.0) < 1e-5)
    ok("点光：外层 f501.f4 **不带 f1**（判别律：带 f1 ⇔ 聚光灯）",
       all(x[0] != 1 for x in l4))
    ok("颜色组 f51 在（互斥参数组，多数派）", any(x[0] == 51 for x in l4))
    g51 = parse(next(x for x in l4 if x[0] == 51)[2])
    rad = _s.unpack("<f", next(x for x in g51 if x[0] == 2)[2])[0]
    inten = _s.unpack("<f", next(x for x in g51 if x[0] == 3)[2])[0]
    ok("半径落变体 f51.f2（非强度）", abs(rad - 9.0) < 1e-5)
    ok("强度落变体 f51.f3（非生效范围）", abs(inten - 30.0) < 1e-5)
    ok("挂接点 f501.f6=GI_RootNode",
       next(x for x in lp if x[0] == 6)[2].decode("utf-8") == "GI_RootNode")

    # ==== 1b. 聚光灯槽位（半径=f52.f2 / 角度=f52.f3 / 强度=f52.f4）====
    comp_sp = component.light_component(name="探针聚光", group="f52", radius=33.3,
                                        intensity=7.7, angle=47.5,
                                        effect_range=21.5, color=0xFF00FF00)
    ent_sp = parse(parse(next(x for x in parse(comp_sp) if x[0] == 49)[2])[0][2])
    lp_sp = parse(next(x for x in ent_sp if x[0] == 501)[2])
    l4sp = parse(next(x for x in lp_sp if x[0] == 4)[2])
    gsp = parse(next(x for x in l4sp if x[0] == 52)[2])
    ok("聚：外层 f501.f4.f2 = 生效范围 21.5",
       abs(_s.unpack("<f", next(x for x in l4sp if x[0] == 2)[2])[0] - 21.5) < 1e-4)
    ok("聚：f52.f2 = 半径 33.3",
       abs(_s.unpack("<f", next(x for x in gsp if x[0] == 2)[2])[0] - 33.3) < 1e-4)
    ok("聚：f52.f3 = 角度 47.5",
       abs(_s.unpack("<f", next(x for x in gsp if x[0] == 3)[2])[0] - 47.5) < 1e-4)
    ok("聚：f52.f4 = 强度 7.7",
       abs(_s.unpack("<f", next(x for x in gsp if x[0] == 4)[2])[0] - 7.7) < 1e-4)
    ok("聚：f52.f5 = 颜色 0xFF00FF00",
       viv(next(x for x in gsp if x[0] == 5)[2]) == 0xFF00FF00)
    ok("聚光：外层 f501.f4 **带 f1=1**（判别律：带 f1 ⇔ 聚光灯）",
       next((viv(x[2]) for x in l4sp if x[0] == 1), None) == 1)

    # ==== 2. 放置目标实体（球体=灯头基元）====
    rp = entity.entity_place(aid=SPHERE, pos=(0.0, 20.0), guid=GUID_T)
    ok("放置目标球体实体", rp.ok and rp.value["guid"] == GUID_T)

    # ==== 3. 正例：挂光源组件（cid38，f7 槽）====
    r1 = component.component_attach("hello", GUID_T, component.LIGHT_CID, comp, slot=7)
    ok("attach 光源返回 ok 且有版本", r1.ok and r1.version is not None)
    ch = [(str(a), str(b)) for a, b in r1.checks]
    ok("后验 roundtrip/读回在位/载荷逐字节一致/实体数不变",
       ("roundtrip", "PASS") in ch
       and any(n == "component_readback_present" and v.startswith("PASS") for n, v in ch)
       and any(n == "payload_byte_equal" and v.startswith("PASS") for n, v in ch)
       and any(n == "entity_count_audit" and v.startswith("PASS") for n, v in ch)
       and ("trial_gate", "TRIAL_PASS") in ch)
    ok("包装器 commit_byte_equal 在账", ("commit_byte_equal", "PASS") in ch)
    ok("value.action=appended 且 slot=7 cid=38",
       r1.value["action"] == "appended" and r1.value["slot"] == 7
       and r1.value["cid"] == component.LIGHT_CID)

    # 产物读回：目标实体 f7 槽确有一条 cid38，载荷字节 == 请求
    from mods.component import Container, emit, _entity_bodies, _body_guid, _component_cid
    cur = core.version_path("hello", core.current_version("hello"))
    t = parse(Container.load(str(cur)).proto)
    found = None
    for _c, _e, _en, body in _entity_bodies(t):
        if _body_guid(body) == GUID_T:
            for x in body:
                if isinstance(x, list) and x[0] == 7 and x[1] == 2 and _component_cid(x) == 38:
                    found = x
    ok("关卡字节读回：f7 槽 cid38 存在", found is not None)
    ok("读回载荷 == 生成器字节（逐字节）", found is not None and found[2] == comp)

    # ==== 4. 负例：重复挂（同槽同 cid）→ 前置不过 ====
    r2 = component.component_attach("hello", GUID_T, component.LIGHT_CID, comp, slot=7)
    ok("重复挂被前置拦截（PreconditionError）",
       (not r2.ok) and str(r2.error).startswith("PRECONDITION"))
    ok("重复挂不产新版本（版本不动）", core.current_version("hello") == r1.version)

    # ==== 5. 负例：cid 与载荷不符 ====
    r3 = component.component_attach("hello", GUID_T, 999, comp, slot=7)
    ok("cid≠载荷首字段 → 前置不过",
       (not r3.ok) and "PRECONDITION" in str(r3.error))

    # ==== 6. 负例：实体不在位 ====
    r4 = component.component_attach("hello", 0x40479999, component.LIGHT_CID, comp, slot=7)
    ok("目标 guid 不在位 → 前置不过",
       (not r4.ok) and "PRECONDITION" in str(r4.error))

    # ==== 7. 负例：slot 非法 ====
    r5 = component.component_attach("hello", GUID_T, component.LIGHT_CID, comp, slot=99)
    ok("slot 非法 → 前置不过",
       (not r5.ok) and "PRECONDITION" in str(r5.error))

    # ==== 8. 正例：replace 替换（改半径 → 重挂）====
    comp2 = component.light_component(name="光源1", radius=16.0, color=0xFFB347)
    r6 = component.component_attach("hello", GUID_T, component.LIGHT_CID, comp2,
                                    slot=7, replace=True)
    ok("replace 替换成功", r6.ok and r6.value["action"] == "replaced")
    t2 = parse(Container.load(str(core.version_path("hello", core.current_version("hello")))).proto)
    got2 = None
    for _c, _e, _en, body in _entity_bodies(t2):
        if _body_guid(body) == GUID_T:
            for x in body:
                if isinstance(x, list) and x[0] == 7 and x[1] == 2 and _component_cid(x) == 38:
                    got2 = x
    ok("replace 后读回 == 新字节（仅一条 cid38）", got2 is not None and got2[2] == comp2)

    # ==== 8b. 正例：另一宿主（多宿主可达）+ 限额参数守卫 ====
    rp2 = entity.entity_place(aid=10009008, pos=(5.0, 5.0), guid=0x40470002,
                              scale=(0.3, 1.5, 0.3))
    ok("放置第二宿主（圆柱）", rp2.ok)
    r7 = component.component_attach("hello", 0x40470002, component.LIGHT_CID,
                                    component.light_component(radius=5.0), slot=7)
    ok("光源可挂到另一宿主实体（多宿主可达）", r7.ok)
    r8 = component.component_attach("hello", 0x40470002, component.LIGHT_CID, comp,
                                    slot=7, max_same=0)
    ok("max_same=0 → 前置不过（限额守卫）",
       (not r8.ok) and "PRECONDITION" in str(r8.error))

    # ==== 8c. 可见性组件生成器（步 2b 隐身）====
    vf = parse(component.visible_component(True))
    ok("可见组件首字段 f1=8（cid）", vf[0][0] == 1 and viv(vf[0][2]) == 8)
    ok("可见组件不携带 f2（f6 槽同形）", all(x[0] != 2 for x in vf))
    f18v = next(x for x in vf if x[0] == 18)
    pv = parse(f18v[2])
    ok("可见载荷 f18 = {f1:1, f501:1}",
       [(x[0], viv(x[2])) for x in pv] == [(1, 1), (501, 1)])

    hf = parse(component.visible_component(False))
    f18h = next(x for x in hf if x[0] == 18)
    ph = parse(f18h[2])
    ok("隐身载荷 f18 = {f501:1}（**删 f1**）",
       [(x[0], viv(x[2])) for x in ph] == [(501, 1)])
    ok("隐身载荷严格比可见载荷少 f1 一字段",
       len(f18h[2]) == len(f18v[2]) - 2)
    try:
        component.visible_component("yes")
        ok("visible 非 bool → 前置不过", False)
    except Exception as e:
        ok("visible 非 bool → 前置不过（Precondition）",
           "PRECONDITION" in str(e).upper() or "须为 bool" in str(e))

    # ==== 8d. set_visible 正例：可见→隐身→读回逐字节 ====
    hide = component.visible_component(False)
    rv = component.set_visible("hello", 0x40470002, visible=False)
    ok("set_visible(False) 成功（replace）", rv.ok and rv.value["action"] == "replaced")
    t3 = parse(Container.load(str(core.version_path("hello", core.current_version("hello")))).proto)
    got3 = None
    for _c, _e, _en, body in _entity_bodies(t3):
        if _body_guid(body) == 0x40470002:
            for x in body:
                if isinstance(x, list) and x[0] == 6 and x[1] == 2 and _component_cid(x) == 8:
                    got3 = x
    ok("读回：f6 cid8 载荷 == 隐身字节", got3 is not None and got3[2] == hide)
    ok("读回：隐身载荷内无 f1",
       got3 is not None and all(y[0] != 1 for y in
                                parse(next(z for z in parse(got3[2]) if z[0] == 18)[2])))
    rv2 = component.set_visible("hello", 0x40470002, visible=True)
    ok("set_visible(True) 可复原", rv2.ok and rv2.value["action"] == "replaced")

    # ==== 8e. 负例：目标实体不在位 ====
    rv3 = component.set_visible("hello", 0x40479999, visible=False)
    ok("目标不在位 → 前置不过", (not rv3.ok) and "PRECONDITION" in str(rv3.error))

    # ==== 9. 底座只读纪律 ====
    ok("合成夹具底座未被改动", base_path.read_bytes() == base_bytes)

    return st.finish(passes, gate)


if __name__ == "__main__":
    sys.exit(main())
