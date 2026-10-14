# -*- coding: utf-8 -*-
"""terrain_patch — 地形产线 v1（vendored，本仓库开源版的只读依赖副本）。

来源：内部研究工具树的同名工具（纪律：只 import 包装，不改语义）。本副本
相对原件的差异仅一处——qxfmt 导入自举：原件按旧树相对路径拼 sys.path，
本副本改用「直接 import，失败回退仓库 src/」（mods.core 导入时已自举，
此处兜底保证单独加载亦可）。

结构依据（2026-10-03 商城对战图族解剖 + 手册/17）：
  主.gil f7 → f1 地形组{f1:组id, f2:名, f3:组元数据, f4×N 地块}
  地块 = {1:(gx<<16)|gz 键（grid 100~119）, 2:层位, [3:坡形态], [4:表面形态]}
  实证：L2 地块带 f3=1 且邻块 L1 = 坡（坡向语义待编辑器判决 R7）；
        f4=1 出现于 62 块 L1 地块（表面/路径形态，语义待判 R8）。
"""
import sys as _sys
from pathlib import Path as _Path

try:
    from qxfmt.container import Container
    from qxfmt.pbtree import parse, emit, first, roundtrip, varint_value, set_varint_value, _enc_varint
except ImportError:  # 兜底自举：仓库 src/qxfmt（mods/_vendor/*.py → 仓库根两级之上）
    _repo_src = _Path(__file__).resolve().parents[2] / "src"
    if _repo_src.is_dir():
        _sys.path.append(str(_repo_src))
    from qxfmt.container import Container
    from qxfmt.pbtree import parse, emit, first, roundtrip, varint_value, set_varint_value, _enc_varint


def _tile_key(gx, gz):
    return (gx << 16) | gz


class TerrainPatcher:
    def __init__(self, gil_path):
        self.c = Container.load(gil_path)
        if not roundtrip(self.c.proto):
            raise RuntimeError('底座往返验证失败')
        self.proto = parse(self.c.proto)
        f7 = first(self.proto, 7)
        if f7 is None:
            raise RuntimeError('无 f7 地形组')
        self.f7 = f7
        self.f7_children = parse(f7[2])        # 保留列表引用——save 时要重新 emit 这一层
        self.group = self.f7_children[0]       # f7 唯一子 f1
        self.tiles = {}
        self.order = []
        for nd in parse(self.group[2]):
            if nd[0] == 4:
                tl = parse(nd[2])
                k = varint_value(first(tl, 1))
                self.tiles[k] = tl
                self.order.append((nd, k))

    def _find(self, gx, gz):
        k = _tile_key(gx, gz)
        if k not in self.tiles:
            raise KeyError(f'地块 ({gx},{gz}) 不存在')
        return k

    def _set_int_field(self, gx, gz, field_no, value):
        """在地块上设整数字段（存在改值，不存在按字段序插入）。"""
        tl = self.tiles[self._find(gx, gz)]
        nd = first(tl, field_no)
        if nd is not None and nd[1] == 0:
            set_varint_value(nd, value)
        else:
            # 按字段号序插入（1 < 2 < 3 < 4 < 5 < 6）
            pos = len(tl)
            for i, x in enumerate(tl):
                if x[0] > field_no:
                    pos = i
                    break
            tl.insert(pos, [field_no, 0, _enc_varint(value)])

    def set_layer(self, gx, gz, layer):
        self._set_int_field(gx, gz, 2, layer)

    def set_slope(self, gx, gz, code):
        """坡 = f6（16×type+d；块置低侧）。17卷v2 定案。"""
        self._set_int_field(gx, gz, 6, code)

    def set_material(self, gx, gz, mat):
        """材质 = f3（1..8：1冰/4草/6岩…）。"""
        self._set_int_field(gx, gz, 3, mat)

    def set_water(self, gx, gz, on=1):
        """水体 = f4（顶部一层水体）。"""
        self._set_int_field(gx, gz, 4, on)

    def set_path(self, gx, gz, on=1):
        """路径表面 = f5。"""
        self._set_int_field(gx, gz, 5, on)

    def set_surface(self, gx, gz, form=1):
        """旧名兼容（v1 误判 f4 为表面——实为水体，见 set_water）。"""
        self._set_int_field(gx, gz, 4, form)

    def apply_grid(self, grid):
        """grid: dict {(gx,gz): {'layer':n, 'slope':n, 'surface':n}}（缺省项不动）"""
        for (gx, gz), spec in grid.items():
            if 'layer' in spec: self.set_layer(gx, gz, spec['layer'])
            if 'slope' in spec: self.set_slope(gx, gz, spec['slope'])
            if 'surface' in spec: self.set_surface(gx, gz, spec['surface'])

    def save(self, out_path):
        new_tiles = []
        for nd, k in self.order:
            nd[2] = emit(self.tiles[k])
            new_tiles.append(nd)
        children = [x for x in parse(self.group[2]) if x[0] != 4] + new_tiles
        self.group[2] = emit(children)
        self.f7[2] = emit(self.f7_children)    # f7 层重发射（嵌套回写链完整性）
        proto = emit(self.proto)
        if not roundtrip(proto):
            raise RuntimeError('输出往返验证失败')
        Container(self.c.file_type, proto).save(out_path)

    def read_layer(self, gx, gz):
        tl = self.tiles[self._find(gx, gz)]
        f2 = first(tl, 2)
        return varint_value(f2) if f2 else None


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2]
    p = TerrainPatcher(src)
    print('原始层位样本 (108,108):', p.read_layer(108, 108))
    # 自测网格：4×4 平台 L2 + 一条坡 + 一格表面
    grid = {}
    for gx in range(108, 112):
        for gz in range(108, 112):
            grid[(gx, gz)] = {'layer': 2}
    grid[(109, 112)] = {'layer': 2, 'slope': 1}
    grid[(110, 112)] = {'layer': 2, 'slope': 1}
    grid[(109, 113)] = {'surface': 1}
    p.apply_grid(grid)
    p.save(dst)
    # 回读验证
    p2 = TerrainPatcher(dst)
    checks = [p2.read_layer(108, 108) == 2, p2.read_layer(108, 111) == 2,
              p2.read_layer(100, 100) == 1, p2.read_layer(109, 112) == 2]
    print('回读验证:', 'PASS' if all(checks) else f'FAIL {checks}')
