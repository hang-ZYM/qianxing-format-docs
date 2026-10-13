# -*- coding: utf-8 -*-
"""level.deploy（关卡部署到导入目录）+ level.judge（试玩观察判决）。

定位（docs/30）：设计书把两者合称「部署+判决」组合形态——实现拆成两个注册
单元，编排器两连调即得（v = deploy 然后 judge）。
本文件只注册 level.deploy 与 level.judge；level.mount 由 mods/level.py 另行注册。

## level.deploy（纯离线，完全可自测）
    执行：把 level_gil 的字节复制到游戏导入目录，命名 <r_name>.gil
    （如 hello_loop_map_r5.gil）；返回落点（Result.artifact）。
    后验：落点存在 + 字节一致；不一致即删残件并 ModuleRejected——导入目录里的坏文件
    会被真人导入，残件不留盘。
    领地：只写导入目录；不校验 gil 内容（L1 字节门归产物模块，deploy 只管忠实搬运）。

## level.judge（三相阻塞观察器）
    相1 导入观察：轮询导入镜像目录等新地图。known_maps=基线
        （None=调用时刻镜像快照；传入集合则按它算基线）。目录式 <id>/<id>.gil 与
        平铺 <id>.gil 两种落盘形态都认（实测镜像里两者并存）。新图出现后解剖：
        f10 图在位 / f7 保留 / 挂载 / f6 叶（结构判据=诊断证据，不是判决门）。
    相2 等待调试日志：轮询调试日志目录，等比基线新的 .gia（新文件名或 mtime 更新）。
    相3 判决：在新 .gia 的字节流中找 expect_print 的 UTF-8 字节（.gia 是含内嵌文本的
        二进制日志，故按字节搜；文件可能仍在增长，轮询重读）。找到 → Verdict(passed=True)。
    阻塞语义：同步 sleep 轮询；timeout_min 是三相总预算，超时如实返回
    Verdict(passed=False, reason=...)。

## 前置（依赖用户白名单动作，模块只能等、不能代做）
    - 相1 前置：用户在游戏内点「导入」<r_name>.gil——白名单动作。judge 必须在用户
      导入之前启动，导入先于基线快照会被当成旧图而白等超时。
    - 相2/3 前置：.gia 只在「编辑器内试玩 + 日志两层门开」时产生，游戏内
      直接试玩不产生 .gia。门没开/没试玩 → 模块只会如实超时（reason 里写明），不冒充。
    - 模块不做假判决：passed=True 当且仅当 expect_print 的字节确实出现在新 .gia 中；
      解剖失败/结构异常只进 evidence（struct），不参与 passed 判定，也绝不反向冒充。

## 返回语义
    Result.ok = 观察器是否完整跑完（观察完成恒 True）；判决真值在 Result.value.passed
    （Verdict 对象：passed/evidence/map_id/reason/log_file/struct）。checks 同步落
    ("verdict","PASS"/"FAIL") 等条目供 log.query 审计。
    不用 ok=False 表达判决失败，原因有二：core 包装器对自评失败会丢弃 value（判决证据
    要靠 value 回流编排器）；设计要求超时也返回 Verdict（判决败→数据回流→修复序列）。
    代价：判决失败不计入 Voyager 连续拒绝计数，编排器须读 value.passed 自行触发修复。

## 游戏目录（路径抽象，见 mods/config）
    解析优先级：调用参数 > 环境变量（QXY_GAME_EXPORT / QXY_GAME_MIRROR /
    QXY_GAME_DEBUGLOG）> 常见默认路径探测。全部未命中 → PreconditionError 并附
    配置指引（部署/判决没有可写的领地时理应拒绝，绝不猜路径落盘）。
    自测经参数注入临时目录，零污染真实游戏目录（CORE）。
"""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import config, core

_R_NAME_ILLEGAL = set(' /\\:*?"<>|')


# ---------------------------------------------------------------------------
# 游戏侧路径解析（收敛到 mods/config；此处只保留模块语义命名）
# ---------------------------------------------------------------------------

