# -*- coding: utf-8 -*-
"""element.build 自测（FULL——需工具树；元件通道固化，案例 #71）。

运行：python -m mods.test_element（仓库根；mods.selftest 编排其一）
环境前置：QXY_TOOL_ROOT（合成模板库 + trial_gate，见 mods/config）——缺则整组
SKIP 如实报告（mods.selftest --full 模式下判失败）。
状态根经 QXYV2_ROOT 重定向到临时目录，落盘目录经 out_dir 注入——零污染真实 state/。
guid 分配经 monkeypatch 假台账（不写工具树 guid_ledger.json）。trial_gate 走真实产线
（subprocess python -m qxy.trial_gate，cwd=工具树根）——门禁本身是被验对象。

正例 = 最小元件（复现本次导入成功件形态）；负例 = aid 不在册 / guid 段错 / 成员数超限。
在线验收（真实导入+拖出）不在本自测范围——导入是用户白名单动作。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行

MEMBER_AID = 10009001   # 长方体（元件组成员；official_prefab_db 在册）


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    t_ok, t_reason = st.tool_ready()
    if not gate.ready("element_full_build", t_ok, t_reason):
        print("SKIP [FULL] mods.test_element 整组（工具树未配置，见 mods/config）")
        return st.finish([], gate)

    tmp = tempfile.mkdtemp(prefix="qxy_mods_element_")
    os.environ["QXYV2_ROOT"] = tmp
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import config, core, element  # noqa: E402  env 先设

    # guid 分配假台账（避免写工具树 guid_ledger.json）：0x40460001 起（BAND_ELEMENT 内）
    root = config.require_tool_root("元件构造/打包/元件体门禁链路")
    if str(root) not in sys.path:
        sys.path.append(str(root))
    import qxy.paradigm as P  # noqa: E402
    _seq = [0x40460001]

    def _fake_alloc(count, note=None):
        out = [_seq[0] + i for i in range(count)]
        _seq[0] += count
        return out

    P.alloc_guids = _fake_alloc

    elems = Path(tmp) / "elements"
    elems.mkdir(parents=True, exist_ok=True)
    passes: list[str] = []

    def ok(name, cond):
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS {len(passes):02d}  {name}")

    def pairs(checks):
        return [tuple(c) for c in checks]

    # ============ 1. 正例：最小元件（元件组 1 主件 + 1 成员）============
    # bare=False 强制定义体——复现案例 #71 成功件的"嵌入形态"（成员带体）；
    # 该件无实例数据，若不显式置 False 会被自动判为裸引用（见自测 §3e）。
    r = element.element_build(members=[{"aid": MEMBER_AID, "pos": (0, 0, 0), "bare": False}],
                              name="最小元件_test1", out_dir=str(elems))
    pkg = elems / "最小元件_test1.gia"
    ok("正例/返回 ok 且产物在注入目录", r.ok and r.artifact == str(pkg))
    ok("正例/产物存在非空", pkg.is_file() and pkg.stat().st_size > 0)
    ok("正例/后验 trial_gate=TRIAL_PASS", ("trial_gate", "TRIAL_PASS") in pairs(r.checks))
    ok("正例/元件体门 PASS", ("element_body_gate", "PASS") in pairs(r.checks))
    ok("正例/count=2 guids=2", r.value["count"] == 2 and len(r.value["guids"]) == 2)
    ok("正例/kind=group", r.value["kind"] == "group")

    # 复现成功件形态：成员体三槽 cid 序列与 7.1 正典一致
    from qxfmt.pbtree import parse, first, varint_value  # noqa: E402
    from qxfmt.container import Container  # noqa: E402
    c = Container.load(pkg)
    top = parse(c.proto)
    member_body = None
    for nd in top:
        if nd[0] == 2 and nd[1] == 2:
            e = parse(nd[2])
            member_body = parse(first(e, 11)[2])[0][2]
            break
    seqs = {}
    for sf in (6, 7, 8):
        seqs[sf] = [varint_value(parse(x[2])[0]) for x in parse(member_body)
                    if x[0] == sf and x[1] == 2]
    ok("正例/成员体 f6 cid 序列=正典", seqs[6] == [1, 13, 14, 38, 40, 111, 61, 62])
    ok("正例/成员体 f7 cid 序列=正典", seqs[7] == [1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 16, 17, 19, 20, 22])
    ok("正例/成员体 f8 cid 序列=正典", seqs[8] == [18, 1, 3, 19, 6, 14])

    # ============ 2. 正例：实例数据路（scale/color/roty/name 透传 → 槽位平移）============
    r2 = element.element_build(
        members=[{"aid": MEMBER_AID, "pos": (1.0, 2.0, 3.0), "scale": (2.0, 0.5, 1.0),
                  "color": (0x35528F, 0xC0, None), "rot": (0, 45, 0), "name": "券石_1"}],
        name="实例数据件", out_dir=str(elems))
    ok("实例数据路/ok + trial_gate PASS",
       r2.ok and ("trial_gate", "TRIAL_PASS") in pairs(r2.checks))
    c2 = Container.load(elems / "实例数据件.gia")
    mb2 = None
    for nd in parse(c2.proto):
        if nd[0] == 2 and nd[1] == 2:
            e = parse(nd[2])
            mb2 = parse(first(e, 11)[2])[0][2]
            break
    cids2 = {sf: [varint_value(parse(x[2])[0]) for x in parse(mb2) if x[0] == sf and x[1] == 2]
             for sf in (6, 7, 8)}
    ok("实例数据路/成员体带 f7 cid1(变换)+cid22(染色)", 1 in cids2[7] and 22 in cids2[7])
    ok("实例数据路/成员体 cid 序列=正典(去实例态)",
       cids2[6] == [1, 13, 14, 38, 40, 111, 61, 62] and len(cids2[8]) >= 1)

    # ============ 3. 正例：单体元件（single，1 条目自引用闭环）============
    r3 = element.element_build(members=[{"aid": MEMBER_AID, "pos": (0, 0, 0)}],
                               name="单体件", kind="single", out_dir=str(elems))
    ok("单体元件/ok + trial_gate PASS",
       r3.ok and ("trial_gate", "TRIAL_PASS") in pairs(r3.checks) and r3.value["count"] == 1)

    # ============ 3b. 正例：多成员组 + 三轴旋转 + 摆放表记录数交叉核对 ============
    r3b = element.element_build(
        members=[{"aid": MEMBER_AID, "pos": (i, 0, i * 0.5), "scale": (0.3, 0.28, 0.22),
                  "rot": (0, 0, 30.0 * i), "color": (0x35528F, 0x18, None), "name": f"成员{i}"}
                 for i in range(6)],
        name="多成员组", out_dir=str(elems))
    ok("多成员组/ok + trial_gate PASS + count=7",
       r3b.ok and ("trial_gate", "TRIAL_PASS") in pairs(r3b.checks) and r3b.value["count"] == 7)
    # 主件 cid61 摆放表记录数 == 成员数
    c3b = Container.load(elems / "多成员组.gia")
    tbl = None
    for nd in parse(c3b.proto):
        if nd[0] == 1 and nd[1] == 2:
            e = parse(nd[2])
            master = parse(first(e, 11)[2])[0][2]
            for comp in parse(master):
                if comp[0] == 6 and comp[1] == 2:
                    ci = parse(comp[2])
                    if varint_value(first(ci, 1)) == 61:
                        tbl = parse(first(ci, 65)[2])
            break
    ok("多成员组/主件 cid61 记录数=6", tbl is not None and len(tbl) == 6)
    # 三轴旋转透传：扫描所有成员体 f7.cid1 的旋转消息，应至少一件含 f3(绕 Z)
    has_z = False
    for nd in parse(c3b.proto):
        if not (nd[0] == 2 and nd[1] == 2):
            continue
        e = parse(nd[2])
        mbody = parse(first(e, 11)[2])[0][2]
        for comp in parse(mbody):
            if comp[0] == 7 and comp[1] == 2:
                ci = parse(comp[2])
                if varint_value(first(ci, 1)) == 1:
                    p = parse(first(ci, 11)[2])
                    r2 = first(p, 2)
                    if r2 and r2[1] == 2 and any(x[0] == 3 for x in parse(r2[2])):
                        has_z = True
    ok("多成员组/成员体 f7.cid1 三轴旋转透传（含 f3 绕Z）", has_z)

    # ============ 3c. 正例：旋转交叉核对（拱券 5 件含不同 rot 形态 → 逐件读回对齐）============
    # rot 形态覆盖：单轴 Z / 单轴 Y / 单轴 X / 负角 Z / 无旋转。与 BOM 的 rot 形态同构。
    arch_specs = [
        {"aid": MEMBER_AID, "pos": (0.0, 0.0, 0.0), "scale": (0.3, 0.28, 0.22),
         "rot": (0, 0, 90), "color": (0x35528F, 0x18, None), "name": "券石_Z90"},
        {"aid": MEMBER_AID, "pos": (1.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0),
         "rot": (0, 90, 0), "name": "券石_Y90"},
        {"aid": MEMBER_AID, "pos": (2.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0),
         "rot": (45, 0, 0), "name": "券石_X45"},
        {"aid": MEMBER_AID, "pos": (3.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0),
         "rot": (0, 0, -80.6), "name": "券石_Zneg"},
        {"aid": MEMBER_AID, "pos": (4.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0),
         "name": "券石_none"},
    ]
    r3c = element.element_build(members=arch_specs, name="旋转交叉核对样", out_dir=str(elems))
    ok("旋转交叉核对/ok + trial_gate PASS（旋转后验守卫未拦）",
       r3c.ok and ("trial_gate", "TRIAL_PASS") in pairs(r3c.checks))
    c3c = Container.load(elems / "旋转交叉核对样.gia")
    got_rots = []
    for nd in parse(c3c.proto):
        if nd[0] == 2 and nd[1] == 2:
            e = parse(nd[2])
            mb = parse(first(e, 11)[2])[0][2]
            got_rots.append({k: round(v, 3) for k, v in element.read_body_rotation(mb).items()})
    want_rots = [{k: round(v, 3) for k, v in element._spec_rot(s.get("rot")).items()}
                 for s in arch_specs]
    ok("旋转交叉核对/逐件读回 == 请求（Z/Y/X/负Z/无 五形态全对齐）", got_rots == want_rots)
    ok("旋转交叉核对/单轴形态只写对应字段（Z→f3, Y→f2, X→f1）",
       got_rots[0] == {3: 90.0} and got_rots[1] == {2: 90.0}
       and got_rots[2] == {1: 45.0} and got_rots[3] == {3: -80.6} and got_rots[4] == {})

    # ============ 3d. 对冲：member_table_rotation=True 时摆放表 f3 载旋转 ============
    r3d = element.element_build(
        members=[m for m in arch_specs if m.get("rot")], name="摆放表旋转",
        out_dir=str(elems), member_table_rotation=True)
    ok("摆放表旋转/ok + trial_gate PASS",
       r3d.ok and ("trial_gate", "TRIAL_PASS") in pairs(r3d.checks))
    c3d = Container.load(elems / "摆放表旋转.gia")
    import struct as _st  # noqa: E402

    def _f3rot(rec):
        f3 = first(parse(rec[2]), 3)
        if f3 is None or not f3[2]:
            return {}
        return {x[0]: round(_st.unpack("<f", x[2])[0], 3) for x in parse(f3[2])}

    recs3d = []
    for nd in parse(c3d.proto):
        if nd[0] == 1 and nd[1] == 2:
            e = parse(nd[2])
            master = parse(first(e, 11)[2])[0][2]
            for comp in parse(master):
                if comp[0] == 6 and comp[1] == 2:
                    ci = parse(comp[2])
                    if varint_value(first(ci, 1)) == 61:
                        recs3d = parse(first(ci, 65)[2])
            break
    tbl_rot = [_f3rot(r) for r in recs3d]
    ok("摆放表旋转/每条记录 f3 载对应成员旋转（Z/Y/X/负Z）",
       tbl_rot == [{3: 90.0}, {2: 90.0}, {1: 45.0}, {3: -80.6}])

    # ============ 3e. 真实样本 f3 旋转字节回归（f3=成员旋转 定案 2026-10-14）============
    # 证据：用户真实样本「测试2」主件 0x40400007 rec1 f3 原字节；A/B 判定实验的 B 件 rec2 f3 原字节。
    TEST2_F3 = bytes.fromhex("0d00008c431500008c431d00008c43")   # 三轴各 280°（无缩放）
    B_REF2_F3 = bytes.fromhex("150000b442")                      # 绕 Y 90°（A/B 的 B 件 rec2）
    ok("真实样本f3/测试2 rec1 三轴280° 字节相符（0d00008c43 15… 1d…）",
       element._rotmsg({1: 280.0, 2: 280.0, 3: 280.0}) == TEST2_F3)
    ok("真实样本f3/A/B 的 B 件 rec2 绕Y90° 字节相符（150000b442）",
       element._rotmsg({2: 90.0}) == B_REF2_F3)
    import struct as _st280  # noqa: E402
    ok("真实样本f3/三轴280° 可解回原值",
       [round(_st280.unpack('<f', TEST2_F3[1:5])[0], 2),
        round(_st280.unpack('<f', TEST2_F3[6:10])[0], 2),
        round(_st280.unpack('<f', TEST2_F3[11:15])[0], 2)] == [280.0, 280.0, 280.0])

    # ============ 3f. 缺省 member_table_rotation=True：摆放表 f3 自动载旋转 ============
    tbl3b = []
    for nd in parse(c3b.proto):
        if nd[0] == 1 and nd[1] == 2:
            e = parse(nd[2])
            master = parse(first(e, 11)[2])[0][2]
            tbl3b = element.table_record_rot(master)
            break
    ok("缺省/摆放表 f3 载旋转（member_table_rotation 缺省 True）",
       [{k: round(v, 3) for k, v in r.items()} for r in tbl3b]
       == [{}, {3: 30.0}, {3: 60.0}, {3: 90.0}, {3: 120.0}, {3: 150.0}])

    # ============ 3g. 裸引用（减重）：无实例数据的成员不建定义 ============
    r3g = element.element_build(
        members=[{"aid": MEMBER_AID, "pos": (0.0, 0.0, 0.0)},                        # 无数据 → 裸引用
                 {"aid": MEMBER_AID, "pos": (1.0, 0.0, 0.0), "scale": (2.0, 2.0, 2.0)}],  # 有缩放 → 定义体
        name="裸引用样", out_dir=str(elems))
    ok("裸引用/ok + trial_gate PASS", r3g.ok and ("trial_gate", "TRIAL_PASS") in pairs(r3g.checks))
    c3g = Container.load(elems / "裸引用样.gia")
    n_ent3g = len([nd for nd in parse(c3g.proto) if nd[0] == 2 and nd[1] == 2])
    rec_tokens = []
    for nd in parse(c3g.proto):
        if nd[0] == 1 and nd[1] == 2:
            e = parse(nd[2])
            master = parse(first(e, 11)[2])[0][2]
            for comp in parse(master):
                if comp[0] == 6 and comp[1] == 2 and varint_value(first(parse(comp[2]), 1)) == 61:
                    for rn in parse(first(parse(comp[2]), 65)[2]):
                        rf = parse(rn[2])
                        rec_tokens.append((varint_value(first(rf, 1)), varint_value(first(rf, 5))))
            break
    ok("裸引用/仅 1 个成员条目（无数据成员不建定义）；count 仍记 2 条",
       n_ent3g == 1 and r3g.value["count"] == 2)
    ok("裸引用/首条表记录 f1=f5=aid（裸官方 prefab）", rec_tokens[0] == (MEMBER_AID, MEMBER_AID))
    ok("裸引用/次条表记录 f1=成员guid(≠aid) 且 f5=aid（定义体成员）",
       len(rec_tokens) == 2 and rec_tokens[1][1] == MEMBER_AID and rec_tokens[1][0] != MEMBER_AID)
    # 反例：单位缩放 + 无染色/名 且显式 bare=False → 仍建定义体
    r3h = element.element_build(members=[{"aid": MEMBER_AID, "pos": (0, 0, 0), "bare": False}],
                                name="强制定义", out_dir=str(elems))
    n_ent3h = len([nd for nd in parse(Container.load(elems / "强制定义.gia").proto)
                   if nd[0] == 2 and nd[1] == 2])
    ok("裸引用/bare=False 覆盖自动判据 → 仍建定义体", r3h.ok and n_ent3h == 1
       and r3h.value["count"] == 2)

    # ============ 4. 负例：aid 不在册 ============
    r4 = element.element_build(members=[{"aid": 99999999, "pos": (0, 0, 0)}],
                               name="坏aid", out_dir=str(elems))
    ok("负例/aid 不在册 → PRECONDITION", (not r4.ok)
       and (r4.error or "").startswith("PRECONDITION"))

    # ============ 5. 负例：guid 段错（0x414 关卡实体段）============
    r5 = element.element_build(members=[{"aid": MEMBER_AID, "pos": (0, 0, 0)}],
                               name="坏guid", guid=0x41400001, out_dir=str(elems))
    ok("负例/guid 落 0x414 → PRECONDITION", (not r5.ok)
       and (r5.error or "").startswith("PRECONDITION"))

    # ============ 6. 负例：成员数超限（注入 MEMBER_LIMIT=3 快速触发）============
    # 真 limit=512（纯溢出保护）；注入小值以快速验证守卫分支。
    _saved_limit = element.MEMBER_LIMIT
    element.MEMBER_LIMIT = 3
    try:
        big = [{"aid": MEMBER_AID, "pos": (0, 0, 0)} for _ in range(3)]
        r6 = element.element_build(members=big, name="超限", out_dir=str(elems))
    finally:
        element.MEMBER_LIMIT = _saved_limit
    ok("负例/成员数 ≥ MEMBER_LIMIT（注入 3）→ PRECONDITION", (not r6.ok)
       and (r6.error or "").startswith("PRECONDITION"))
    ok("负例/MEMBER_LIMIT 默认放行 266（>266 才拦）", element.MEMBER_LIMIT > 266)

    # ============ 7. 负例：kind 非法 / members 空 ============
    r7 = element.element_build(members=[{"aid": MEMBER_AID}], name="坏kind",
                               kind="junk", out_dir=str(elems))
    ok("负例/kind 非法 → PRECONDITION", (not r7.ok) and (r7.error or "").startswith("PRECONDITION"))
    r8 = element.element_build(members=[], name="空成员", out_dir=str(elems))
    ok("负例/members 空 → PRECONDITION", (not r8.ok) and (r8.error or "").startswith("PRECONDITION"))

    # ============ 8. 去重（定义共享）：同键成员复用同一 guid / 同一条定义体 ============
    # 键 = (aid,scale,color,name)。前两件同键（仅 pos/rot 不同）→ 共享定义；第三件键异 → 独立。
    r9 = element.element_build(
        members=[
            {"aid": MEMBER_AID, "pos": (0.0, 0.0, 0.0), "scale": (0.3, 0.28, 0.22),
             "color": (0x35528F, 0x18, None), "rot": (0, 0, 30.0), "name": "券石A"},
            {"aid": MEMBER_AID, "pos": (1.0, 0.0, 0.0), "scale": (0.3, 0.28, 0.22),
             "color": (0x35528F, 0x18, None), "rot": (0, 0, 60.0), "name": "券石A"},
            {"aid": MEMBER_AID, "pos": (2.0, 0.0, 0.0), "scale": (0.5, 0.5, 0.5),
             "color": (0x35528F, 0x18, None), "name": "另型"},
        ],
        name="去重样", out_dir=str(elems), dedup=True)
    ok("去重/ok + trial_gate PASS", r9.ok and ("trial_gate", "TRIAL_PASS") in pairs(r9.checks))
    c9 = Container.load(elems / "去重样.gia")
    n_ent9 = len([nd for nd in parse(c9.proto) if nd[0] == 2 and nd[1] == 2])
    ok("去重/3 成员 → 2 条定义（同键前两件共享）",
       n_ent9 == 2 and r9.value["count"] == 3 and r9.value["members"] == 3
       and r9.value["definitions"] == 3)
    recs9 = []
    tbl9 = []
    for nd in parse(c9.proto):
        if nd[0] == 1 and nd[1] == 2:
            e = parse(nd[2])
            master = parse(first(e, 11)[2])[0][2]
            for comp in parse(master):
                if comp[0] == 6 and comp[1] == 2 and varint_value(first(parse(comp[2]), 1)) == 61:
                    for rn in parse(first(parse(comp[2]), 65)[2]):
                        rf = parse(rn[2])
                        recs9.append((varint_value(first(rf, 1)), varint_value(first(rf, 5))))
                    tbl9 = element.table_record_rot(master)
            break
    ok("去重/摆放表 3 条记录，前两条 token 相同（共享定义）",
       len(recs9) == 3 and recs9[0][0] == recs9[1][0] and recs9[2][0] != recs9[0][0])
    ok("去重/表 f3 逐件旋转仍各异（30/60）——位置旋转不进定义体",
       [{k: round(v, 3) for k, v in r.items()} for r in tbl9] == [{3: 30.0}, {3: 60.0}, {}])
    # 共享定义体 = 原点/零旋转（体的 pos/rot 空、scale/color 保留）
    mb0 = None
    for nd in parse(c9.proto):
        if nd[0] == 2 and nd[1] == 2:
            e = parse(nd[2])
            mb0 = parse(first(e, 11)[2])[0][2]
            break
    ok("去重/共享定义体取原点零旋转（read_body_rotation={}）", element.read_body_rotation(mb0) == {})
    # 键含 name：把第三件 name 也改成"券石A" → 与它们同键 → 应共享（3 件 1 定义）
    r10 = element.element_build(
        members=[
            {"aid": MEMBER_AID, "pos": (0.0, 0.0, 0.0), "scale": (0.3, 0.28, 0.22),
             "color": (0x35528F, 0x18, None), "name": "券石A"},
            {"aid": MEMBER_AID, "pos": (1.0, 0.0, 0.0), "scale": (0.3, 0.28, 0.22),
             "color": (0x35528F, 0x18, None), "name": "券石A"},
        ],
        name="去重全并", out_dir=str(elems), dedup=True)
    n_ent10 = len([nd for nd in parse(Container.load(elems / "去重全并.gia").proto)
                   if nd[0] == 2 and nd[1] == 2])
    ok("去重/键含 name：名字不同则分家（26 已证）；此处同名 → 2 成员 1 定义",
       r10.ok and n_ent10 == 1 and r10.value["count"] == 2)

    # ============ 8. 名字组件（元件库显示名权威字段，2026-10-14 定案）============
    # 8a 组主件体 cid1→f11→f1 == 元件名；且组件字节形态 = synth 填名同款（08015a<len>0a<slen>）
    def _master_body(path):
        cp = Container.load(path)
        for nd in parse(cp.proto):
            if nd[0] == 1 and nd[1] == 2:
                e = parse(nd[2])
                return parse(first(e, 11)[2])[0][2]
        return None

    def _name_comp(body):
        for x in parse(body):
            if x[0] == 6 and x[1] == 2 and varint_value(parse(x[2])[0]) == 1:
                return x[2]
        return None

    mb_master = _master_body(pkg)
    ok("名字组件/组主件体读回 == 元件名", element.read_body_name(mb_master) == "最小元件_test1")
    # 组件原始字节：{f1:1, f11:{f1:name}} —— 与 synth.synthesize_entity 填名逐字节同款
    _comp1 = _name_comp(mb_master)
    _nb1 = "最小元件_test1".encode("utf-8")
    _want1 = (b"\x08\x01" + bytes([0x5A, 2 + len(_nb1), 0x0A, len(_nb1)]) + _nb1)
    ok("名字组件/字节形态 = {f1:1, f11:{f1:name}}（synth 填名同款）", _comp1 == _want1)
    # 8b 三种形态（组/实例数据路/单体）主件体名都 == 元件名
    ok("名字组件/实例数据路主件体名 == '实例数据件'",
       element.read_body_name(_master_body(elems / "实例数据件.gia")) == "实例数据件")
    ok("名字组件/单体元件主件体名 == '单体件'",
       element.read_body_name(_master_body(elems / "单体件.gia")) == "单体件")
    ok("名字组件/多成员组主件体名 == '多成员组'",
       element.read_body_name(_master_body(elems / "多成员组.gia")) == "多成员组")
    # 8c 缺陷根源取证：全部官方模板的名字组件恒为空（`3204 0801 5a00`）——模板直映路必须由我们的填名补齐
    import qxy.synth as _synth  # noqa: E402
    _tmpl = _synth.load_template(10008001)
    ok("名字组件/官方模板 cid1 名组件为空（320408015a00）— 缺陷根源",
       b"\x32\x04\x08\x01\x5a\x00" in _tmpl and element.read_body_name(_tmpl) == "")
    # 8d 后验守卫依据：读回 == 元件名才放行；改写即被读回捕获
    ok("名字组件/守卫依据：改后读回 != 原名（可被后验拦）",
       element.read_body_name(element.set_body_name(mb_master, "被别人改过")) == "被别人改过")
    # 8e 回归：set_body_name 幂等且不扰动其余字段（写回原值 → 字节复原）
    ok("名字组件/幂等且不扰动其余字段（set→set 复原字节）",
       element.set_body_name(element.set_body_name(mb_master, "X"), "最小元件_test1") == mb_master)

    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
