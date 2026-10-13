# -*- coding: utf-8 -*-
"""mods.config — 路径与环境抽象（模块库对一切本机位置的唯一出口）。

模块库代码不出现任何本机绝对路径；所有外部位置经本模块解析。三组配置：

═══ 1. 状态根（模块库自己的领地，默认随仓库走）═══

    环境变量 QXYV2_ROOT  >  默认 <仓库根>/_state/

    状态根下设 state/（操作日志 oplog.jsonl、tmp 槽、assets/）、levels/
    （关卡版本 v<N>.gil + current.json）、runs/（.gis 中间产物）。
    _state/ 已列入 .gitignore——运行产物永不入库。

═══ 2. 游戏目录（用户白名单动作的观察面 / 交付落点）═══

    每类目录按优先级解析：调用参数 > 环境变量 > 常见默认路径探测 > 未找到。

    | 领域     | 环境变量           | 默认探测（…/AppData/LocalLow/miHoYo/原神/BeyondLocal/） |
    |----------|--------------------|--------------------------------------------------------|
    | export   | QXY_GAME_EXPORT    | Beyond_Local_Export/（关卡/资产导入目录）               |
    | mirror   | QXY_GAME_MIRROR    | <账号>/Beyond_Local_Save_Level/（导入镜像，judge 相1）  |
    | savelevel| QXY_GAME_SAVELEVEL | <账号>/Beyond_Local_Save_Level/（关卡样本来源）         |
    | debuglog | QXY_GAME_DEBUGLOG  | <账号>/Beyond_Debug_Log/（试玩调试日志，judge 相2/3）   |

    探测不针对任何具体账号：<账号> 段按目录扫描取第一个含目标子目录的条目。
    未找到时相关模块调用抛 PreconditionError 并附配置指引（不算失败，换路）。

    关卡样本（level.mount 的底座/金样本，需用户自备于本机游戏目录）：
        base_level_path()   <savelevel>/1073742022/1073742022.gil（骨架底座样本）
        gold_level_path()   <savelevel>/1073742025/1073742025.gil（挂载/资源树样本）

═══ 3. 工具树（开发机可选依赖；缺省仅影响部分模块的 FULL 能力）═══

    环境变量 QXY_TOOL_ROOT  >  未配置（None）

    工具树指本机私有研究工具目录，含：qxy/ 包（form_gate / oracle_gate /
    trial_gate / paradigm / synth 等）、M4_组件/graph_asm（图装配器）、
    kernel_universe.json、标本库/bank.json。开源仓库不附带、不探测——
    graphgen.build / entity.place / asset 产线需要它；其余模块（core/state/
    level.mount/deploy/judge/terrain）零工具树可跑（见各模块 docstring 与
    selftest 的 CORE/FULL 标注）。

═══ 4. 第三方依赖 ═══

    qxfmt            仓库内置 src/qxfmt，ensure_qxfmt() 自举（pip install -e . 亦可）
    blackboxprotobuf pip 包，仅工具树链路需要，ensure_third_party() 校验并给指引
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR_NAME = "_state"

ENV_STATE_ROOT = "QXYV2_ROOT"
ENV_TOOL_ROOT = "QXY_TOOL_ROOT"

# 游戏目录各领域 → 环境变量名（优先级第二位；第一位是模块调用参数）
GAME_ENV_KEYS = {
    "export": "QXY_GAME_EXPORT",
    "mirror": "QXY_GAME_MIRROR",
    "savelevel": "QXY_GAME_SAVELEVEL",
    "debuglog": "QXY_GAME_DEBUGLOG",
}
# 探测用相对布局（BeyondLocal 之下）
_EXPORT_SUB = "Beyond_Local_Export"
_ACCOUNT_SUBS = {
    "mirror": "Beyond_Local_Save_Level",
    "savelevel": "Beyond_Local_Save_Level",
    "debuglog": "Beyond_Debug_Log",
}
_BASE_MAP_ID = "1073742022"   # 骨架底座样本（84B 形态；任意含同形骨架的关卡可替代）
_GOLD_MAP_ID = "1073742025"   # 挂载/资源树金样本

CONFIG_HINT = (
    "如何配置：①设环境变量 {key}=<目录>；或 ②确认游戏已在本机安装过编辑器"
    "（默认探测 %USERPROFILE%\\AppData\\LocalLow\\miHoYo\\原神\\BeyondLocal\\）；"
    "或 ③调用该模块时显式传入对应目录参数。")


# ---------------------------------------------------------------------------
# 状态根（模块库自己的领地）
# ---------------------------------------------------------------------------

def state_root(override: str | None = None) -> Path:
    """状态根：参数 > QXYV2_ROOT > <仓库根>/_state/。"""
    if override:
        return Path(override)
    env = os.environ.get(ENV_STATE_ROOT)
    if env:
        return Path(env)
    return REPO_ROOT / STATE_DIR_NAME


def state_dir() -> Path:
    """运行状态目录（oplog.jsonl / tmp / assets）。"""
    return state_root() / "state"


def levels_root() -> Path:
    """关卡版本域根（<名>/v<N>.gil + current.json）。"""
    return state_root() / "levels"


def runs_dir() -> Path:
    """.gis 等中间产物目录。"""
    return state_root() / "runs"


# ---------------------------------------------------------------------------
# 游戏目录
# ---------------------------------------------------------------------------

def _beyond_local() -> Path | None:
    """游戏 BeyondLocal 根的常见默认位置；不存在返回 None。"""
    up = os.environ.get("USERPROFILE") or str(Path.home())
    p = Path(up) / "AppData" / "LocalLow" / "miHoYo" / "原神" / "BeyondLocal"
    return p if p.is_dir() else None


def _probe_account_sub(sub: str) -> Path | None:
    """<账号>/<sub> 目录探测：扫 BeyondLocal 下各账号目录，取第一个含 sub 者。"""
    bl = _beyond_local()
    if bl is None:
        return None
    try:
        for d in sorted(bl.iterdir()):
            cand = d / sub
            if cand.is_dir():
                return cand
    except OSError:
        return None
    return None


def game_dir(kind: str, override: str | None = None) -> Path | None:
    """解析一类游戏目录；未配置且探测不到 → None（调用方决定如何拒绝）。

    kind ∈ export / mirror / savelevel / debuglog（见模块 docstring 表）。
    """
    if override:
        return Path(override)
    env = os.environ.get(GAME_ENV_KEYS.get(kind, ""))
    if env:
        return Path(env)
    if kind == "export":
        bl = _beyond_local()
        p = bl / _EXPORT_SUB if bl else None
        return p if p and p.is_dir() else None
    return _probe_account_sub(_ACCOUNT_SUBS[kind])


def require_game_dir(kind: str, override: str | None = None,
                     purpose: str = "") -> Path:
    """game_dir 的必得版：未找到 → PreconditionError（附配置指引）。

    purpose 为一句用途说明（进错误消息，帮调用者对号入座）。
    """
    p = game_dir(kind, override)
    if p is not None:
        return p
    from . import core  # 延迟导入避免环（core 顶部导入 config）
    what = f"（{purpose}）" if purpose else ""
    raise core.PreconditionError(
        f"游戏目录未找到：{kind}{what}。{CONFIG_HINT.format(key=GAME_ENV_KEYS[kind])}")


def savelevel_sample(map_id: str) -> Path | None:
    """关卡样本文件 <savelevel>/<map_id>/<map_id>.gil；无则 None。"""
    sl = game_dir("savelevel")
    if sl is None:
        return None
    p = sl / map_id / f"{map_id}.gil"
    return p if p.is_file() else None


def base_level_path() -> Path | None:
    """骨架底座样本（1073742022）；无则 None。"""
    return savelevel_sample(_BASE_MAP_ID)


def gold_level_path() -> Path | None:
    """挂载/资源树金样本（1073742025）；无则 None。"""
    return savelevel_sample(_GOLD_MAP_ID)


# ---------------------------------------------------------------------------
# 工具树（开发机可选依赖）
# ---------------------------------------------------------------------------

def tool_root(override: str | None = None) -> Path | None:
    """本机研究工具树根（含 qxy/ 包与 M4_组件/）；QXY_TOOL_ROOT > None。

    开源仓库不探测、不附带工具树——需要它的模块在缺省时如实报 PRECONDITION。
    """
    if override:
        return Path(override)
    env = os.environ.get(ENV_TOOL_ROOT)
    return Path(env) if env else None


def require_tool_root(purpose: str = "") -> Path:
    """tool_root 的必得版：未配置 → PreconditionError（附配置指引）。"""
    p = tool_root()
    if p is not None and p.is_dir():
        return p
    from . import core
    what = f"（{purpose}）" if purpose else ""
    raise core.PreconditionError(
        f"工具树未配置{what}：本能力依赖本机研究工具（qxy 包/图装配器），"
        f"开源仓库不附带。设环境变量 {ENV_TOOL_ROOT}=<工具树根目录> 后重试。")


# ---------------------------------------------------------------------------
# 依赖自举与校验
# ---------------------------------------------------------------------------

def bootstrap_repo_src() -> None:
    """把仓库 src/（qxfmt）加入 sys.path（幂等；仓库内路径，随仓库走）。"""
    src = REPO_ROOT / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.append(str(src))


def ensure_qxfmt() -> None:
    """qxfmt 可用性：优先直接 import；失败自举仓库 src/ 再试；仍败给清晰指引。"""
    try:
        import qxfmt  # noqa: F401
        return
    except ImportError:
        pass
    bootstrap_repo_src()
    try:
        import qxfmt  # noqa: F401
    except ImportError as e:
        from . import core
        raise core.PreconditionError(
            f"qxfmt 不可用（{e}）。本仓库内置 src/qxfmt：从仓库根运行，"
            "或 pip install -e . 安装后重试。") from e


def ensure_third_party(name: str = "blackboxprotobuf") -> None:
    """第三方依赖可用性；缺失给 pip 指引（不代装）。"""
    try:
        __import__(name)
    except ImportError as e:
        from . import core
        raise core.PreconditionError(
            f"缺少第三方依赖 {name}（{e}）。安装：pip install {name}") from e
