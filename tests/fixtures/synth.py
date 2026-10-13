# -*- coding: utf-8 -*-
"""tests/fixtures/synth — 合成最小夹具构造器（零游戏资产，全部格式常量生成）。

三个用途（对位 mods 各模块测试的夹具需求）：
  1. 骨架底座关卡（write_base_gil）——level.mount 的 base / terrain.patch 的
     「无 f7 负例底座」。真实样本是 84B 形态（f1 map id + f2 名 + 元数据字段）；
     本合成件取其结构最小集（f1+f2），对 mount 的校验面等价。
  2. 宿主样本关卡（write_gold_like_gil）——level.mount 金样本克隆的替代件：
     含 0x41400001 关卡宿主（f2 头 asset_id=10003004、f6 四节点 f11/f13挂载/f14/
     f17、f7 在 f6 之后——assemble V2 校验的结构面）。13B 挂载内芯等挂载形态
     常量与正典生成器（mount_unit_inner）逐字节同构。
  3. 最小图件（write_min_gis）——level.mount 的输入 .gis：单文档单图
     （kernel71 事件 → kernel1 打印 + 文本引脚），过 load_graph_doc 结构门。

地形夹具（write_terrain_gil）按 docs/17 形态构造 f7 组：组{f1:id, f2:名, f4×N 地块}，
地块 {f1:格键, f2..f6 五字段}——terrain.patch 契约测试的底座。

所有构造器不依赖游戏目录与工具树（CORE 夹具）；字节形态对齐仓库 docs 卷宗
的公开格式知识。字段语义未锚定的位置一律留空/省略，绝不编造。
"""
from __future__ import annotations

from pathlib import Path

# qxfmt 可用性：mods.core 导入时已自举仓库 src/；此处兜底（夹具可独立使用）。
try:
    from qxfmt.container import Container
    from qxfmt.pbtree import emit
except ImportError:  # pragma: no cover
    import sys
    _repo_src = Path(__file__).resolve().parents[2] / "src"
    if _repo_src.is_dir():
        sys.path.append(str(_repo_src))
    from qxfmt.container import Container
    from qxfmt.pbtree import emit

LEVEL_FILE_TYPE = 2   # .gil（关卡容器）
GRAPH_FILE_TYPE = 6   # .gis（图容器）

HOST_GUID = 0x41400001        # S0 唯一关卡宿主
HOST_ASSET_ID = 10003004      # 宿主 f2 头 asset_id（assemble V2 校验锚）
MOUNT_COMPONENT_CID = 3       # f6 挂载组件 cid（载荷 f13）
GOLD_INNER_HEX = "0801108180808004a81fa09c01"  # 13B 挂载内芯格式常量（guid=0x40000001, cat=20000）


# ---------------------------------------------------------------------------
# 基础原语
# ---------------------------------------------------------------------------

def enc(n: int) -> bytes:
    """varint 编码（与 qxfmt 同律；夹具自带，免触私有 API）。"""
    out = bytearray()
    while True:
        b7 = n & 0x7F
        n >>= 7
        out.append(b7 | (0x80 if n else 0))
        if not n:
            return bytes(out)


def mount_unit_inner(graph_guid: int, category: int) -> bytes:
    """挂载条目内芯 13B：{f1:1, f2:图guid, f501:类别}（正典形态）。"""
    return emit([[1, 0, enc(1)], [2, 0, enc(graph_guid)], [501, 0, enc(category)]])


def _save(path, file_type: int, proto: bytes) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    Container(file_type, proto).save(str(p))
    return p


# ---------------------------------------------------------------------------
# 1. 骨架底座关卡（mount 的 base / terrain 的无 f7 底座）
# ---------------------------------------------------------------------------

def base_level_proto(map_id: int = 0x400000C6, name: bytes = b"fixture_map") -> bytes:
    """最小关卡骨架：{f1:map id, f2:名}（真实样本 84B 形态的结构最小集）。"""
    return emit([[1, 0, enc(map_id)], [2, 2, name]])


def write_base_gil(path, map_id: int = 0x400000C6, name: bytes = b"fixture_map") -> Path:
    """写出骨架底座 .gil（无 f5/f6/f7/f10——挂载在其上建，地形负例用其无 f7）。"""
    return _save(path, LEVEL_FILE_TYPE, base_level_proto(map_id, name))


# ---------------------------------------------------------------------------
# 2. 宿主样本关卡（mount 金样本克隆的替代件）
# ---------------------------------------------------------------------------

def _host_entity_tree(host_guid: int = HOST_GUID) -> list:
    """关卡宿主实体树（assemble V2 校验的结构面）：
    {f1:guid, f2:头{f1:asset_id}, f6×4（f11/f13空挂载/f14/f17）, f7 尾随}。
    空挂载节点 = {f1:cid3, f13:{}}（真实样本空挂载形态 0803 6a00 同构）。"""
    def comp(cid: int, extra=()) -> list:
        return [6, 2, emit([[1, 0, enc(cid)]] + list(extra))]

    empty_mount = comp(MOUNT_COMPONENT_CID, [[13, 2, emit([])]])
    tree = [
        [1, 0, enc(host_guid)],
        [2, 2, emit([[1, 0, enc(HOST_ASSET_ID)]])],
        comp(1),                    # f11 编辑器组件位（语义未锚，结构占位）
        empty_mount,                # f13 挂载节点（clone_level_host 摘除位）
        comp(2),                    # f14 编辑器组件位
        comp(4),                    # f17 编辑器组件位
        [7, 2, b"\x0a\x00"],        # f7 尾随（V2 字段序校验：f6 全部先于 f7）
    ]
    return tree


