"""qxfmt.verify — 图文件格式规则校验（规则面，docs/06 §9-§10 的代码化）。

三条规则 + 两条可选检查：

* R-kind5：kind5 属性引脚的完整形态 = f3 值 + f6 标记{1:6,2:1} + f7；
  裸形态在装载时被静默剥离。
* R-泛型信封：泛型槽位的字面值必须走 poly 信封（widget=10000 + f110 泛型链）；
  裸值形态被静默丢弃。（需要引脚目录才能判定哪些槽是泛型——可选）
* R-信封完整：已呈 poly 信封形态的值必须有 f110 链。

可选：kernel 宇宙表（不在表内 = WARN，节点装载时会被解析器拒绝）。
可选目录都是 JSON：目录格式 {kernel_id: {inputs: [...], outputs: [...]}}，
条目含 kind/index/type；宇宙格式 {kernels: [...]}。
"""
import json

from .container import Container
from .pbtree import parse, varint_value, first, all_of

POLY_ENVELOPE_PREFIX = b"\x08\x90\x4e"  # f1(widget)=10000
KIND5_MARKER = b"\x08\x06\x10\x01"      # f6 = {1:6, 2:1}


def _fields(b):
    return parse(b)


def _load_json(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kernel_id(node_bytes):
    for f, wt, val in [(nd[0], nd[1], nd[2]) for nd in parse(node_bytes)]:
        if f == 3 and wt == 2:
            f5 = first(parse(val), 5)
            if f5 is not None and f5[1] == 0:
                return varint_value(f5)
    return None


def _node_id(node_bytes):
    f1 = first(parse(node_bytes), 1)
    return varint_value(f1) if f1 is not None and f1[1] == 0 else None


def _pin_slot(pin_bytes):
    f1 = first(parse(pin_bytes), 1)
    if f1 is None or f1[1] != 2:
        return None
    kind = idx = 0
    for sf in parse(f1[2]):
        if sf[0] == 1 and sf[1] == 0:
            kind = varint_value(sf)
        elif sf[0] == 2 and sf[1] == 0:
            idx = varint_value(sf)
    return kind, idx


def verify_bytes(data: bytes, catalog=None, universe=None):
    """对整个文件字节做规则校验。返回 (verdict, messages)。"""
    from .graph import find_graphs
    gs = find_graphs(data[20:len(data) - 4]) if len(data) >= 24 else []
    if not gs:
        return "ERROR", ["无图载荷"]
    hits, warns = [], []
    stats = [0, 0]

    def check_pin(pin_bytes, kid, nid):
        stats[1] += 1
        slot = _pin_slot(pin_bytes)
        val = f6 = None
        f7 = None
        for nd in parse(pin_bytes):
            if nd[0] == 3 and nd[1] == 2:
                val = nd[2]
            elif nd[0] == 6 and nd[1] == 2:
                f6 = nd[2]
            elif nd[0] == 7 and nd[1] == 0:
                f7 = varint_value(nd)
        if slot and slot[0] == 5:
            if f6 != KIND5_MARKER or f7 is None:
                hits.append(f"kind5裸引脚 node={nid} kernel={kid} slot={slot} "
                            f"(正典=f3值+f6{{1:6,2:1}}+f7)")
        if slot and catalog:
            ent = catalog.get(str(kid)) if kid is not None else None
            if ent:
                for e in (ent.get("inputs") or []) + (ent.get("outputs") or []):
                    if e.get("kind") == slot[0] and e.get("index") == slot[1] and e.get("type") == "泛型":
                        if val is not None and len(val) >= 3 and val[:3] != POLY_ENVELOPE_PREFIX:
                            hits.append(f"泛型槽裸值 node={nid} kernel={kid} slot={slot} "
                                        "(必须 poly 信封 widget=10000)")
                        break
        if val is not None and len(val) >= 3 and val[:3] == POLY_ENVELOPE_PREFIX:
            if not any(nd[0] == 110 for nd in parse(val)):
                hits.append(f"信封缺f110泛型链 node={nid} slot={_pin_slot(pin_bytes)}")

    for gi, g in enumerate(gs):
        for nd in parse(g):
            if nd[0] == 3 and nd[1] == 2 and len(nd[2]) > 24:
                stats[0] += 1
                kid = _kernel_id(nd[2])
                nid = _node_id(nd[2])
                if universe and kid is not None and kid not in universe:
                    warns.append(f"未知kernel node={nid} kernel={kid}({kid:#x}) — 装载时节点将被删除(WARN)")
                for p in parse(nd[2]):
                    if p[0] == 4 and p[1] == 2:
                        check_pin(p[2], kid, nid)

    tail = [f"图{len(gs)}张 节点{stats[0]} 引脚{stats[1]}"]
    if warns:
        tail.append(f"WARN×{len(warns)}")
    if not hits:
        return "PASS", [" ".join(tail)]
    return "SICK", hits + warns


def verify_file(path, catalog_path=None, universe_path=None):
    c = Container.load(path)
    return verify_bytes(c.to_bytes(), _load_json(catalog_path), _load_json(universe_path))
