# -*- coding: utf-8 -*-
"""模块基础设施（Wave 1）。

把 docs/30《任务分解与模块化方法论》的模块接口标准变成可运行代码：
  - Result 统一返回（产物路径 + 校验明细 + 版本号 + 耗时）
  - PreconditionError（前置不过，不计失败）/ ModuleRejected（后验不过，不入账）
  - module 注册装饰器（包装器：计时 / 自动附 module+secs+version / 成功自动版本+1 落盘 /
    拒绝自动不入账 / 连续 4 次拒绝抛 Voyager 律信号）
  - 操作日志 oplog.jsonl（追加式 JSONL）
  - 版本制 levels/<关卡>/v<N>.gil + current.json 指针

状态根默认 <仓库根>/_state/（gitignore），可用环境变量 QXYV2_ROOT 重定向
（自测用，零污染）；路径解析统一收敛在 mods/config（见其 docstring）。
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import config

# ---- 环境自举：qxfmt（仓库内置 src/qxfmt）幂等入径，不强制导入 ----
config.bootstrap_repo_src()

REJECT_LIMIT = 4  # Voyager 律：同模块连续 4 次拒绝 → 编排器换路


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------

class PreconditionError(Exception):
    """前置不过——不计失败、不计拒绝，编排器换路。"""


class ModuleRejected(Exception):
    """后验不过——不入账（版本指针不动），计入连续拒绝。"""


class ConsecutiveRejectError(Exception):
    """同模块连续 4 次拒绝——Voyager 律信号，编排器必须换路。"""


# ---------------------------------------------------------------------------
# Result 统一返回
# ---------------------------------------------------------------------------

@dataclass
class Result:
    """统一返回。module / secs / version 由包装器自动附填。"""
    ok: bool
    module: str = ""
    artifact: str | None = None   # 产物路径；版本落盘时复制它的字节
    checks: list = field(default_factory=list)  # [(检查名, PASS/FAIL/TRIVIAL/PENDING-ANCHOR)]
    version: int | None = None
    error: str | None = None
    secs: float = 0.0
    # 以下为 spec 七字段之外的扩展
    level: str | None = None        # 模块声明的关卡域——决定版本落点
    value: Any = None               # 查询型模块的返回载荷（如 log.query 的条目）
    rollback_to: int | None = None  # 指针回拨目标版（前置校验过；wrapper 落指针）


# ---------------------------------------------------------------------------
# 模块注册表 + 包装器
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable] = {}
_rejects: dict[str, int] = {}  # 模块名 → 连续拒绝计数（内存态；oplog 留全量证据）


def module(name: str, readonly: bool = False) -> Callable:
    """模块注册装饰器。readonly=纯读模块：不落日志、不碰版本。"""
    def deco(fn: Callable) -> Callable:
        if name in _REGISTRY:
            raise ValueError(f"模块重复注册: {name}")

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return run_module(fn, name, args, kwargs, readonly=readonly)

        wrapper.module_name = name
        wrapper.readonly = readonly
        wrapper.raw_fn = fn
        _REGISTRY[name] = wrapper
        return wrapper

    return deco


def get_module(name: str) -> Callable:
    return _REGISTRY[name]


def list_modules() -> list[str]:
    return sorted(_REGISTRY)


def reset_rejections(name: str | None = None) -> None:
    """清连续拒绝计数（编排器换路后/自测用）。None=全清。"""
    if name is None:
        _rejects.clear()
    else:
        _rejects.pop(name, None)


def _sanitize(s: str) -> str:
    """机器位置脱写：状态根/仓库根/用户主目录 → 标记。oplog 是运行产物，
    保持可审计但不携带本机绝对路径（可能被扫查/随环境共享）。
    覆盖三种出现形态：原样 / repr 转义（反斜杠双写）/ 正斜杠。"""
    for needle, mark in ((str(config.state_root()), "<state_root>"),
                         (str(config.REPO_ROOT), "<repo>"),
                         (os.environ.get("USERPROFILE") or "", "<user>")):
        for form in (needle, needle.replace("\\", "\\\\"), needle.replace("\\", "/")):
            if form and form in s:
                s = s.replace(form, mark)
    return s


def _summarize(args: tuple, kwargs: dict) -> str:
    """参数摘要：repr 截断到 160 字符；机器位置脱写（_sanitize）。"""
    s = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
    return _sanitize(s) if len(s) <= 160 else _sanitize(s)[:157] + "..."


def _reject(name: str, args_summary: str, checks: list, error: str, secs: float) -> Result:
    """记账一次拒绝并推进 Voyager 计数；达到 4 次抛换路信号。"""
    _append_oplog(kind="rejected", module=name, args=args_summary, ok=False,
                  checks=checks, version=None, error=error, secs=secs)
    n = _rejects.get(name, 0) + 1
    if n >= REJECT_LIMIT:
        _rejects[name] = 0  # 信号已发，给换路后的重试一个干净计数
        raise ConsecutiveRejectError(
            f"{name} 连续 {REJECT_LIMIT} 次拒绝（Voyager 律）→ 编排器换路")
    _rejects[name] = n
    return Result(ok=False, module=name, error=error, secs=secs)


def run_module(fn: Callable, name: str, args: tuple, kwargs: dict,
               readonly: bool = False) -> Result:
    """包装器主流程：计时 → 执行 → 异常记账 → 成功落版 → 落日志。"""
    t0 = time.perf_counter()
    args_summary = _summarize(args, kwargs)

    def _secs() -> float:
        return round(time.perf_counter() - t0, 6)

    # ---- 前置 / 后验 / 意外异常 三分支记账 ----
    try:
        r = fn(*args, **kwargs)
    except PreconditionError as e:
        # 前置不过：不计失败、不计拒绝，换路
        _append_oplog(kind="precondition", module=name, args=args_summary, ok=False,
                      checks=[], version=None, error=f"PRECONDITION: {e}", secs=_secs())
        return Result(ok=False, module=name, error=f"PRECONDITION: {e}", secs=_secs())
    except ModuleRejected as e:
        # 后验不过：不入账（版本指针不动）+ 计连续拒绝
        return _reject(name, args_summary, [], f"REJECTED: {e}", _secs())
    except Exception as e:
        # 非前置/后验的意外崩溃：落日志后原样上抛（响亮失败，不计拒绝）
        _append_oplog(kind="error", module=name, args=args_summary, ok=False,
                      checks=[], version=None, error=f"ERROR: {e!r}", secs=_secs())
        raise

    if not isinstance(r, Result):
        raise TypeError(f"模块 {name} 必须返回 Result，得到 {type(r).__name__}")

    r.module = name
    r.secs = _secs()

    if readonly:
        return r  # 纯读：不落日志、不碰版本

    if not r.ok:
        # 模块自评失败（未抛异常）也按拒绝记账
        return _reject(name, args_summary, list(r.checks),
                       r.error or "REJECTED: 模块自评失败", r.secs)

    # ---- 成功：按模块交出的产物决定版本动作 ----
    if r.level and r.artifact:
        src = Path(r.artifact)
        if not src.exists():
            # 宣称的产物不存在 = 后验事实不成立，按拒绝处理
            return _reject(name, args_summary, list(r.checks),
                           f"REJECTED: 产物不存在: {r.artifact}", r.secs)
        newv = commit_version(r.level, src)
        if version_path(r.level, newv).read_bytes() != src.read_bytes():
            # 落盘字节守恒失败——基础设施事故，响亮失败
            _append_oplog(kind="error", module=name, args=args_summary, ok=False,
                          checks=list(r.checks), version=newv,
                          error="ERROR: 版本落盘字节不守恒", secs=r.secs)
            raise RuntimeError(f"{name}: v{newv} 落盘字节与产物不一致")
        r.checks = list(r.checks) + [("commit_byte_equal", "PASS")]
        r.version = newv
        seq = _append_oplog(kind="ok", module=name, args=args_summary, ok=True,
                            checks=r.checks, version=newv, error=None, secs=r.secs)
        _write_pointer(r.level, newv, seq)
    elif r.level and r.rollback_to is not None:
        r.version = r.rollback_to  # 指针回拨：不产新版本，只改 current 指向
        seq = _append_oplog(kind="ok", module=name, args=args_summary, ok=True,
                            checks=list(r.checks), version=r.version, error=None, secs=r.secs)
        _write_pointer(r.level, r.version, seq)
    elif r.level:
        r.version = current_version(r.level)  # 无产物：版本不动，仅刷新溯源序号
        seq = _append_oplog(kind="ok", module=name, args=args_summary, ok=True,
                            checks=list(r.checks), version=r.version, error=None, secs=r.secs)
        _write_pointer(r.level, r.version, seq)
    else:
        _append_oplog(kind="ok", module=name, args=args_summary, ok=True,
                      checks=list(r.checks), version=None, error=None, secs=r.secs)

    _rejects[name] = 0  # 成功清零连续拒绝计数
    return r


# ---------------------------------------------------------------------------
# 状态根与路径（解析收敛到 config；此处保留旧名做模块内部便捷面）
# ---------------------------------------------------------------------------

def _root() -> Path:
    """状态根：默认 <仓库根>/_state/，QXYV2_ROOT 可重定向（自测隔离用）。"""
    return config.state_root()


def state_dir() -> Path:
    return _root() / "state"


def levels_root() -> Path:
    return _root() / "levels"


def oplog_path() -> Path:
    return state_dir() / "oplog.jsonl"


def level_dir(name: str) -> Path:
    return levels_root() / name


def version_path(level: str, v: int) -> Path:
    return level_dir(level) / f"v{v}.gil"


def current_path(level: str) -> Path:
    return level_dir(level) / "current.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# 版本制：v<N>.gil + current.json
# ---------------------------------------------------------------------------

def current_version(level: str) -> int:
    p = current_path(level)
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get("version", 0))
    except Exception:
        return 0


def _write_pointer(level: str, version: int, op_seq: int | None) -> None:
    """写 current.json：{version, op_seq, updated_ts}。"""
    p = current_path(level)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"version": version, "op_seq": op_seq, "updated_ts": _now()},
        ensure_ascii=False), encoding="utf-8")


def commit_version(level: str, src: Path) -> int:
    """把 src 的字节落成 level 的新版本（v<当前+1>.gil），返回新版本号。"""
    level_dir(level).mkdir(parents=True, exist_ok=True)
    newv = current_version(level) + 1
    shutil.copyfile(src, version_path(level, newv))
    return newv


def read_current(level: str) -> bytes | None:
    """读当前生效版本的字节；无版本返回 None。"""
    v = current_version(level)
    if v <= 0:
        return None
    p = version_path(level, v)
    return p.read_bytes() if p.exists() else None


def check_rollback(level: str, to_version: int) -> None:
    """回滚前置校验：目标版存在且不是当前版。不过抛 PreconditionError。"""
    if to_version <= 0 or not version_path(level, to_version).exists():
        raise PreconditionError(f"{level} v{to_version} 不存在，无法回滚")
    if to_version == current_version(level):
        raise PreconditionError(f"{level} 已在 v{to_version}，无需回滚")


def rollback(level: str, to_version: int, op_seq: int | None = None) -> int:
    """指针回拨（不产新版本）。供编排器直接调用；模块路径走 level.rollback。"""
    check_rollback(level, to_version)
    _write_pointer(level, to_version, op_seq)
    return to_version


# ---------------------------------------------------------------------------
# 操作日志 oplog.jsonl（追加式）
# ---------------------------------------------------------------------------

def _last_seq() -> int:
    """读文件尾部取最后一条的 seq（避免全文件扫描）。"""
    p = oplog_path()
    if not p.exists():
        return 0
    with open(p, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        buf = b""
        pos = size
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            if b"\n" in buf:
                break
    lines = [ln for ln in buf.strip().split(b"\n") if ln.strip()]
    if not lines:
        return 0
    try:
        return int(json.loads(lines[-1].decode("utf-8"))["seq"])
    except Exception:
        return 0


def _append_oplog(*, kind: str, module: str, args: str, ok: bool,
                  checks: list, version: int | None, error: str | None,
                  secs: float) -> int:
    """追加一条操作日志，返回其 seq。"""
    oplog_path().parent.mkdir(parents=True, exist_ok=True)
    seq = _last_seq() + 1
    entry = {
        "seq": seq, "ts": _now(), "module": module, "args": _sanitize(args), "kind": kind,
        "ok": ok,
        "checks": [[_sanitize(str(x)) for x in c] if isinstance(c, (list, tuple))
                   else _sanitize(str(c)) for c in checks],
        "version": version,
        "error": _sanitize(error) if error else error, "secs": secs,
    }
    with open(oplog_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return seq


def read_oplog() -> list[dict]:
    """全量读操作日志（P0 日志量小，直接全读）。"""
    p = oplog_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def query_oplog(module: str | None = None, seq_from: int | None = None,
                seq_to: int | None = None, ok: bool | None = None) -> list[dict]:
    """log.query 的实现：按 module 精确名 / seq 闭区间 / ok 过滤。"""
    rows = read_oplog()
    if module is not None:
        rows = [r for r in rows if r.get("module") == module]
    if seq_from is not None:
        rows = [r for r in rows if r.get("seq", 0) >= seq_from]
    if seq_to is not None:
        rows = [r for r in rows if r.get("seq", 0) <= seq_to]
    if ok is not None:
        rows = [r for r in rows if r.get("ok") is ok]
    return rows