def export_root(override: str | None = None) -> Path:
    """导入目录：关卡部署的落点（用户在游戏内点「导入」的扫描面）。"""
    return config.require_game_dir("export", override, purpose="level.deploy 落点")


def mirror_root(override: str | None = None) -> Path:
    """导入镜像目录：judge 相1 的观察面（新导入的地图在此出现）。"""
    return config.require_game_dir("mirror", override, purpose="level.judge 相1 观察面")


def debug_root(override: str | None = None) -> Path:
    """调试日志目录：judge 相2/3 的观察面（试玩产生的 .gia 在此出现）。"""
    return config.require_game_dir("debuglog", override, purpose="level.judge 相2/3 观察面")


# ---------------------------------------------------------------------------
# Verdict 与观察原语（level.judge 与单测共用）
# ---------------------------------------------------------------------------

@dataclass
class Verdict:
    """L5 试玩判决。passed=True 当且仅当 expect_print 确实出现在新 .gia 中。"""
    passed: bool
    evidence: str = ""            # 命中处的可读上下文窗（控制字符以 · 代）
    map_id: str | None = None     # 相1 观察到的新地图 id
    reason: str | None = None     # passed=False 时的如实原因：
                                  #   timeout_no_new_map / timeout_no_new_debug_log /
                                  #   print_not_found
    log_file: str | None = None   # 命中（或最后观察的）.gia 路径
    struct: dict = field(default_factory=dict)  # 相1 解剖明细（诊断证据，非判决门）
    expect_print: str = ""


def mirror_snapshot(mirror) -> dict[str, tuple[str, float]]:
    """镜像目录快照 {地图id: (gil路径, mtime)}。兼容两种落盘形态：
    目录式 <id>/<id>.gil 与平铺 <id>.gil。读不到（权限/瞬时消失）的条目跳过。"""
    root = Path(mirror)
    out: dict[str, tuple[str, float]] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.iterdir()):
        gil: Path | None = None
        try:
            if p.is_dir():
                cand = p / (p.name + ".gil")
                if cand.is_file():
                    gil = cand
            elif p.is_file() and p.suffix == ".gil":
                gil = p
            if gil is not None:
                out[p.name] = (str(gil), gil.stat().st_mtime)
        except OSError:
            continue
    return out


def debug_snapshot(dbg) -> dict[str, float]:
    """调试日志目录快照 {文件名: mtime}（只认根目录平铺 .gia——当前实测形态）。"""
    root = Path(dbg)
    out: dict[str, float] = {}
    if not root.is_dir():
        return out
    for p in root.iterdir():
        try:
            if p.is_file() and p.suffix == ".gia":
                out[p.name] = p.stat().st_mtime
        except OSError:
            continue
    return out


def _viv(b) -> int:
    v = 0
    for i, x in enumerate(b):
        v |= (x & 0x7F) << (7 * i)
        if not x & 0x80:
            break
    return v


def _enc_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b7 = n & 0x7F
        n >>= 7
        out.append(b7 | (0x80 if n else 0))
        if not n:
            return bytes(out)


