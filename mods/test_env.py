# -*- coding: utf-8 -*-
"""env.set 模块自测（FULL——需游戏目录真实样本；案例 #76）。

运行：python -m mods.test_env（仓库根；mods.selftest 编排其一）
环境前置：游戏目录 savelevel 下真实样本图 1073741954.gil（具名环境预设的来源）——
缺则整组 SKIP 如实报告（mods.selftest --full 模式下判失败）。底座用合成夹具挂载
产物（CORE 链：合成底座 + 合成宿主样本 + 最小图件，零游戏资产），无 f15 形态。
① 正例：临时域 m4（无 f15）→ set very_dark → ok + version=2 + 独立重读交叉核对
   （f15 新增/f6 追加/其余顶层字段逐字节不变/载荷逐字节==真实样本夜晚预设）；
② 正例：set extreme_dark → 载荷==真实样本黑色预设；读回 guid/类型码/名；
③ 负例：非法 preset → PRECONDITION（不计拒绝）；
④ 负例：无当前版本的域 → PRECONDITION。
状态根经 QXYV2_ROOT 重定向（版本/日志零污染真实 state/levels）；真实样本只读。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    # 环境面：真实样本图 1073741954.gil 在位（env 预设/直写底座的唯一来源）
    from mods import env
    g_ok = env._src_map_path() is not None
    if not gate.ready("env_full_sample", g_ok,
                      "游戏目录 savelevel 缺真实样本图 1073741954.gil"
                      "（QXY_GAME_SAVELEVEL / 默认探测，见 mods/config）"):
        print("SKIP [FULL] mods.test_env 整组（真实样本图未在位，见 mods/config）")
        return st.finish([], gate)

    tmp = tempfile.mkdtemp(prefix="qxy_mods_env_")
    os.environ["QXYV2_ROOT"] = tmp
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from fixtures import synth

    from mods import core, entity, env, level
    from qxfmt.container import Container
    from qxfmt.pbtree import parse, first, varint_value

    def _seed_mounted(level_name: str) -> bool:
        """用合成夹具 + 最小图件挂出一个关卡版本域（无 f15 形态），返回是否成功。"""
        fx = Path(tmp) / "fixtures" / level_name
        dft = (entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD)
        entity.assemble.DEFAULT_BASE = str(synth.write_base_gil(fx / "base.gil"))
        entity.assemble.DEFAULT_GOLD = str(synth.write_gold_like_gil(fx / "gold_like.gil"))
        gis = synth.write_min_gis(fx / "g.gis", 0x40000001, 20000, b"hello", b"hi")
        rm = level.level_mount(graph_gis=str(gis), host_guid=0x41400001,
                               graph_guid=0x40000001, category=20000, level_name=level_name)
        entity.assemble.DEFAULT_BASE, entity.assemble.DEFAULT_GOLD = dft
        return rm.ok

    # 播种临时域 m4：v1 = 合成夹具挂载产物（无 f15 的形态）
    assert _seed_mounted("m4"), "合成夹具挂载失败（m4 底座）"

    passes = []

    def ok(name, cond):
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS {len(passes):02d}  {name}")

    def gi(n, f):
        x = first(n, f)
        return varint_value(x) if (x and x[1] == 0) else None

    # 独立字节面（不走模块内部函数）
    def topfields(path):
        c = Container.load(str(path))
        nodes = parse(c.proto, strict=False)
        return {f: first(nodes, f)[2] for f, wt, _ in nodes}

    def env_entry(path):
        c = Container.load(str(path))
        f15 = first(parse(c.proto, strict=False), 15)
        e = parse(first(parse(f15[2], strict=False), 1)[2], strict=False)
        return e

    def payload_of(path):
        e = env_entry(path)
        for f, wt, body in e:
            if f == 4 and wt == 2:
                cn = parse(body, strict=False)
                if gi(cn, 1) == 70:
                    for cf, cwt, cb in cn:
                        if cf in (75, 80):
                            return cb
        return None

    base = topfields(core.version_path("m4", 1))

    # --- ① very_dark ---
    r = env.set_environment("m4", "very_dark")
    ok("very_dark ok", r.ok)
    ok("very_dark version=2", r.version == 2)
    out = core.version_path("m4", 2)
    ok("out exists", out.exists())
    after = topfields(out)
    ok("only f6/f15 changed",
       all(base[k] == after.get(k) for k in base if k not in (6, 15)) and
       set(after) - set(base) == {15})
    e = env_entry(out)
    ok("guid=0x46C00001", gi(e, 1) == env.ENV_GUID)
    ok("tc=26", gi(e, 2) == env.ENV_TC)
    ok("payload == 夜晚 preset",
       payload_of(out) == env._env_payload(env._extract_env_entry(0x46c00003)))
    ok("current=2", core.current_version("m4") == 2)
    ok("roundtrip", __import__('qxfmt.pbtree', fromlist=['roundtrip']).roundtrip(
        Container.load(str(out)).proto))

    # --- ② extreme_dark ---
    r2 = env.set_environment("m4", "extreme_dark")
    ok("extreme_dark ok", r2.ok)
    out3 = core.version_path("m4", 3)
    ok("payload == 黑色 preset",
       payload_of(out3) == env._env_payload(env._extract_env_entry(0x46c00005)))

    # --- ③ 非法 preset ---
    r3 = env.set_environment("m4", "nope")
    ok("bad preset -> precondition", (not r3.ok) and "PRECONDITION" in (r3.error or ""))

    # --- ④ 无当前版本 ---
    r4 = env.set_environment("empty", "very_dark")
    ok("no version -> precondition", (not r4.ok) and "PRECONDITION" in (r4.error or ""))

    # ================= env.direct 字段直写（2026-10-14 A/B/C 三档） =================
    # 底座：合成夹具挂载产物（无 f15 形态；_install_env 走"新建 f15"分支，与 set 同）
    assert _seed_mounted("m4d"), "合成夹具挂载失败（m4d 底座）"
    base_pl = env._env_payload(env._extract_env_entry(0x46c00003))   # 夜晚 preset 真实样本

    def cfg_map(payload):
        return {f: body for f, wt, body in env._cfg_of(payload)}

    def cfg_val(field, payload, kind="int"):
        cfg = env._cfg_of(payload)
        nd = first(cfg, field)
        n = first(parse(nd[2], strict=False), 2) if nd else None
        if n is None:
            return None
        if kind == "f32":
            import struct as _s
            return _s.unpack('<f', n[2])[0]
        return varint_value(n)

    A = dict(sun=0.0, moon=0.1, light_color=0xFF000000,
             sky=(0xFF000000,) * 4, ambient=(0xFF000000,) * 4, fog=0xFF000000)
    ra = env.direct_environment("m4d", "A_深黑", base="very_dark", **A)
    ok("direct A ok", ra.ok)
    outa = core.version_path("m4d", ra.version)
    pla = payload_of(outa)
    ok("A sun=0", abs(cfg_val(24, pla, "f32") - 0.0) < 1e-5)
    ok("A moon=0.1", abs(cfg_val(25, pla, "f32") - 0.1) < 1e-5)
    ok("A 受光色=0", cfg_val(26, pla) == 0xFF000000)
    ok("A 天空/环境全 0", all(cfg_val(f, pla) == 0xFF000000 for f in (30, 31, 32, 33, 34, 35, 36, 37)))
    ok("A 夜标记 on", first(env._cfg_of(pla), 16) is not None)
    # 最小扰动：动过的字段之外，其余 cfg 字段与真实样本底座逐字节一致
    _touched = {24, 25, 26, 30, 31, 32, 33, 34, 35, 36, 37, 47, 16}
    bm, om = cfg_map(base_pl), cfg_map(pla)
    ok("A 只动指定字段（其余字节不动）",
       all(bm[k] == om[k] for k in bm if k not in _touched) and set(bm) == set(om))

    B = dict(sun=0.0, moon=0.55)   # 颜色/关键帧全保持夜晚真实样本
    rb = env.direct_environment("m4d", "B_月夜", base="very_dark", **B)
    ok("direct B ok", rb.ok)
    plb = payload_of(core.version_path("m4d", rb.version))
    ok("B sun=0", abs(cfg_val(24, plb, "f32") - 0.0) < 1e-5)
    ok("B moon=0.55", abs(cfg_val(25, plb, "f32") - 0.55) < 1e-5)
    ok("B 受光色=夜晚真实样本", cfg_val(26, plb) == cfg_val(26, base_pl))
    ok("B 除日月亮度外与真实样本一致",
       all(cfg_map(base_pl)[k] == cfg_map(plb)[k] for k in cfg_map(base_pl) if k not in (24, 25)))

    C = dict(sun=0.4, moon=0.2, light_color=0xFFFFF0C3,
             sky=(0xFF3E3560, 0xFF2A2440, 0xFFD98A5A, 0xFF8A5F52),
             ambient=(0xFF9A84B8, 0xFF8A6470, 0xFF5E4A48, 0xFFFFF1C0),
             fog=0xFF7A6A72)
    rc = env.direct_environment("m4d", "C_黄昏", base="very_dark", **C)
    ok("direct C ok", rc.ok)
    plc = payload_of(core.version_path("m4d", rc.version))
    ok("C sun=0.4", abs(cfg_val(24, plc, "f32") - 0.4) < 1e-5)
    ok("C moon=0.2", abs(cfg_val(25, plc, "f32") - 0.2) < 1e-5)
    ok("C 受光色暖=0xFFFFF0C3", cfg_val(26, plc) == 0xFFFFF0C3)

    # 负例：sky 长度非法 / base 非法 → PRECONDITION
    r5 = env.direct_environment("m4d", "bad", base="very_dark", sky=(1, 2, 3))
    ok("direct bad sky -> precondition", (not r5.ok) and "PRECONDITION" in (r5.error or ""))
    r6 = env.direct_environment("m4d", "bad2", base="nope")
    ok("direct bad base -> precondition", (not r6.ok) and "PRECONDITION" in (r6.error or ""))

    # ============ 案例 #77：雾（f75.f1.f3 天气配置）+ 生效目标（f75.f1.f1 repeated f1） ============
    def f1_of_f75(payload):
        ap = parse(payload, strict=False)
        return parse(first(ap, 1)[2], strict=False)

    def weather_of(payload):
        w = first(f1_of_f75(payload), env.F_WEATHER)
        return w[2] if w is not None else None

    def targets_of(payload):
        return [n for n in env._cfg_of(payload) if n[0] == env.F_TARGETS]

    base_w = weather_of(base_pl)
    ok("底座无雾（f3=占位）", base_w == bytes.fromhex(env.WEATHER_OFF_HEX))
    ok("底座无生效目标", len(targets_of(base_pl)) == 0)

    AF = dict(A)
    rf = env.direct_environment("m4d", "A_深黑_雾", base="very_dark", **AF,
                                weather_fog=True, bind_targets=True)
    ok("direct A+fog ok", rf.ok)
    plf = payload_of(core.version_path("m4d", rf.version))
    ok("雾块写回读一致（逐字节==移植块）",
       weather_of(plf) == bytes.fromhex(env.WEATHER_FOG_HEX))
    ok("生效目标写回读一致（8 条 == 移植块）",
       len(targets_of(plf)) == 8 and
       __import__('qxfmt.pbtree', fromlist=['emit']).emit(targets_of(plf))
       == bytes.fromhex(env.TARGETS_HEX))
    ok("A+fog：夜色字段仍成立",
       cfg_val(26, plf) == 0xFF000000 and abs(cfg_val(25, plf, "f32") - 0.1) < 1e-5
       and first(env._cfg_of(plf), 16) is not None)
    # 关雾 / 去绑定 → 回到占位（开关可逆）
    rf0 = env.direct_environment("m4d", "A_深黑_无雾", base="very_dark",
                                 weather_fog=False, bind_targets=False)
    ok("direct off ok", rf0.ok)
    pl0 = payload_of(core.version_path("m4d", rf0.version))
    ok("关雾后 f3 回占位", weather_of(pl0) == bytes.fromhex(env.WEATHER_OFF_HEX))
    ok("去绑定后 f1 清空", len(targets_of(pl0)) == 0)
    ok("雾块长度=613B", len(env._fog_block()) == 613)

    # ---- 案例 #79：雾色（fog_color） ----
    def fog_colors_of(payload):
        w = weather_of(payload)
        s51 = parse(first(parse(first(parse(w, strict=False), 2)[2],
                                strict=False), 51)[2], strict=False)
        out = []
        for f in env.FOG_COLOR_FIELDS:
            grp = parse(first(s51, f)[2], strict=False)
            out.append(varint_value(first(grp, 2)))
        return out

    bb = env._fog_block()
    ok("雾色默认值=FF8394AA",
       fog_colors_of(env._direct_payload(base_pl, weather_fog=True)) == [0xFF8394AA] * 3)
    ok("雾色改色保持块长=613B", len(env._set_fog_color(bb, 0xFF2A3348)) == 613)
    ok("雾色默认值往返恒等", env._set_fog_color(bb, 0xFF8394AA) == bb)
    rfc = env.direct_environment("m4d", "A_深黑_蓝雾", base="very_dark", **A,
                                 weather_fog=True, bind_targets=True, fog_color=0xFF2A3348)
    ok("direct fog_color ok", rfc.ok)
    plc = payload_of(core.version_path("m4d", rfc.version))
    ok("雾色写回读一致（f15/16/20）", fog_colors_of(plc) == [0xFF2A3348] * 3)
    ok("改雾色不改块长（613B）", len(weather_of(plc)) == 613)

    # ---- 案例 #79：远雾点距离 f17（fog_far_dist） ----
    import struct as _st

    def f17_of(payload):
        s51 = parse(first(parse(first(parse(weather_of(payload), strict=False), 2)[2],
                                strict=False), 51)[2], strict=False)
        g = parse(first(s51, env.FOG_FAR_DIST)[2], strict=False)
        return _st.unpack('<f', first(g, 2)[2])[0]

    ok("默认 f17=2400", abs(f17_of(env._direct_payload(base_pl, weather_fog=True)) - 2400.0) < 1e-3)
    ok("f17 改值保持块长=613B", len(env._set_fog_scalar(bb, env.FOG_FAR_DIST, 200.0)) == 613)
    rfd = env.direct_environment("m4d", "A_深黑_雾距200", base="very_dark", **A,
                                 weather_fog=True, bind_targets=True, fog_far_dist=200.0)
    ok("direct fog_far_dist ok", rfd.ok)
    pld = payload_of(core.version_path("m4d", rfd.version))
    ok("f17 写回读一致=200", abs(f17_of(pld) - 200.0) < 1e-3)

    # ---- 案例 #81：浓度候选（fog_set 逐字段直写）+ 整段移植（fog_block_hex） ----
    def field_of(payload, fld):
        s51 = parse(first(parse(first(parse(weather_of(payload), strict=False), 2)[2],
                                strict=False), 51)[2], strict=False)
        nd = first(s51, fld)
        if nd is None:
            return None
        if nd[1] == 5:
            return _st.unpack('<f', nd[2])[0]
        if nd[1] == 2:
            bn = first(parse(nd[2], strict=False), 2)
            return _st.unpack('<f', bn[2])[0] if (bn is not None and bn[1] == 5) else None
        return None

    ok("fog_set f18 改值块长不变(613B)", len(env._set_fog_field(bb, 18, 0.5)) == 613)
    ok("fog_set f18 幂等（二次应用==一次）",
       env._set_fog_field(env._set_fog_field(bb, 18, 0.5), 18, 0.5)
       == env._set_fog_field(bb, 18, 0.5))
    r18 = env.direct_environment("m4d", "f18_05", base="very_dark", **A,
                                 weather_fog=True, bind_targets=True, fog_set={18: 0.5})
    ok("direct fog_set f18 ok", r18.ok)
    p18 = payload_of(core.version_path("m4d", r18.version))
    ok("f18 写回读=0.5", abs(field_of(p18, 18) - 0.5) < 1e-4)
    ok("fog_set f18 不动 f17", abs(f17_of(p18) - 2400.0) < 1e-3)
    ok("fog_set f21 补 base 块长 +5", len(env._set_fog_field(bb, 21, 50.0)) == 613 + 5)
    r21 = env.direct_environment("m4d", "f21_50", base="very_dark", **A,
                                 weather_fog=True, bind_targets=True, fog_set={21: 50.0})
    ok("direct fog_set f21 ok", r21.ok)
    p21 = payload_of(core.version_path("m4d", r21.version))
    ok("f21 写回读=50", abs(field_of(p21, 21) - 50.0) < 1e-4)
    ok("fog_block_hex 恒等移植", env._fog_block(fog_block_hex=bb.hex()) == bb)
    ok("fog_block_hex 移植后可改色块长不变",
       len(env._fog_block(fog_color=0xFF2A3348, fog_block_hex=bb.hex())) == len(bb))

    # ---- 案例 #81：整段移植 f75 载荷（base_payload_hex，收用户手调环境为正典） ----
    rraw = env.direct_environment("m4d", "raw", base="very_dark",
                                  base_payload_hex=base_pl.hex())
    ok("direct base_payload_hex ok", rraw.ok)
    praw = payload_of(core.version_path("m4d", rraw.version))
    ok("整段移植载荷逐字节一致", praw == base_pl)

    # 移植载荷 + 只换雾色（夜间雾色件路径）
    _wf = env._direct_payload(base_pl, weather_fog=True)
    rrawc = env.direct_environment("m4d", "rawc", base="very_dark",
                                   base_payload_hex=_wf.hex(), fog_color=0xFF16202E)
    ok("direct base_payload_hex+fog_color ok", rrawc.ok)
    prawc = payload_of(core.version_path("m4d", rrawc.version))
    ok("移植载荷只换雾色（其余不动）", prawc == env._payload_fog_color(_wf, 0xFF16202E))
    ok("换色后雾色读回=0xFF16202E",
       fog_colors_of(prawc) == [0xFF16202E] * 3)

    # ============ 案例 #83：时间推进（随时间自动切换 + 参数组时点表） ============
    import struct as _s2

    # --- _level_f11f1（关卡设置 f11.f1）---
    nf = parse(env._level_f11f1(5, None), strict=False)
    ok("f11f1 缺 f18（=0）", first(nf, 18) is None)
    i17 = first(nf, 17)
    ok("f11f1 f17=5", i17 is not None and i17[1] == 0 and varint_value(i17) == 5)
    nf2 = parse(env._level_f11f1(4, 10.0), strict=False)
    n18 = first(nf2, 18)
    ok("f11f1 f18=10.0", n18 is not None and n18[1] == 5
       and abs(_s2.unpack('<f', n18[2])[0] - 10.0) < 1e-6)
    ok("f11f1 生效范围 500³", all(_s2.unpack('<f', b)[0] == 500.0
                                 for _, wt, b in parse(first(nf, 1)[2], strict=False) if wt == 5))

    # --- _set_time_switch（cfg 顶层 f3）---
    tp = env._direct_payload(base_pl)
    ok("底座 cfg 无 f3（随时间关）", first(env._cfg_of(tp), 3) is None)
    tp2 = env._payload_apply_time(tp, True, None)
    ok("开随时间 → cfg.f3=1", first(env._cfg_of(tp2), 3) is not None)
    tp3 = env._payload_apply_time(tp2, False, None)
    ok("关随时间 → cfg.f3 缺", first(env._cfg_of(tp3), 3) is None)
    ok("开关可逆（关后字节==底座）", tp3 == tp)

    # --- _group_set_time（组 base + 时点表 + 组内 f1=1）---
    pts = [(0, 0, 0xFF000000), (2, 0, 0xFF000000), (5, 30, 0xFF8FA6C0), (23, 59, 0xFF000000)]
    tp4 = env._payload_apply_time(tp, True, {30: {"base": 0xFF8FA6C0, "pts": pts}})
    cfg4 = env._cfg_of(tp4)
    g30 = parse(first(cfg4, 30)[2], strict=False)
    ok("组内 f1=1（时间曲线生效位）",
       first(g30, 1) is not None and varint_value(first(g30, 1)) == 1)
    ok("组 base=0xFF8FA6C0", varint_value(first(g30, 2)) == 0xFF8FA6C0)
    kfs = [n for n in g30 if n[0] == 3]
    ok("时点表 4 帧", len(kfs) == 4)
    k0 = parse(kfs[0][2], strict=False)
    ok("首帧值=黑", varint_value(first(k0, 1)) == 0xFF000000)
    ok("首帧时间 0:00（分钟=0 → f2 空，官方规范形）",
       first(k0, 2) is not None and first(k0, 2)[2] == b'')
    t3rd = parse(first(parse(kfs[2][2], strict=False), 2)[2], strict=False)
    ok("第3帧时间 5:30", varint_value(first(t3rd, 1)) == 5
       and varint_value(first(t3rd, 2)) == 30)
    cmpb = {f: b for f, wt, b in env._cfg_of(tp)}
    cmpo = {f: b for f, wt, b in cfg4}
    ok("只动指定组 + 总开关（其余逐字节相同）",
       set(cmpo) - set(cmpb) == {3} and
       all(cmpb[k] == cmpo[k] for k in cmpb if k not in (3, 30)))
    ok("未指定组不加 f1（f26 仍静态）",
       first(parse(first(cfg4, 26)[2], strict=False), 1) is None)

    # 浮点组（自动探测 f32 线型）
    tp5 = env._payload_apply_time(tp, True, {24: {"base": 0.05, "pts": [(0, 0, 0.0), (6, 30, 0.3)]}})
    g24 = parse(first(env._cfg_of(tp5), 24)[2], strict=False)
    ok("f24 自动探测 f32 线型", first(g24, 2) is not None and first(g24, 2)[1] == 5
       and abs(_s2.unpack('<f', first(g24, 2)[2])[0] - 0.05) < 1e-6)

    # --- 未知组 → 响亮失败（ValueError，非静默）---
    try:
        env._payload_apply_time(tp, True, {99: {"base": 1, "pts": [(0, 0, 1)]}})
        ok("未知组应报错", False)
    except ValueError:
        ok("未知组 → ValueError", True)

    # --- direct_environment 端到端（含 f11）---
    rd = env.direct_environment("m4d", "time_static", base="very_dark",
                                base_payload_hex=base_pl.hex(), time_switch=True,
                                time_curve={30: {"base": 0xFF8FA6C0, "pts": pts}},
                                level_time=(5, None))
    ok("direct time_switch+curve+level_time ok", rd.ok)
    pldt = payload_of(core.version_path("m4d", rd.version))
    ok("direct: cfg.f3=1", first(env._cfg_of(pldt), 3) is not None)
    ok("direct: f30 时点表 4 帧",
       len([n for n in parse(first(env._cfg_of(pldt), 30)[2], strict=False) if n[0] == 3]) == 4)
    topd = topfields(core.version_path("m4d", rd.version))
    s11 = parse(first(parse(topd[11], strict=False), 1)[2], strict=False)
    ok("direct: f11.f1.f17=5", varint_value(first(s11, 17)) == 5)
    ok("direct: f11 缺 f18", first(s11, 18) is None)
    rd2 = env.direct_environment("m4d", "time_run", base="very_dark",
                                 base_payload_hex=base_pl.hex(), time_switch=True,
                                 time_curve={30: {"base": 0xFF8FA6C0, "pts": pts}},
                                 level_time=(4, 10.0))
    ok("direct time_run ok", rd2.ok)
    topd2 = topfields(core.version_path("m4d", rd2.version))
    s11b = parse(first(parse(topd2[11], strict=False), 1)[2], strict=False)
    ok("direct: f18=10.0", abs(_s2.unpack('<f', first(s11b, 18)[2])[0] - 10.0) < 1e-6)

    # ============ 案例 #84：M4「守到天亮」节奏曲线（前6轮黑 / 后两轮亮 / 5:30 后写平） ============
    T_N = [(0, 0), (2, 0), (4, 0), (5, 7)]      # 保持黑的锚点（含 5:07）
    T_D = [(5, 30), (23, 59)]                   # 天亮后写平

    def _pace(night, dawn):
        return {"base": night, "pts": [(h, m, night) for h, m in T_N]
                + [(h, m, dawn) for h, m in T_D]}

    pace = {24: _pace(0.0, 0.18), 25: _pace(0.30, 0.0), 32: _pace(0xFF000000, 0xFFEDEFF1)}
    tpp = env._payload_apply_time(tp, True, pace)
    ok("节奏: cfg.f3=1（随时间开）", first(env._cfg_of(tpp), 3) is not None)
    g32 = parse(first(env._cfg_of(tpp), 32)[2], strict=False)
    kfs32 = [parse(n[2], strict=False) for n in g32 if n[0] == 3]
    ok("节奏: 时点表 6 帧", len(kfs32) == 6)
    ok("节奏: 0:00 与 5:07 帧均为黑",
       all(varint_value(first(k, 1)) == 0xFF000000 for k in (kfs32[0], kfs32[3])))
    t3 = parse(first(kfs32[3], 2)[2], strict=False)
    ok("节奏: 第4帧时间 5:07",
       varint_value(first(t3, 1)) == 5 and varint_value(first(t3, 2)) == 7)
    ok("节奏: 5:30 与 23:59 帧同值（5:30 后写平）",
       first(kfs32[4], 1)[2] == first(kfs32[5], 1)[2])
    ok("节奏: 天亮帧=0xFFEDEFF1", varint_value(first(kfs32[4], 1)) == 0xFFEDEFF1)
    kfs24 = [parse(n[2], strict=False) for n in parse(first(env._cfg_of(tpp), 24)[2], strict=False) if n[0] == 3]
    ok("节奏: f24 天亮帧=0.18",
       abs(_s2.unpack('<f', first(kfs24[4], 1)[2])[0] - 0.18) < 1e-6)
    ok("节奏: 只动 3 组 + 总开关（其余逐字节相同）",
       all(cmpb[k] == {f: b for f, wt, b in env._cfg_of(tpp)}[k]
           for k in cmpb if k not in (3, 24, 25, 32)))

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
