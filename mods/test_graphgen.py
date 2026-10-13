# -*- coding: utf-8 -*-
"""graphgen.build 自测（CORE 前置负例 + FULL 正例构建）。

运行：python -m mods.test_graphgen（仓库根；mods.selftest 编排其一）
CORE（无工具树/无游戏目录）：
  IR 前置校验负例四种（kernel 出宇宙 / exec 边悬空 / text 超长 / guid 出 0x4000 段）
  → 各 PreconditionError、包装器转 PRECONDITION、不落版；log.query 记账可查。
  （无工具树时 kernel 宇宙退化已知集——负例两核均在已知集外/内，两种环境同过。）
FULL（工具树在位时）：
  正例：设计书竖线 hello 逻辑 → 构建 + 官方门禁四连全绿 + 关卡 v1 落盘；
  确定性：同逻辑同名二次构建，新版本字节与 v1 全同（.gis 内嵌图名，对照须同名）。
状态根经 QXYV2_ROOT 重定向到临时目录，零污染。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    tmp = tempfile.mkdtemp(prefix="qxy_mods_graphgen_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：自测零污染
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import core, state          # noqa: E402  env 先设
    from mods import graphgen             # noqa: E402
    from mods.graphgen import GraphLogic, Node, Exec  # noqa: E402

    passes: list[str] = []

    def ok(name: str, cond: bool, layer: str = "CORE") -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS [{layer}] {len(passes):02d}  {name}")

    assert 999999 not in graphgen.UNIVERSE, "自测假设失效: 999999 竟在 kernel 宇宙内"
    print(f"INFO kernel 宇宙来源: {graphgen.UNIVERSE_SOURCE}")
    print(f"INFO 标本库来源: {graphgen.BANK_SOURCE}")

    # ---- 1. CORE 负例 IR 校验：四种违规各抛 PreconditionError ----
    def expect_precondition(tag: str, logic, name: str, guid: int) -> None:
        raised = None
        try:
            graphgen.build.raw_fn(logic=logic, name=name, guid=guid)
        except core.PreconditionError as e:
            raised = str(e)
        ok(f"负例[{tag}] 模块函数抛 PreconditionError", raised is not None)
        print(f"        ↳ {raised}")
        rw = graphgen.build(logic=logic, name=name, guid=guid)
        ok(f"负例[{tag}] 包装器转 PRECONDITION Result(ok=False)",
           (not rw.ok) and (rw.error or "").startswith("PRECONDITION"))
        ok(f"负例[{tag}] 不落版（关卡仍 v0）", core.current_version(name) == 0)

    expect_precondition(
        "kernel 出宇宙", GraphLogic(nodes=[Node(1, kernel=999999)]),
        name="neg_kernel", guid=0x40000002)
    expect_precondition(
        "exec 边悬空", GraphLogic(nodes=[Node(1, kernel=71)], edges=[Exec(1, 3)]),
        name="neg_dangling", guid=0x40000002)
    expect_precondition(
        "text 超长", GraphLogic(nodes=[Node(1, kernel=1, text="印" * 1001)]),
        name="neg_text", guid=0x40000002)
    expect_precondition(
        "guid 出 0x4000 段", GraphLogic(nodes=[Node(1, kernel=71)]),
        name="neg_guid", guid=0x40800001)  # 0x408xxxxx=实体图波段，不归 graphgen.build

    # ---- 2. CORE 注册确认：log.query 能查到负例记账 ----
    q = state.log_query(module="graphgen.build")
    ok("log.query 查得到 graphgen.build", q.ok and len(q.value) >= 4)
    pre_entries = [e for e in q.value if e["kind"] == "precondition"]
    ok("4 条前置失败全部以 kind=precondition 记账（不计失败不计拒绝）",
       len(pre_entries) == 4
       and all((e["error"] or "").startswith("PRECONDITION") for e in pre_entries))

    # ---- 3. FULL 正例：工具树在位时构建 + 门禁四连 + 确定性 ----
    t_ok, t_reason = st.tool_ready()
    if gate.ready("graphgen_full_build", t_ok, t_reason):
        r1 = graphgen.build(logic=GraphLogic(
            nodes=[Node(1, kernel=71), Node(2, kernel=1, text="[hello_loop] 圈活了")],
            edges=[Exec(1, 2)]), name="hello", guid=0x40000001)
        ok("FULL build 返回 ok 且附 module 名", r1.ok and r1.module == "graphgen.build",
           layer="FULL")
        ok("FULL artifact 已落盘", r1.artifact is not None and Path(r1.artifact).exists(),
           layer="FULL")
        got = {c[0]: c[1] for c in r1.checks}
        for g in ("roundtrip", "verify", "form_gate", "oracle_gate"):
            ok(f"FULL 门禁四连之 {g} = PASS", got.get(g) == "PASS", layer="FULL")
        ok("FULL 前置自查 ir_validate = PASS", got.get("ir_validate") == "PASS",
           layer="FULL")
        ok("FULL 包装器自动附 commit_byte_equal = PASS",
           got.get("commit_byte_equal") == "PASS", layer="FULL")
        ok("FULL 关卡 hello 落 v1", r1.version == 1 and core.current_version("hello") == 1,
           layer="FULL")
        ok("FULL v1 字节 = 产物字节",
           core.read_current("hello") == Path(r1.artifact).read_bytes(), layer="FULL")

        # 确定性：同逻辑同名二次构建 → 新版本字节与 v1 全同
        #（.gis 内嵌图名，故确定性对照必须同名；图名不同的产物字节必然不同）
        r1b = graphgen.build(logic=GraphLogic(
            nodes=[Node(1, kernel=71), Node(2, kernel=1, text="[hello_loop] 圈活了")],
            edges=[Exec(1, 2)]), name="hello", guid=0x40000001)
        ok("FULL 同逻辑同名二次构建字节全同（确定性装配，v2==v1）",
           r1b.ok and r1b.version == 2
           and core.read_current("hello") == Path(core.version_path("hello", 1)).read_bytes(),
           layer="FULL")
        ok_entries = [e for e in state.log_query(module="graphgen.build").value
                      if e["kind"] == "ok"]
        ok("FULL 成功记录 checks 含四连 + 落盘守恒",
           set(["roundtrip", "verify", "form_gate", "oracle_gate", "commit_byte_equal"])
           <= {c[0] for c in ok_entries[0]["checks"]}, layer="FULL")

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
