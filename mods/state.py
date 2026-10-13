# -*- coding: utf-8 -*-
"""首批状态类模块：level.checkpoint / level.rollback / log.query。

- level.checkpoint：当前 .gil 落一版（人工节点前后调用）
- level.rollback：版本指针回拨（不产新版本）
- log.query：读操作日志（编排器读状态用；readonly=自身不落日志）

全部零外部依赖（CORE：无游戏目录/无工具树可跑）。
"""
from __future__ import annotations

from pathlib import Path

from . import core


@core.module("level.checkpoint")
def level_checkpoint(level_name: str, source_gil: str) -> core.Result:
    """把 source_gil 的字节落成 level_name 的下一版。

    前置：源文件存在。
    后验：字节落盘（包装器自动加 commit_byte_equal 字节守恒检查）。
    """
    src = Path(source_gil)
    if not src.exists():
        raise core.PreconditionError(f"源 .gil 不存在: {source_gil}")
    if src.stat().st_size == 0:
        raise core.ModuleRejected("源 .gil 为空（0 字节），拒绝落版")
    return core.Result(ok=True, artifact=str(src), level=level_name,
                       checks=[("source_readable", "PASS")])


@core.module("level.rollback")
def level_rollback(level_name: str, to_version: int) -> core.Result:
    """版本指针回拨到 to_version（不产新版本，只改 current.json）。"""
    core.check_rollback(level_name, to_version)  # 前置：目标版存在且非当前
    return core.Result(ok=True, level=level_name, rollback_to=to_version,
                       checks=[("target_version_exists", "PASS")])


@core.module("log.query", readonly=True)
def log_query(module: str | None = None, seq_from: int | None = None,
              seq_to: int | None = None, ok: bool | None = None) -> core.Result:
    """读操作日志，条目列表放在 Result.value。过滤条件可组合。"""
    rows = core.query_oplog(module=module, seq_from=seq_from,
                            seq_to=seq_to, ok=ok)
    return core.Result(ok=True, value=rows, checks=[("count", "TRIVIAL")])
