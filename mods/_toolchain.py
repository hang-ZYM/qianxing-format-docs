# -*- coding: utf-8 -*-
"""mods/_toolchain — 本机研究工具树链路（内部件；开源仓库不附带工具树本体）。

工具树（QXY_TOOL_ROOT，见 mods/config）提供实体合成/打包/门禁的研究实现：
    qxy.paradigm   V3 正典合成（P.entity 实体 / P.gia 资产包包装 / P.synth 模板库 /
                   P.alloc_guids 台账分配）
    qxy.trial_gate L3 实体形态门禁（comp22 f7/f8/非升序 SICK 拦截、guid 撞号、版本门卫）

本模块把「工具树加载 + trial_gate 运行」收敛为一处（mods/entity.py 等复用），
缺工具树时一律 PreconditionError 并附配置指引——绝不静默降级、绝不猜路径。
"""
from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
from pathlib import Path

from . import config, core


def ensure_toolchain():
    """装载工具树（幂等），返回 (paradigm, trial_gate)。

    前置：QXY_TOOL_ROOT 配置且存在；第三方依赖 blackboxprotobuf 可 import
    （qxy 包经 dsl 间接依赖）——缺失各自给清晰指引（PreconditionError）。
    """
    root = config.require_tool_root("实体合成/资产打包/形态门禁链路")
    config.ensure_third_party("blackboxprotobuf")
    if str(root) not in sys.path:
        sys.path.append(str(root))
    import qxy.paradigm as P      # noqa: E402  触发 qxy/__init__
    import qxy.trial_gate as tg   # noqa: E402
    return P, tg


def run_trial_gate(gia_file: str | Path) -> tuple[str, str]:
    """跑 trial_gate，返回 (结论, 全量输出)。结论 ∈ TRIAL_PASS / TRIAL_SICK。

    首选 subprocess `python -m qxy.trial_gate <file>`（与产线调用形制一致，
    cwd=工具树根保证 qxy 可导入）；spawn 失败（OSError）降级进程内 import
    同一 gate 函数——两者是同一判定代码，只差进程隔离。
    """
    root = config.require_tool_root("trial_gate 形态门禁")
    try:
        cp = subprocess.run(
            [sys.executable, "-m", "qxy.trial_gate", str(gia_file)],
            cwd=str(root), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=120)
        out = (cp.stdout or "") + (cp.stderr or "")
        m = re.search(r"结论:\s*(TRIAL_PASS|TRIAL_SICK)", out)
        if m:
            return m.group(1), out
        return ("TRIAL_PASS" if cp.returncode == 0 else "TRIAL_SICK"), out
    except OSError:  # spawn 失败 → 进程内降级（同一 gate 函数）
        _, tg = ensure_toolchain()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = tg.gate(str(gia_file))
        return ("TRIAL_PASS" if rc == 0 else "TRIAL_SICK"), buf.getvalue()
