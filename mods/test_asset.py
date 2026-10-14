# -*- coding: utf-8 -*-
"""asset.package / asset.deploy 自测（FULL——需工具树；P0.5）。

运行：python -m mods.test_asset（仓库根；mods.selftest 编排其一）
环境前置：QXY_TOOL_ROOT（合成模板库 + trial_gate，见 mods/config）——缺则整组
SKIP 如实报告（mods.selftest --full 模式下判失败）。
状态根经 QXYV2_ROOT 重定向到临时目录，包落盘与部署输出路径经 out_dir / export_dir 参数
注入临时目录——零污染真实 state/ 与真实导入目录。guid 分配路径经 monkeypatch 把
台账重定向到临时文件（分配即记台账是产线防撞号的既有机制，生产常态）。
trial_gate 走真实产线（subprocess python -m qxy.trial_gate，cwd=工具树根）——
门禁本身不在本自测的替换范围，它是被验对象的一部分。

在线/游戏侧验收（真实导入+试玩）不在本自测范围——导入与试玩是用户白名单动作。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许从任意 cwd 运行

AID = 20002889          # 石质立柱（official_prefab_db 在册，synth 有模板）
GUID = 0x40460001       # 0x404 用户段（避开 0x414 关卡实体段）


def main() -> int:
    from mods import selftest as st
    gate = st.FullGate()

    t_ok, t_reason = st.tool_ready()
    if not gate.ready("asset_full_package", t_ok, t_reason):
        print("SKIP [FULL] mods.test_asset 整组（工具树未配置，见 mods/config）")
        return st.finish([], gate)

    tmp = tempfile.mkdtemp(prefix="qxy_mods_asset_")
    os.environ["QXYV2_ROOT"] = tmp  # 状态根重定向：state/assets、oplog 全落临时目录
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from mods import asset, core, state  # noqa: E402  env 先设，core 动态读根

    # 台账重定向（alloc_guids 分配即记台账是产线机制；自测不污染真实台账）
    P, _ = asset._ensure_qxy()
    P._LEDGER = str(Path(tmp) / "guid_ledger.json")

    export = Path(tmp) / "export"
    export.mkdir(parents=True, exist_ok=True)
    passes: list[str] = []

    def ok(name: str, cond: bool) -> None:
        assert cond, f"断言失败: {name}"
        passes.append(name)
        print(f"PASS {len(passes):02d}  {name}")

    def pairs(checks) -> list[tuple[str, str]]:
        return [tuple(c) for c in checks]

    # ==== 1. asset.package 正例：最小单实体 → 打包 → trial_gate PASS ====
    pkg_dir = Path(tmp) / "assets"
    r = asset.asset_package(items=[{"aid": AID, "guid": GUID, "pos": (0.0, -20.0)}],
                            name="probe_pillar", out_dir=str(pkg_dir))
    pkg = pkg_dir / "probe_pillar.gia"
    ok("package 返回 ok 且产物在注入目录", r.ok and r.artifact == str(pkg))
    ok("产物存在且非空", pkg.is_file() and pkg.stat().st_size > 0)
    ok("后验 trial_gate=TRIAL_PASS", ("trial_gate", "TRIAL_PASS") in pairs(r.checks))
    ok("value 载荷含 count/guids",
       r.value["count"] == 1 and r.value["guids"] == [GUID])
    ok("P0 形态门与合成门记账", ("item_form_p0", "PASS") in pairs(r.checks)
       and ("aid_has_template", "PASS") in pairs(r.checks))

    # 打包字节再包一次（同 guid 重复打包=同名覆盖，幂等产物）
    r1b = asset.asset_package(items={"aid": AID, "guid": GUID, "pos": {"x": 0.0, "z": -20.0}},
                              name="probe_pillar", out_dir=str(pkg_dir))
    ok("dict 单件形态与 pos{x,z} 形态同路", r1b.ok and r1b.value["count"] == 1)

    # guid 省略 → alloc_guids 台账分配路径（台账经 monkeypatch 重定向到临时文件；此处只验证可走通）
    r_alloc = asset.asset_package(items=[{"aid": AID, "pos": (5.0, 5.0)}],
                                  name="probe_alloc", out_dir=str(pkg_dir))
    ok("guid 省略 → 台账分配且 0x404 段",
       r_alloc.ok and 0x40400000 <= r_alloc.value["guids"][0] < 0x41400000)

    # ==== 2. asset.package 负例：坏 aid / 坏形态 / 坏名 → PRECONDITION 换路 ====
    r_bad = asset.asset_package(items=[{"aid": 999999999, "guid": GUID, "pos": (0, 0)}],
                                name="probe_bad_aid", out_dir=str(pkg_dir))
    ok("坏 aid（无 prefab 模板）→ PRECONDITION",
       (not r_bad.ok) and (r_bad.error or "").startswith("PRECONDITION"))
    r_form = asset.asset_package(items=[{"guid": GUID, "pos": (0, 0)}],
                                 name="probe_no_aid", out_dir=str(pkg_dir))
    ok("缺 aid 形态 → PRECONDITION",
       (not r_form.ok) and (r_form.error or "").startswith("PRECONDITION"))
    r_pos = asset.asset_package(items=[{"aid": AID, "guid": GUID, "pos": "北偏东"}],
                                name="probe_bad_pos", out_dir=str(pkg_dir))
    ok("非法 pos → PRECONDITION",
       (not r_pos.ok) and (r_pos.error or "").startswith("PRECONDITION"))
    r_nm = asset.asset_package(items=[{"aid": AID, "guid": GUID}],
                               name="../evil", out_dir=str(pkg_dir))
    ok("非法 name → PRECONDITION",
       (not r_nm.ok) and (r_nm.error or "").startswith("PRECONDITION"))

    # oplog 三态记账（ok + precondition；拒绝态见 deploy 段）
    pk_entries = [e for e in core.read_oplog() if e["module"] == "asset.package"]
    ok("package oplog 记账（ok/precondition 两态在账）",
       {"ok", "precondition"} <= {e["kind"] for e in pk_entries})

    # ==== 3. asset.deploy 正例：字节一致输出路径 + 覆盖重部署 ====
    r_d = asset.asset_deploy(gia_path=str(pkg), export_dir=str(export))
    dest = export / "probe_pillar.gia"
    ok("deploy 返回 ok 且输出路径正确", r_d.ok and r_d.artifact == str(dest))
    ok("输出路径字节与源一致", dest.is_file() and dest.read_bytes() == pkg.read_bytes())
    ok("后验 byte_equal=PASS", ("byte_equal", "PASS") in pairs(r_d.checks))

    pkg.write_bytes(pkg.read_bytes() + b"\x1a\x02v2")  # 改版重部署（常规流程）
    r_d2 = asset.asset_deploy(gia_path=str(pkg), export_dir=str(export))
    ok("重复部署=覆盖且字节更新", r_d2.ok and dest.read_bytes() == pkg.read_bytes())

    # 环境变量重定向输出路径（QXY_GAME_EXPORT，与 level.deploy 同一解析面）
    os.environ["QXY_GAME_EXPORT"] = str(Path(tmp) / "env_export")
    try:
        r_env = asset.asset_deploy(gia_path=str(pkg))
        ok("QXY_GAME_EXPORT 重定向生效",
           r_env.ok and r_env.artifact == str(Path(tmp) / "env_export" / "probe_pillar.gia"))
    finally:
        os.environ.pop("QXY_GAME_EXPORT", None)

    # ==== 4. asset.deploy 负例：缺源/非 .gia/空源 → 前置与拒绝判定标准如实 ====
    r_miss = asset.asset_deploy(gia_path=str(Path(tmp) / "nope.gia"), export_dir=str(export))
    ok("缺源 → PRECONDITION", (not r_miss.ok)
       and (r_miss.error or "").startswith("PRECONDITION"))
    notgia = Path(tmp) / "not_gia.gil"
    notgia.write_bytes(b"\x0a\x04fake")
    r_suf = asset.asset_deploy(gia_path=str(notgia), export_dir=str(export))
    ok("非 .gia 后缀 → PRECONDITION（领地卫生）",
       (not r_suf.ok) and (r_suf.error or "").startswith("PRECONDITION"))
    empty = Path(tmp) / "empty.gia"
    empty.write_bytes(b"")
    r_empty = asset.asset_deploy(gia_path=str(empty), export_dir=str(export))
    ok("空源 → REJECTED", (not r_empty.ok)
       and (r_empty.error or "").startswith("REJECTED"))
    dp_entries = [e for e in core.read_oplog() if e["module"] == "asset.deploy"]
    ok("deploy oplog 记账三态（ok/precondition/rejected）",
       {"ok", "precondition", "rejected"} <= {e["kind"] for e in dp_entries})

    # ==== 5. 注册确认：log.query 可查两模块 ====
    names = core.list_modules()
    ok("registry 含 asset.package 与 asset.deploy",
       "asset.package" in names and "asset.deploy" in names)
    pk_rows = state.log_query(module="asset.package")
    ok("log.query 可查 asset.package", len(pk_rows.value) >= 5)
    dp_rows = state.log_query(module="asset.deploy")
    ok("log.query 可查 asset.deploy", len(dp_rows.value) >= 5)
    ok("trial_gate 结论落日志可审计",
       any(("trial_gate", "TRIAL_PASS") in [tuple(c) for c in x["checks"]]
           for x in pk_rows.value))

    shutil.rmtree(tmp, ignore_errors=True)
    return st.finish(passes, gate)


if __name__ == "__main__":
    raise SystemExit(main())