def gold_like_level_proto(host_guid: int = HOST_GUID) -> bytes:
    """宿主样本关卡 proto：f5 容器内恰一枚宿主实体（金样本克隆的输入面）。"""
    host = _host_entity_tree(host_guid)
    return emit([[5, 2, emit([[1, 2, emit(host)]])]])


def write_gold_like_gil(path, host_guid: int = HOST_GUID) -> Path:
    """写出宿主样本 .gil（供 assemble 克隆宿主；测试注入 assemble.DEFAULT_GOLD）。"""
    return _save(path, LEVEL_FILE_TYPE, gold_like_level_proto(host_guid))


# ---------------------------------------------------------------------------
# 3. 最小图件（mount 的输入 .gis）
# ---------------------------------------------------------------------------

def _pin(kind: int, index: int, text: bytes | None = None) -> list:
    """引脚：sig{f1:kind, f2:index(0 省略)}；数据脚带 TypedValue{f105 字符串字面}
    （类型槽形态对齐 docs 卷宗正典；字符串槽 kind=5/类型 6）。"""
    sig = [[1, 0, enc(kind)]] + ([[2, 0, enc(index)]] if index else [])
    body = [[1, 2, emit(sig)]]
    if text is not None:
        body.append([3, 2, emit([
            [1, 0, enc(5)],
            [4, 2, emit([[1, 0, enc(1)], [100, 2, emit([[1, 0, enc(6)]])]])],
            [105, 2, emit([[1, 2, text]])]])])
    return [4, 2, emit(body)]


def _node(index: int, kernel: int, pins: list) -> list:
    """节点：{f1:index, f2:shell_ref{f5:shell=kernel}, f3:kernel_ref{f5:kernel},
    f4:[引脚×N]}（shell=kernel：非泛型节点正典）。"""
    return [3, 2, emit([
        [1, 0, enc(index)],
        [2, 2, emit([[5, 0, enc(kernel)]])],
        [3, 2, emit([[5, 0, enc(kernel)]])],
    ] + pins)]


def min_graph_proto(graph_guid: int, category: int = 20000,
                    name: bytes = b"hello",
                    text: bytes = "[hello_fixture] 圈活了".encode("utf-8")) -> bytes:
    """最小图体：id 块{f1:空间10000, f2:类别, f5:guid} + 图名 + 两节点
    （kernel71 事件 →kernel1 打印+文本脚）——mount 结构门的输入面。"""
    idb = emit([[1, 0, enc(10000)], [2, 0, enc(category)], [5, 0, enc(graph_guid)]])
    node1 = _node(1, 71, [_pin(2, 0)])                       # 事件：流程出 idx0
    node2 = _node(2, 1, [_pin(1, 0), _pin(3, 0, text)])      # 打印：流程入 + 文本
    return emit([
        [1, 2, idb],
        [2, 2, name],
        node1,
        node2,
    ])


def write_min_gis(path, graph_guid: int, category: int = 20000,
                  name: bytes = b"hello",
                  text: bytes = "[hello_fixture] 圈活了".encode("utf-8")) -> Path:
    """写出最小 .gis：f10 → 信封 f1 → 载荷 f1 → 图体（load_graph_doc 同路径）。"""
    doc = [10, 2, emit([[1, 2, emit([[1, 2, min_graph_proto(
        graph_guid, category, name, text)]])]])]
    return _save(path, GRAPH_FILE_TYPE, emit([doc]))


# ---------------------------------------------------------------------------
# 4. 地形夹具（terrain.patch 底座）
# ---------------------------------------------------------------------------

def terrain_level_proto(tiles: list[dict], group_id: int = 1,
                        group_name: bytes = b"fixture_group") -> bytes:
    """地形关卡 proto：f7 → 组{f1:id, f2:名, f4×N 地块}。
    tiles = [{"gx":100,"gz":100,"layer":2,"material":3,...}, ...]（docs/17 形态）。"""
    field_no = {"layer": 2, "material": 3, "water": 4, "path": 5, "slope": 6}
    children: list = [[1, 0, enc(group_id)], [2, 2, group_name]]
    for t in tiles:
        key = (t["gx"] << 16) | t["gz"]
        nd: list = [[1, 0, enc(key)]]
        for fname in ("layer", "material", "water", "path", "slope"):
            if fname in t and t[fname] is not None:
                nd.append([field_no[fname], 0, enc(t[fname])])
        children.append([4, 2, emit(nd)])
    group = [1, 2, emit(children)]
    return emit([[7, 2, emit([group])]])


def write_terrain_gil(path, tiles: list[dict]) -> Path:
    """写出带 f7 地形组的 .gil（terrain.patch 底座；无 f5/f6——地形手术不触）。"""
    return _save(path, LEVEL_FILE_TYPE, terrain_level_proto(tiles))
