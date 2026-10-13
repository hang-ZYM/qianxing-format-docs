# -*- coding: utf-8 -*-
"""模块基础设施自测（CORE）。

运行：python -m mods.test_core（仓库根；mods.selftest 编排其一）
全部用哑模块与合成字节证明基础设施性质，不依赖任何游戏文件与工具树；
状态根经 QXYV2_ROOT 重定向到临时目录，零污染。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行

GATE = None  # 本模块纯 CORE，无 FULL 组（selftest.finish 用）


def main() -> int:
    from mods import selftest as st
    global GATE
    gate = st.FullGate()
    GATE = gate

    tmp = tempfile.mkdtemp(prefix="qxy_mods_core_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：自测不碰任何真实目录
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import config, core, state  # noqa: E402  env 先设，core 动态读根

    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS [CORE] {len(passes):02d}  {name}")

    # ---- 0. 路径抽象：状态根 / 游戏目录 / 工具树的解析律 ----
    os.environ.pop("QXY_GAME_SAVELEVEL", None)
    os.environ.pop("QXY_GAME_EXPORT", None)
    os.environ.pop("QXY_TOOL_ROOT", None)
    _saved_root = os.environ.pop("QXYV2_ROOT", None)  # 缺省值检查需无环境重定向
    _saved_up = os.environ.get("USERPROFILE")
    try:
        ok("状态根缺省=仓库 _state/", config.state_root() == config.REPO_ROOT / "_state")
        try:
            os.environ["USERPROFILE"] = str(tmp)  # 探测面指向空目录（无游戏，临时）
            ok("game_dir 无配置且探测不到 → None",
               config.game_dir("savelevel") is None and config.game_dir("export") is None)
            raised = None
            try:
                config.require_game_dir("export", purpose="测试")
            except core.PreconditionError as e:
                raised = str(e)
            ok("require_game_dir 未配置 → PreconditionError 含环境变量指引",
               raised is not None and "QXY_GAME_EXPORT" in raised)
        finally:
            if _saved_up is not None:
                os.environ["USERPROFILE"] = _saved_up  # 还原探测面
        raised2 = None
        try:
            config.require_tool_root("测试")
        except core.PreconditionError as e:
            raised2 = str(e)
        ok("require_tool_root 未配置 → PreconditionError 含 QXY_TOOL_ROOT 指引",
           raised2 is not None and "QXY_TOOL_ROOT" in raised2)
    finally:
        if _saved_root is not None:
            os.environ["QXYV2_ROOT"] = _saved_root
    ok("状态根参数优先于环境变量", str(config.state_root(override=tmp)) == tmp)
    os.environ["QXY_GAME_EXPORT"] = str(Path(tmp) / "gd")
    ok("game_dir 环境变量优先", config.game_dir("export") == Path(tmp) / "gd")
    os.environ.pop("QXY_GAME_EXPORT", None)
    os.environ["QXY_TOOL_ROOT"] = tmp
    ok("tool_root 环境变量生效", config.tool_root() == Path(tmp))
    os.environ.pop("QXY_TOOL_ROOT", None)

    # ---- 1. dummy.write：调用 → 日志有记录、版本 v1 产生 ----
    @core.module("dummy.write")
    def dummy_write(path: str, level: str, content: str) -> core.Result:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if not os.path.exists(path):  # 后验：文件存在
            raise core.ModuleRejected("文件未落盘")
        return core.Result(ok=True, artifact=path, level=level,
                           checks=[("file_exists", "PASS")])

    @core.module("dummy.bad")
    def dummy_bad(level: str) -> core.Result:
        raise core.ModuleRejected("后验必败（哑件）")

    lv = "selftest_lv"
    art = os.path.join(tmp, "artifact.txt")

    r = dummy_write(path=art, level=lv, content="hello v1")
    ok("dummy.write 返回 ok 且附 module", r.ok and r.module == "dummy.write")
    ok("Result 自动附 version/secs", r.version == 1 and r.secs >= 0)
    ok("v1 文件产生且字节守恒", core.read_current(lv) == "hello v1".encode("utf-8"))
    ok("current.json 指针=1", core.current_version(lv) == 1)
    e1 = core.read_oplog()[0]
    ok("oplog 有记录（seq1/kind/version）", e1["seq"] == 1 and e1["module"] == "dummy.write"
       and e1["ok"] is True and e1["version"] == 1 and e1["kind"] == "ok")
    ok("oplog 记录参数摘要", "artifact.txt" in e1["args"])
    ok("包装器自动加落盘守恒检查", ("commit_byte_equal", "PASS") in [tuple(c) for c in r.checks])

    # ---- 2. dummy.bad：ModuleRejected → 版本不变、日志记 REJECTED ----
    r2 = dummy_bad(level=lv)
    ok("拒绝返回 ok=False + REJECTED", (not r2.ok) and (r2.error or "").startswith("REJECTED"))
    ok("拒绝后版本不变（无 v2 产生）", core.current_version(lv) == 1
       and not core.version_path(lv, 2).exists())
    last = core.read_oplog()[-1]
    ok("日志记 REJECTED", last["kind"] == "rejected"
       and (last["error"] or "").startswith("REJECTED"))

    # ---- 3. 连续 4 次拒绝 → Voyager 律换路信号 ----
    core.reset_rejections()  # 清计数，从零起算
    seq_before = len(core.read_oplog())
    raised_on = None
    for i in range(4):
        try:
            dummy_bad(level=lv)
        except core.ConsecutiveRejectError as e:
            raised_on = i + 1
            ok("信号消息含『连续 4 次拒绝』", "连续 4 次拒绝" in str(e))
            break
    ok("第 4 次拒绝才抛信号", raised_on == 4)
    fresh = core.query_oplog(seq_from=seq_before + 1, module="dummy.bad")
    ok("4 次拒绝全部落日志", len(fresh) == 4 and all(not x["ok"] for x in fresh))

    # ---- 4. checkpoint + rollback 往返：v1→v2→回滚 v1 ----
    lv2 = "selftest_lv2"
    s1 = os.path.join(tmp, "s1.gil")
    s2 = os.path.join(tmp, "s2.gil")
    Path(s1).write_text("AAA", encoding="utf-8")
    Path(s2).write_text("BBB", encoding="utf-8")
    c1 = state.level_checkpoint(level_name=lv2, source_gil=s1)
    c2 = state.level_checkpoint(level_name=lv2, source_gil=s2)
    ok("checkpoint 连落 v1/v2", c1.version == 1 and c2.version == 2
       and core.current_version(lv2) == 2)
    ok("v2 字节=最新源", core.read_current(lv2) == b"BBB")
    rb = state.level_rollback(level_name=lv2, to_version=1)
    ok("rollback 回拨指针到 v1", rb.ok and core.current_version(lv2) == 1
       and core.read_current(lv2) == b"AAA")
    ptr = json.loads(core.current_path(lv2).read_text(encoding="utf-8"))
    ok("current.json 溯源 op_seq 更新", ptr["op_seq"] == core.read_oplog()[-1]["seq"])
    rb_bad = state.level_rollback(level_name=lv2, to_version=99)
    ok("回滚到不存在版 → PRECONDITION", (not rb_bad.ok)
       and (rb_bad.error or "").startswith("PRECONDITION"))

    # ---- 5. log.query 三种过滤各返回正确条目 ----
    by_mod = state.log_query(module="dummy.write")
    ok("过滤①按 module", len(by_mod.value) == 1
       and by_mod.value[0]["module"] == "dummy.write")
    by_seq = state.log_query(seq_from=seq_before + 1, seq_to=seq_before + 4)
    ok("过滤②按 seq 范围", len(by_seq.value) == 4
       and all(seq_before + 1 <= x["seq"] <= seq_before + 4 for x in by_seq.value))
    n_false = len([x for x in core.read_oplog() if x["ok"] is False])
    by_ok = state.log_query(ok=False)
    ok("过滤③按 ok=False", len(by_ok.value) == n_false
       and all(x["ok"] is False for x in by_ok.value))
    before_probe = len(core.read_oplog())
    state.log_query()  # readonly：自身不落日志
    ok("log.query 自身不落日志", len(core.read_oplog()) == before_probe)

    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
