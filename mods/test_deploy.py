# -*- coding: utf-8 -*-
"""level.deploy / level.judge 自测（CORE——全部离线可跑）。

运行：python -m mods.test_deploy（仓库根；mods.selftest 编排其一）
不依赖任何游戏文件与用户动作：状态根经 QXYV2_ROOT 重定向到临时目录，观察面经
mirror_dir / debug_dir / export_dir 参数注入临时目录，零污染真实游戏目录。
唯一并发件：端到端用例用后台线程延迟写入假 .gia，模拟"用户试玩后日志落盘"。

真实试玩判决（hello_loop_map_rN 全链路）不在本自测范围——导入与试玩是用户白名单
动作，标注"待用户白名单动作"。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行

EXPECT = "[hello_loop] 圈活了"


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()  # 本模块纯 CORE

    tmp = tempfile.mkdtemp(prefix="qxy_mods_deploy_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：oplog/levels 全落临时目录
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import core, deploy, state  # noqa: E402  env 先设，core 动态读根

    export = Path(tmp) / "export"
    mirror = Path(tmp) / "mirror"
    dbg = Path(tmp) / "dbg"
    for d in (export, mirror, dbg):
        d.mkdir(parents=True, exist_ok=True)

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS [CORE] {len(passes):02d}  {name}")

    def pairs(checks) -> list[tuple[str, str]]:
        return [tuple(c) for c in checks]

    # ==== 0. 路径前置：游戏目录未配置 → PRECONDITION（含指引，不猜路径落盘） ====
    _sv = {k: os.environ.pop(k, None) for k in
           ("QXY_GAME_EXPORT", "QXY_GAME_MIRROR", "QXY_GAME_DEBUGLOG")}
    _up = os.environ.get("USERPROFILE")
    src0 = Path(tmp) / "pre.gil"
    src0.write_bytes(b"\x0a\x04preload")  # 合法源（本节只验目录解析，不验源）
    try:
        os.environ["USERPROFILE"] = str(tmp)  # 探测面指向空目录（无游戏，临时）
        r_ng = deploy.level_deploy(level_gil=str(src0), r_name="x")
        ok("导入目录未配置 → PRECONDITION（不猜路径落盘）",
           (not r_ng.ok) and (r_ng.error or "").startswith("PRECONDITION")
           and "QXY_GAME_EXPORT" in (r_ng.error or ""))
        r_nj = deploy.level_judge(expect_print=EXPECT, timeout_min=0.05)
        ok("观察面未配置 → PRECONDITION（judge 不猜路径）",
           (not r_nj.ok) and (r_nj.error or "").startswith("PRECONDITION"))
    finally:
        for k, v in _sv.items():
            if v is not None:
                os.environ[k] = v
        if _up is not None:
            os.environ["USERPROFILE"] = _up

    # ==== 1. level.deploy 正例：临时关卡文件 → 落点出现且字节一致 ====
    src = Path(tmp) / "deploy_src.gil"
    payload = b"\x0a\x05hello" + bytes(range(256)) * 3
    src.write_bytes(payload)
    r = deploy.level_deploy(level_gil=str(src), r_name="hello_loop_map_r5",
                            export_dir=str(export))
    dest = export / "hello_loop_map_r5.gil"
    ok("deploy 返回 ok 且落点正确", r.ok and r.artifact == str(dest))
    ok("落点存在且字节一致", dest.is_file() and dest.read_bytes() == payload)
    ok("后验检查 byte_equal=PASS", ("byte_equal", "PASS") in pairs(r.checks))

    # 覆盖重部署（r5→同 r_name 新字节=常规改版流程）
    payload2 = payload + b"\x0a\x02v6"
    src.write_bytes(payload2)
    r1b = deploy.level_deploy(level_gil=str(src), r_name="hello_loop_map_r5",
                              export_dir=str(export))
    ok("重复部署=覆盖且字节更新", r1b.ok and dest.read_bytes() == payload2)

    # 环境变量重定向落点（QXY_GAME_EXPORT）
    os.environ["QXY_GAME_EXPORT"] = str(Path(tmp) / "env_export")
    try:
        r_env = deploy.level_deploy(level_gil=str(src), r_name="env_redirect_lv")
        ok("QXY_GAME_EXPORT 重定向生效",
           r_env.ok and r_env.artifact == str(Path(tmp) / "env_export" / "env_redirect_lv.gil"))
    finally:
        os.environ.pop("QXY_GAME_EXPORT", None)

    # deploy 负例：非法名/空源/缺源 → 前置与后验口径如实
    r_bad = deploy.level_deploy(level_gil=str(src), r_name="../evil", export_dir=str(export))
    ok("非法 r_name → PRECONDITION 不计失败",
       (not r_bad.ok) and (r_bad.error or "").startswith("PRECONDITION"))
    empty = Path(tmp) / "empty.gil"
    empty.write_bytes(b"")
    r_empty = deploy.level_deploy(level_gil=str(empty), r_name="x", export_dir=str(export))
    ok("空源 → REJECTED", (not r_empty.ok) and (r_empty.error or "").startswith("REJECTED"))
    r_miss = deploy.level_deploy(level_gil=str(Path(tmp) / "nope.gil"),
                                 r_name="x", export_dir=str(export))
    ok("缺源 → PRECONDITION", (not r_miss.ok)
       and (r_miss.error or "").startswith("PRECONDITION"))
    dep_entries = [e for e in core.read_oplog() if e["module"] == "level.deploy"]
    dep_kinds = {e["kind"] for e in dep_entries}
    ok("oplog 记账三态（ok/precondition/rejected）",
       {"ok", "precondition", "rejected"} <= dep_kinds)

    # ==== 2. judge 相3 单测：假 .gia 含判据 → passed=True 且证据正确 ====
    unit = Path(tmp) / "unit.gia"
    unit.write_bytes(b"\x00\x01lua_ctx_pad\x00" + EXPECT.encode("utf-8")
                     + b"\x00tail_pad")
    v = deploy.verdict_from_log(EXPECT, [unit], map_id="1073743000")
    ok("相3 正例：passed=True", v.passed is True)
    ok("相3 证据窗含判据", EXPECT in v.evidence and v.map_id == "1073743000")
    v_neg = deploy.verdict_from_log("绝不存在的判据XYZ", [unit])
    ok("相3 负例：如实 print_not_found",
       v_neg.passed is False and v_neg.reason == "print_not_found")

    # ==== 3. judge 端到端离线（相1+2+3）：假地图先行，.gia 由后台线程延迟落盘 ====
    fake_map = mirror / "1073742999"
    fake_map.mkdir(parents=True, exist_ok=True)
    (fake_map / "1073742999.gil").write_bytes(b"\x0a\x04fake")  # 垃圾字节→解剖如实降级
    gia_content = b"\x00\x02graph_exec" + EXPECT.encode("utf-8") + b"\x00\x03end"

    def late_write() -> None:
        time.sleep(1.2)
        (dbg / "2026-10-13_18-00-00_999_fixture.gia").write_bytes(gia_content)

    threading.Thread(target=late_write, daemon=True).start()
    t0 = time.time()
    r_j = deploy.level_judge(expect_print=EXPECT, timeout_min=0.15,
                             known_maps=set(),  # 空基线：预先放好的假地图按新图计
                             mirror_dir=str(mirror), debug_dir=str(dbg),
                             poll_sec=0.2)
    el = time.time() - t0
    v_j = r_j.value
    ok("端到端：观察器完成 ok=True 且判决 passed=True",
       r_j.ok and v_j.passed is True)
    ok("端到端：map_id 来自相1", v_j.map_id == "1073742999")
    ok("端到端：证据与日志文件正确",
       EXPECT in v_j.evidence and v_j.log_file.endswith(".gia"))
    ok("端到端：解剖降级不阻塞判决（struct 如实）",
       isinstance(v_j.struct, dict) and v_j.struct.get("ok") is False)
    ok("端到端：checks 全程记账",
       ("phase1_new_map", "PASS") in pairs(r_j.checks)
       and ("phase2_new_gia", "PASS") in pairs(r_j.checks)
       and ("verdict", "PASS") in pairs(r_j.checks))
    ok("端到端：及时返回不挂死", el < 8.0)

    # level_name 溯源：判决记入关卡域指针（版本不动）
    r_lv = deploy.level_judge(expect_print=EXPECT, timeout_min=0.05,
                              known_maps=set(), mirror_dir=str(mirror),
                              debug_dir=str(dbg), poll_sec=0.2,
                              level_name="selftest_judge_lv")
    ok("level_name 溯源：指针产生且版本不动",
       r_lv.ok and core.current_path("selftest_judge_lv").exists()
       and core.current_version("selftest_judge_lv") == 0)

    # ==== 4. judge 负例：无新图短窗超时 → 如实失败，不抛异常不挂死 ====
    empty_m = Path(tmp) / "empty_mirror"
    empty_d = Path(tmp) / "empty_dbg"
    empty_m.mkdir(parents=True, exist_ok=True)
    empty_d.mkdir(parents=True, exist_ok=True)
    t1 = time.time()
    r_to = deploy.level_judge(expect_print=EXPECT, timeout_min=0.05,
                              mirror_dir=str(empty_m), debug_dir=str(empty_d),
                              poll_sec=0.2)
    el_to = time.time() - t1
    v_to = r_to.value
    ok("超时负例：不抛异常且 ok=观察完成",
       r_to.ok is True and isinstance(v_to, deploy.Verdict))
    ok("超时负例：passed=False 且 reason 如实",
       v_to.passed is False and v_to.reason == "timeout_no_new_map")
    ok("超时负例：checks 记 verdict=FAIL",
       ("verdict", "FAIL") in pairs(r_to.checks)
       and ("phase1_new_map", "FAIL") in pairs(r_to.checks))
    ok("超时负例：短窗即返不挂死", 2.0 <= el_to < 20.0)

    # ==== 5. 注册确认：log.query 可查两模块 ====
    names = core.list_modules()
    ok("registry 含 level.deploy 与 level.judge",
       "level.deploy" in names and "level.judge" in names)
    dep_rows = state.log_query(module="level.deploy")
    ok("log.query 可查 level.deploy（含 ok 与账目）",
       len(dep_rows.value) >= 4 and any(x["ok"] for x in dep_rows.value))
    jd_rows = state.log_query(module="level.judge")
    ok("log.query 可查 level.judge（端到端+负例+溯源）", len(jd_rows.value) >= 3)
    ok("判决 checks 落日志（verdict 可审计）",
       any(("verdict", "PASS") in [tuple(c) for c in x["checks"]] for x in jd_rows.value))
    n0 = len(core.read_oplog())
    state.log_query()
    ok("log.query 自身不落日志", len(core.read_oplog()) == n0)

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