def dissect(gil_path, graph_name: str = "hello", graph_guid: int = 0x40000001,
            host_guid: int = 0x41400001) -> dict:
    """导入层解剖：f10 图在位 / f7 保留 / 挂载 / f6 叶。

    返回 {"doc","f7","mount","leaf","ok"}；ok = 三条结构判据全绿。
    qxfmt 不可用或字节异常时如实降级 {"error":…, "ok":False}——不阻塞相2/3，
    判决以运行层打印为准（struct 只是诊断证据）。
    """
    out = {"doc": "未解剖", "f7": "未解剖", "mount": "未解剖", "leaf": False, "ok": False}
    try:
        from qxfmt.container import Container
        from qxfmt.pbtree import parse
    except Exception as e:  # ImportError 及其环境变体——如实降级
        out["error"] = f"qxfmt 不可用: {type(e).__name__}"
        return out
    try:
        gname = graph_name.encode("utf-8")
        t = parse(Container.load(gil_path).proto)
        doc_desc, f7_desc = "无", "无"
        for f in t:
            if not (isinstance(f, list) and f[0] == 10):
                continue
            try:
                env = parse(f[2])
                inner = parse(parse(env[0][2])[0][2])
                name = next((x[2] for x in inner if isinstance(x, list) and x[0] == 2), b"")
                if name != gname:
                    continue
                nodes = len([x for x in inner if isinstance(x, list) and x[0] == 3])
                f7 = next((x for x in env if isinstance(x, list) and x[0] == 7), None)
                f7_desc = "无" if f7 is None else f"wt{f7[1]}={f7[2].hex()}"
                doc_desc = f"图'{graph_name}'在位 {nodes}节点"
            except Exception:
                continue

        mount_desc, leaf_ok = "无宿主/无挂载", False
        f5 = next((x for x in t if isinstance(x, list) and x[0] == 5), None)
        if f5 is not None:
            for e in parse(f5[2]):
                if not (isinstance(e, list) and e[0] == 1):
                    continue
                tree = parse(e[2])
                g = next((_viv(x[2]) for x in tree
                          if isinstance(x, list) and x[0] == 1 and x[1] == 0), None)
                if g != host_guid:
                    continue
                mounts = []
                for x in tree:
                    if isinstance(x, list) and x[0] == 6:
                        for m in parse(x[2]):
                            # 挂载条目载荷形如 …10 <guid varint>…，从 0x10 标记后解 varint
                            if isinstance(m, list) and m[0] == 13 and m[2]:
                                j = m[2].find(b"\x10")
                                if j >= 0:
                                    mounts.append(_viv(m[2][j + 1:]))
                if mounts:
                    mount_desc = f"实体0x{host_guid:x}挂载→{[hex(m) for m in mounts]}"
        f6 = next((x for x in t if isinstance(x, list) and x[0] == 6), None)
        if f6 is not None:
            leaf_ok = _enc_varint(graph_guid) in f6[2]
        out.update(doc=doc_desc, f7=f7_desc, mount=mount_desc, leaf=leaf_ok)
        out["ok"] = (graph_name in doc_desc and f7_desc.startswith("wt")
                     and hex(graph_guid) in mount_desc and leaf_ok)
    except Exception as e:
        out["error"] = f"解剖异常 {type(e).__name__}: {e}"
    return out


