# -*- coding: utf-8 -*-
"""P0.5 资产通道两模块：asset.package（实体→.gia 打包）+ asset.deploy（落导入目录）。

定位（任务分解架构设计书 §三.5 冷交通道）。设计书签名：
    asset.package(items, name) -> Result   # 实体/元件 → .gia 打包；后验=trial_gate（资产产线包装）
    asset.deploy(gia_path) -> Result       # 落 Beyond_Local_Export（同 level.deploy 模式）

本文件只编排不实现：合成/包装/门禁/搬运全部复用既有件（只读依赖，禁改）——
    P.entity / P.gia   ← 本机研究工具树 qxy/paradigm.py（V3 正典合成 + wrapper 包装 + 往返验证
                          + 资产通道元数据方言「四段尾横杠」+ 落盘）
    trial_gate          ← 本机研究工具树 qxy/trial_gate.py（L3 实体形态门禁：comp22 f7/f8/非升序
                          SICK 拦截、guid 撞号、版本门卫——f7 类事故出厂前拦，不到用户试玩）
工具树位置经 mods/config 解析（QXY_TOOL_ROOT）；开源仓库不附带工具树，缺配置时
相关调用如实抛 PreconditionError（见 mods/_toolchain）。

## asset.package
    items = 实体/元件描述。P0 最小支持形态：{aid, guid?, pos}（aid=官方 prefab id，
    guid=0x404 用户段实例 id〔省略则 P.alloc_guids 台账分配〕，pos=(x,z) 或 {x,z,y?}）。
    多元件/装饰物/染色/碰撞等复杂形态留 P1（entity.mount_decorator / showroom.admit）。
    执行：逐件 P.entity 合成 → P.gia 打包（channel='asset' 元数据方言）落 state/assets/。
    后验=trial_gate（优先 subprocess 调 `python -m qxy.trial_gate <file>` 与本机产线同形制；
    spawn 失败降级进程内 import 同一 gate 函数）。TRIAL_SICK → ModuleRejected 不入账。
    不落盘新版本：core 版本槽形制是 v<N>.gil，.gia 的版本归属未定案（P1 asset.register 遗留）——
    本模块只交 artifact + oplog 日志。

## asset.deploy
    把 .gia 复制到 Beyond_Local_Export（游戏导入点）。同 level.deploy 模式：
    字节一致后验（不一致删残件并 ModuleRejected——导入目录里的坏文件会被真人导入），
    重复部署=覆盖（无备份，重部署是常规流程），只搬不校验内容（形态门归 package 的
    trial_gate）。输出路径解析复用 mods/deploy.py：export_dir 参数 > QXY_GAME_EXPORT > 真实目录。

## 异常语义（core.py 三分支）
    PreconditionError（不计失败，换路）：源不存在 / items 非 P0 形态 / aid 无 prefab 模板 /
      name 非法 / 非法 pos / 部署源不是 .gia 后缀。
    ModuleRejected（后验不过，不入账 + 计连续拒绝）：源 0 字节 / 输出路径字节不一致 /
      trial_gate TRIAL_SICK。

## 自测
    mods/test_asset.py（全离线：状态根与输出路径经参数注入临时目录，零污染真实目录与台账）。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import _toolchain, core, deploy

_DEFAULT_MAP_ID = "1073742009"   # P.gia 元数据图号字段（资产通道方言组成部分，非目标图；
                                 #  paradigm 正典示例值。P1 asset.register 时定案归属）

_R_NAME_ILLEGAL = set(' /\\:*?"<>|')

# 工具树装载与 trial_gate 运行器：复用 _toolchain 的收敛入口（mods/config 的
# QXY_TOOL_ROOT 解析 + 缺配置 PreconditionError），与 mods/entity.py 同形。
_ensure_qxy = _toolchain.ensure_toolchain
run_trial_gate = _toolchain.run_trial_gate


# ---------------------------------------------------------------------------
# items 解析（P0 最小形态）
# ---------------------------------------------------------------------------

def _pos(item: dict, i: int) -> tuple[float, float, float | None]:
    p = item.get("pos", (0.0, 0.0))
    try:
        if isinstance(p, dict):
            x, z = float(p.get("x", 0.0)), float(p.get("z", 0.0))
            y = p.get("y")
            return x, z, (None if y is None else float(y))
        if isinstance(p, (list, tuple)) and 2 <= len(p) <= 3:
            x, z = float(p[0]), float(p[1])
            return x, z, (float(p[2]) if len(p) == 3 else None)
    except (TypeError, ValueError):
        pass
    raise core.PreconditionError(
        f"items[{i}].pos 须为 (x,z)/(x,z,y) 或 {{x,z,y?}}，得到: {p!r}")


def parse_items(items) -> list[dict]:
    """P0 最小形态解析：[{aid, guid?, pos?}, ...]（单件 dict 也收）。
    形态不合规 = PreconditionError（换路：调用方修正形态，不算产线失败）。"""
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, (list, tuple)) or not items:
        raise core.PreconditionError(
            f"items 须为非空 {{aid, guid?, pos}} 或其列表，得到: {type(items).__name__}")
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or "aid" not in it:
            raise core.PreconditionError(
                f"items[{i}] 非 P0 最小形态 {{aid, guid?, pos}}: {it!r}")
        aid = it["aid"]
        if not isinstance(aid, int) or isinstance(aid, bool) or aid <= 0:
            raise core.PreconditionError(f"items[{i}].aid 须为正整数，得到: {aid!r}")
        x, z, y = _pos(it, i)
        g = it.get("guid")
        if g is not None and (not isinstance(g, int) or isinstance(g, bool) or g <= 0):
            raise core.PreconditionError(f"items[{i}].guid 须为正整数，得到: {g!r}")
        out.append({"aid": aid, "guid": g, "x": x, "z": z, "y": y})
    return out


# ---------------------------------------------------------------------------
# 注册模块
# ---------------------------------------------------------------------------

@core.module("asset.package")
def asset_package(items, name: str, map_id: str = _DEFAULT_MAP_ID,
                  out_dir: str | None = None) -> core.Result:
    """实体描述 → .gia 资产包（资产产线包装），后验=trial_gate 形态门禁。

    参数：
        items   P0 最小形态：{aid, guid?, pos}（见模块 docstring；复杂形态留 P1）。
                guid 省略时经 P.alloc_guids 全档扫描分配（写工具树 guid_ledger.json 台账——
                分配即记台账是产线防撞号的既有机制；显式传 guid 则零台账写入）。
        name    包名（单段合法文件名，可含中文；.gia 后缀自动补）。
        map_id  元数据图号字段（资产通道方言「四段尾横杠」的组成部分，非目标图）。
        out_dir 落盘目录注入（自测零污染）；缺省=状态根 state/assets/（自己的领地，
                不碰 Beyond_Local_Export——导入目录只归 asset.deploy 写）。

    返回 Result：artifact=.gia 路径；value={path,count,guids,gate,}；checks 含
    trial_gate 结论。不落盘新版本（.gia 版本归属未定案，见模块 docstring 遗留）。
    """
    P, _ = _ensure_qxy()
    if not name or (set(name) & _R_NAME_ILLEGAL) or name.startswith("."):
        raise core.PreconditionError(f"name 须为单段合法文件名，得到: {name!r}")

    specs = parse_items(items)

    # aid 前置：须有官方 prefab 模板（synth 模板库=唯一合成真相；无模板换 aid 查库）
    for i, s in enumerate(specs):
        if P.synth.load_template(s["aid"]) is None:
            raise core.PreconditionError(
                f"items[{i}].aid {s['aid']} 无 prefab 模板（official_prefab_db）——"
                "先查正确资产 id 再调用")

    # guid：显式给定用之；缺省批量台账分配（避开已分配段与 0x414 关卡实体段）
    missing = [s for s in specs if not s["guid"]]
    if missing:
        got = P.alloc_guids(count=len(missing), note=f"asset.package:{name}")
        for s, g in zip(missing, got):
            s["guid"] = g

    # 执行：合成 + 打包（P.gia 内含往返验证 assert，失败即异常上抛=响亮失败）
    entities = [(s["guid"], P.entity(s["aid"], x=s["x"], z=s["z"], y=s["y"],
                                     guid=s["guid"])) for s in specs]
    dest_dir = Path(out_dir) if out_dir else core.state_dir() / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    r = P.gia(entities, map_id=str(map_id), name=name,
              out_dirs=[str(dest_dir)], channel="asset")
    pkg = Path(r["paths"][str(dest_dir)])

    # 后验：trial_gate（TRIAL_SICK → 拒绝不入账；WARN 如实透传不美化）
    verdict, gate_out = run_trial_gate(pkg)
    detail = next((ln.strip() for ln in gate_out.splitlines()
                   if "[SICK]" in ln or "[WARN]" in ln), "")
    checks = [
        ("item_form_p0", "PASS"),
        ("aid_has_template", "PASS"),
        ("gia_wrap_roundtrip", "PASS"),
        ("trial_gate", verdict),
    ]
    if detail:
        checks.append(("gate_detail", detail[:120]))
    if verdict != "TRIAL_PASS":
        sick = " | ".join(ln.strip() for ln in gate_out.splitlines() if "[SICK]" in ln)
        raise core.ModuleRejected(f"trial_gate 拦截: {sick or verdict}")
    return core.Result(ok=True, artifact=str(pkg), checks=checks, value={
        "path": str(pkg), "count": r["count"], "guids": [s["guid"] for s in specs],
        "gate": verdict,
    })


@core.module("asset.deploy")
def asset_deploy(gia_path: str, export_dir: str | None = None) -> core.Result:
    """把 .gia 资产包部署到游戏导入目录（Beyond_Local_Export），返回输出路径。

    同 level.deploy 模式：字节复制 → 输出路径存在+字节一致后验（不一致删残件并
    ModuleRejected——导入目录里的坏文件会被真人导入）；重复部署=覆盖（无备份，
    重部署是常规流程）；只搬不校验内容（L3 形态门归 asset.package 的 trial_gate）。
    前置：源存在（PreconditionError）；源非 .gia 后缀（PreconditionError，领地卫生：
    本模块只走资产通道）；源 0 字节视为坏产物（ModuleRejected，同 level.deploy 判定标准）。
    纯离线：自测经 export_dir 参数或 QXY_GAME_EXPORT 重定向，零污染真实导入目录。
    """
    src = Path(gia_path)
    if not src.is_file():
        raise core.PreconditionError(f"源 .gia 不存在: {gia_path}")
    if src.suffix != ".gia":
        raise core.PreconditionError(f"非 .gia 资产包（领地: .gia 通道）: {src.name}")
    if src.stat().st_size == 0:
        raise core.ModuleRejected("源 .gia 为空（0 字节），拒绝部署")

    dest = deploy.export_root(export_dir) / src.name
    if dest.is_dir():
        raise core.PreconditionError(f"输出路径已是目录: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    if not dest.is_file() or dest.read_bytes() != src.read_bytes():
        try:
            dest.unlink()  # 残件不留盘：导入目录里的坏文件会被真人导入
        except OSError:
            pass
        raise core.ModuleRejected(f"输出路径字节不一致（已尝试清除）: {dest}")
    return core.Result(ok=True, artifact=str(dest), checks=[
        ("dest_exists", "PASS"),
        ("byte_equal", "PASS"),
        ("deployed_to", str(dest)),
        ("bytes", str(dest.stat().st_size)),
    ])
