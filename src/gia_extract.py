# -*- coding: utf-8 -*-
"""gia_extract — .gia 资产包实体反向提取（27 卷格式的读取方向）。

把 .gia 里的实体还原成结构化清单（BOM）：guid / asset_id / 名称 / 位置 /
三轴旋转 / 缩放 / 染色。典型用途：编辑器导出件 → 生产数据 → 重建/复用。

用法:
    python -m gia_extract <文件.gia> [--json out.json]

依赖: qxfmt（本仓库）。字段路径见 手册/29。
"""
import argparse
import json
import struct

from qxfmt.container import Container
from qxfmt.pbtree import parse, varint_value


def _f32(b):
    return struct.unpack('<f', b)[0] if len(b) == 4 else None


def _axes(payload):
    """{1:x,2:y,3:z} 的 f32 三元组 -> dict"""
    out = {}
    for nd in parse(payload):
        ax = {1: 'x', 2: 'y', 3: 'z'}.get(nd[0])
        if ax and len(nd[2]) == 4:
            out[ax] = struct.unpack('<f', nd[2])[0]
    return out


def extract_entity(eb):
    """实体消息（与 .gil f5 实体同构）-> dict"""
    d = {}
    for nd in parse(eb):
        f = nd[0]
        if f == 1:
            d['guid'] = varint_value(nd)
        elif f == 8:
            d['asset_id'] = varint_value(nd)
        elif f == 5:
            # 行为组件；名称组件 = {f1:1, f11:{f1: 名称UTF-8}}
            try:
                for s2 in parse(nd[2]):
                    if s2[0] == 11:
                        for s3 in parse(s2[2]):
                            if s3[0] == 1 and isinstance(s3[2], (bytes, bytearray)):
                                try:
                                    d['name'] = bytes(s3[2]).decode('utf-8')
                                except UnicodeDecodeError:
                                    pass
            except Exception:
                pass
        elif f == 6:
            # 编辑器组件；变换组件 = {f1:1, f11:{f1:pos, f2:rot, f3:scale}}
            try:
                for s2 in parse(nd[2]):
                    if s2[0] == 11:
                        for s3 in parse(s2[2]):
                            key = {1: 'pos', 2: 'rot', 3: 'scale'}.get(s3[0])
                            if key:
                                vals = _axes(s3[2])
                                if vals:
                                    d[key] = vals
            except Exception:
                pass
    return d if 'asset_id' in d else None


def extract(gia_path):
    """.gia -> [entity dict, ...]（顺序=包内顺序）"""
    c = Container.load(gia_path)
    ents = []
    for nd in parse(c.proto):
        if nd[0] != 1:
            continue
        eb = None
        for w in parse(nd[2]):
            if w[0] == 12:
                for e2 in parse(w[2]):
                    if e2[0] == 1 and e2[1] == 2:
                        eb = e2[2]
        if eb is not None:
            rec = extract_entity(eb)
            if rec:
                ents.append(rec)
    return ents


def main():
    ap = argparse.ArgumentParser(description='.gia 实体反向提取 (手册/27, 手册/29)')
    ap.add_argument('gia')
    ap.add_argument('--json', dest='json_out', help='输出 JSON 路径（默认打印前 3 条）')
    args = ap.parse_args()
    ents = extract(args.gia)
    print('实体数:', len(ents))
    if args.json_out:
        json.dump(ents, open(args.json_out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('written:', args.json_out)
    else:
        print(json.dumps(ents[:3], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
