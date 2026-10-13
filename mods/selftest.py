# -*- coding: utf-8 -*-
"""模块库自测入口（CORE/FULL 分层）。

运行（仓库根）::

    python -m mods.selftest            # CORE 必跑；FULL 缺环境则如实 SKIP
    python -m mods.selftest --full     # 加验 FULL：环境不备即失败（exit 2）

测试分层标注（每条测试输出前缀 [CORE]/[FULL]）：
    CORE  无游戏目录、无工具树可跑（夹具=tests/fixtures 合成件，零游戏资产）
    FULL  需游戏目录（关卡样本）和/或工具树（QXY_TOOL_ROOT）——在本机真实
          环境验证；缺环境 SKIP 并写明缺什么，绝不冒跑。

子进程隔离：每个测试模块独立进程（QXYV2_ROOT 各自重定向临时目录，零污染）。
本文件另含测试共用工具（环境就绪检查 / FULL 门 / 收尾统计）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_REQUIRE_FULL = "QXY_MODS_REQUIRE_FULL"

# (测试模块, 分层标注, FULL 所需环境说明)
TARGETS = [
    ("mods.test_core", "CORE", "-"),
    ("mods.test_terrain", "CORE", "-"),
    ("mods.test_mount", "CORE+FULL", "游戏目录关卡样本（mount 正例全链）"),
    ("mods.test_deploy", "CORE", "-"),
    ("mods.test_graphgen", "CORE+FULL", "工具树（图装配器 + 门禁四连）"),
    ("mods.test_entity", "FULL", "工具树（合成模板库 + trial_gate）"),
]


# ---------------------------------------------------------------------------
# 测试共用工具（被 mods.test_* 导入）
# ---------------------------------------------------------------------------

def game_ready() -> tuple[bool, str]:
    """游戏目录关卡样本是否在位（mount FULL 的环境面）。"""
    from . import config
    base = config.base_level_path()
    gold = config.gold_level_path()
    if base is None or gold is None:
        miss = "底座样本" if base is None else "金样本"
        return False, f"游戏目录关卡样本缺 {miss}（QXY_GAME_SAVELEVEL / 默认探测，见 mods/config）"
    return True, ""


def tool_ready() -> tuple[bool, str]:
    """工具树是否在位（graphgen/entity FULL 的环境面）。"""
    from . import config
    root = config.tool_root()
    if root is None or not (root / "qxy").is_dir():
        return False, f"工具树未配置（{config.ENV_TOOL_ROOT}，见 mods/config）"
    return True, ""


class FullGate:
    """FULL 分层门：环境就绪→跑；不就绪→SKIP 记账（--full 模式下由 finish 判败）。"""

    def __init__(self) -> None:
        self.skipped: list[str] = []
        self.ran: list[str] = []

    def ready(self, name: str, ok: bool, reason: str = "") -> bool:
        if ok:
            self.ran.append(name)
            return True
        self.skipped.append(name)
        print(f"SKIP [FULL] {name}（{reason or '环境不备'}）")
        return False


def require_full_mode() -> bool:
    """本进程是否处于 --full 强制模式（由 mods.selftest --full 注入）。"""
    return os.environ.get(ENV_REQUIRE_FULL) == "1"


def finish(passes: list, gate: FullGate | None = None) -> int:
    """测试收尾：打印合计；--full 模式下 FULL 被跳过 → exit 2。"""
    print(f"\n=== 全部 {len(passes)} 条 PASS ==="
          + (f"（FULL 跳过 {len(gate.skipped)} 组）" if gate and gate.skipped else ""))
    if require_full_mode() and gate is not None and gate.skipped:
        print(f"[selftest] --full 模式：FULL 组被跳过 → 判失败: {gate.skipped}")
        return 2
    return 0


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------

def _run_target(module: str, full: bool) -> int:
    env = dict(os.environ)
    env.pop("QXYV2_ROOT", None)  # 各测试自行重定向，不带外层状态根
    if full:
        env[ENV_REQUIRE_FULL] = "1"
    else:
        env.pop(ENV_REQUIRE_FULL, None)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", module],
                       cwd=str(REPO_ROOT), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "")
    if out.strip():
        print(out.rstrip())
    if (p.stderr or "").strip():
        print(p.stderr.rstrip(), file=sys.stderr)
    return p.returncode


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="模块库自测（CORE/FULL 分层）")
    ap.add_argument("--full", action="store_true",
                    help="强制加验 FULL：环境不备即失败（本机真实环境验收用）")
    ap.add_argument("--only", action="append", metavar="MODULE",
                    help="只跑指定测试模块（可多次，如 --only mods.test_mount）")
    a = ap.parse_args(argv)

    targets = [(m, layer, need) for m, layer, need in TARGETS
               if not a.only or m in a.only]
    if not targets:
        print(f"[selftest] --only 未匹配任何目标（可选: {[m for m, _, _ in TARGETS]}）")
        return 2

    print(f"[selftest] 仓库根: {REPO_ROOT}")
    print(f"[selftest] 模式: {'CORE+FULL' if a.full else 'CORE（FULL 缺环境则 SKIP）'}\n")

    failed = False
    for module, layer, need in targets:
        print(f"---- {module} [{layer}]" + (f"（FULL 需 {need}）" if "FULL" in layer else ""))
        rc = _run_target(module, full=a.full)
        if rc != 0:
            failed = True
            print(f"[selftest] !! {module} 退出码 {rc}\n")
        else:
            print(f"[selftest] OK {module}\n")

    if failed:
        print("[selftest] 结果：存在失败项（见上）")
        return 1
    print("[selftest] 结果：全部通过"
          + ("（CORE+FULL）" if a.full else "（CORE；FULL 未见环境者已如实 SKIP）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