def find_print(path, needle: bytes, ctx: int = 120) -> str | None:
    """在单个 .gia 字节流中找 needle（expect_print 的 UTF-8 字节）。

    命中返回可读证据窗（前后各 ctx 字节，控制字符以 · 代）；未命中/读不到
    （文件尚未落盘、正被游戏占用）返回 None——由调用方轮询重试。
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    i = data.find(needle)
    if i < 0:
        return None
    win = data[max(0, i - ctx): i + len(needle) + ctx]
    txt = win.decode("utf-8", errors="replace")
    return "".join(ch if (ch.isprintable() or ch == "\t") else "·" for ch in txt)


def verdict_from_log(expect_print: str, gia_paths, map_id: str | None = None) -> Verdict:
    """相3 纯判决（不轮询不等待）：对给定 .gia 逐个找 expect_print。

    level.judge 相3 的内核；也是相3 单测与事后离线复判的入口。
    """
    paths = [str(p) for p in gia_paths]
    needle = expect_print.encode("utf-8")
    for p in paths:
        ev = find_print(p, needle)
        if ev is not None:
            return Verdict(passed=True, evidence=ev, map_id=map_id,
                           log_file=p, expect_print=expect_print)
    return Verdict(passed=False, reason="print_not_found", map_id=map_id,
                   log_file=(paths[0] if paths else None), expect_print=expect_print)


# ---------------------------------------------------------------------------
# 注册模块
# ---------------------------------------------------------------------------

@core.module("level.deploy")
def level_deploy(level_gil: str, r_name: str, export_dir: str | None = None) -> core.Result:
    """把关卡 .gil 部署到游戏导入目录，命名 <r_name>.gil，返回落点。

    前置：源文件存在（PreconditionError）；r_name 为单段合法文件名（PreconditionError）；
    源为 0 字节视为坏产物（ModuleRejected）；游戏导入目录未配置（PreconditionError）。
    执行：字节复制到 export_root(export_dir)。重复部署=覆盖（重部署是常规流程）。
    后验：落点存在 + 字节一致；不一致删残件并 ModuleRejected（坏文件不留导入目录）。
    领地：只写导入目录；不校验 gil 内容（L1 字节门归产物模块）。
    纯离线：自测经 export_dir 参数或 QXY_GAME_EXPORT 重定向，零污染真实导入目录。
    """
    src = Path(level_gil)
    if not src.is_file():
        raise core.PreconditionError(f"源 .gil 不存在: {level_gil}")
    if not r_name or (set(r_name) & _R_NAME_ILLEGAL) or r_name.startswith("."):
        raise core.PreconditionError(f"r_name 须为单段合法文件名，得到: {r_name!r}")
    if src.stat().st_size == 0:
        raise core.ModuleRejected("源 .gil 为空（0 字节），拒绝部署")

    dest = export_root(export_dir) / (r_name if r_name.endswith(".gil") else r_name + ".gil")
    if dest.is_dir():
        raise core.PreconditionError(f"落点已是目录: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    if not dest.is_file() or dest.read_bytes() != src.read_bytes():
        try:
            dest.unlink()  # 残件不留盘：导入目录里的坏文件会被真人导入
        except OSError:
            pass
        raise core.ModuleRejected(f"落点字节不一致（已尝试清除）: {dest}")
    return core.Result(ok=True, artifact=str(dest), checks=[
        ("dest_exists", "PASS"),
        ("byte_equal", "PASS"),
        ("deployed_to", str(dest)),
        ("bytes", str(dest.stat().st_size)),
    ])


def _short(s: str, n: int = 120) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def _judge_checks(map_id: str | None, struct: dict, phase2: str,
                  vd: Verdict, phase3: str) -> list:
    """判决 checks（供 oplog/log.query 审计；值恒为短字符串）。"""
    out = [("phase1_new_map", "PASS" if map_id else "FAIL")]
    if map_id:
        out.append(("map_id", map_id))
    for k in ("doc", "f7", "mount"):
        if k in struct:
            out.append((f"dissect_{k}", _short(str(struct.get(k)))))
    out.append(("dissect_leaf", "PASS" if struct.get("leaf") else "FAIL"))
    if struct.get("error"):
        out.append(("dissect_error", _short(str(struct["error"]))))
    out.append(("phase2_new_gia", phase2))
    if vd.log_file:
        out.append(("log_file", _short(vd.log_file)))
    out.append(("phase3_print", phase3))
    out.append(("expect_print", _short(vd.expect_print)))
    out.append(("reason", _short(str(vd.reason or "-"))))
    out.append(("verdict", "PASS" if vd.passed else "FAIL"))
    return out


@core.module("level.judge")
def level_judge(expect_print: str, timeout_min: float = 10.0, known_maps=None,
                mirror_dir: str | None = None, debug_dir: str | None = None,
                poll_sec: float = 4.0, level_name: str | None = None,
                graph_name: str = "hello", graph_guid: int = 0x40000001,
                host_guid: int = 0x41400001) -> core.Result:
    """三相阻塞观察判决：等导入 → 等 .gia → 在 .gia 中找 expect_print。

    参数：
        expect_print   判决判据（如 "[hello_loop] 圈活了"）；空判据拒绝（不冒充）。
        timeout_min    三相总预算（分钟）。超时如实 Verdict(passed=False, reason=…)。
        known_maps     相1 基线地图 id 集合（dict 则取键）；None=调用时刻镜像快照。
                       判决须在用户导入前启动，否则新导入会被旧基线吞掉。
        mirror_dir/debug_dir  观察面注入（自测零污染）；缺省走 QXY_GAME_MIRROR/
                       QXY_GAME_DEBUGLOG，再缺省走常见默认路径探测。
        poll_sec       轮询间隔秒（下限 0.05；默认 4.0）。
        level_name     可选；给出则把本次判决记入该关卡域的溯源指针（版本不动）。
        graph_name/graph_guid/host_guid  解剖参数（默认=竖线 hello 图三元组）。

    返回：Result.ok=观察完成（恒 True）；value=Verdict（判决真值在 value.passed）。
    前置依赖与不冒充条款见模块 docstring——导入与两层门都是用户白名单动作，
    模块只如实等待与报告。
    """
    if not expect_print:
        raise core.PreconditionError("expect_print 为空——拒绝空判据（不冒充）")
    if timeout_min <= 0:
        raise core.PreconditionError(f"timeout_min 须>0，得到 {timeout_min}")
    poll = max(0.05, float(poll_sec))
    mir = mirror_root(mirror_dir)
    dbg = debug_root(debug_dir)
    deadline = time.time() + timeout_min * 60

    def wait_tick() -> None:
        time.sleep(min(poll, max(0.0, deadline - time.time())))

    # ---- 相1 导入观察：等基线之外的新地图 ----
    base_ids = set(known_maps) if known_maps is not None else set(mirror_snapshot(mir))
    map_id: str | None = None
    gil_path: str | None = None
    while True:
        ents = mirror_snapshot(mir)
        new = {k: v for k, v in ents.items() if k not in base_ids}
        if new:
            map_id, (gil_path, _) = max(new.items(), key=lambda kv: kv[1][1])
            break
        if time.time() >= deadline:
            break
        wait_tick()

    if map_id is None:
        vd = Verdict(passed=False, reason="timeout_no_new_map", expect_print=expect_print)
        return core.Result(ok=True, value=vd, level=level_name, checks=_judge_checks(
            None, {}, "FAIL", vd, "FAIL"))

    struct = dissect(gil_path, graph_name, graph_guid, host_guid)

    # ---- 相2 等待调试日志：等比基线新的 .gia ----
    dbg_base = debug_snapshot(dbg)
    first_gia: list[str] = []
    while True:
        ents = debug_snapshot(dbg)
        first_gia = sorted((n for n, mt in ents.items()
                            if n not in dbg_base or mt > dbg_base[n]),
                           key=lambda n: -ents[n])
        if first_gia:
            break
        if time.time() >= deadline:
            break
        wait_tick()

    if not first_gia:
        vd = Verdict(passed=False, reason="timeout_no_new_debug_log", map_id=map_id,
                     struct=struct, expect_print=expect_print)
        return core.Result(ok=True, value=vd, level=level_name, checks=_judge_checks(
            map_id, struct, "FAIL", vd, "FAIL"))

    # ---- 相3 判决：新 .gia（可能仍在增长）字节流中找 expect_print，轮询到截止 ----
    needle = expect_print.encode("utf-8")
    log_file: str | None = None
    while True:
        ents = debug_snapshot(dbg)  # 重扫：后续试玩会产生更多新 .gia
        names = sorted((n for n, mt in ents.items()
                        if n not in dbg_base or mt > dbg_base[n]),
                       key=lambda n: -ents[n])
        for n in names:
            p = str(dbg / n)
            log_file = log_file or p
            ev = find_print(p, needle)
            if ev is not None:
                vd = Verdict(passed=True, evidence=ev, map_id=map_id, log_file=p,
                             struct=struct, expect_print=expect_print)
                return core.Result(ok=True, value=vd, level=level_name, checks=_judge_checks(
                    map_id, struct, "PASS", vd, "PASS"))
        if time.time() >= deadline:
            break
        wait_tick()

    vd = Verdict(passed=False, reason="print_not_found", map_id=map_id,
                 log_file=log_file or str(dbg / first_gia[0]),
                 struct=struct, expect_print=expect_print)
    return core.Result(ok=True, value=vd, level=level_name, checks=_judge_checks(
        map_id, struct, "PASS", vd, "FAIL"))
