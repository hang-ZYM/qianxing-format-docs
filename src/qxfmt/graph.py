"""qxfmt.graph — 节点图载荷的导航与定位。

图在容器里的藏身路径（docs/03 §2.1、docs/21 §5）::

    proto → f10（图库；不在顶层时在 f2 分片内容里）
          → f1（图条目包装）× 1..N
          → f1（图文档）

节点（f3，NodeInstance）与引脚（f4，PinInstance）的字段语义见 docs/03 §2.2/§2.3。
"""
from .pbtree import parse, first, all_of, varint_value

PRINT_KERNEL = 1  # 打印节点（节点目录 id，docs/07）


def find_graphs(proto: bytes):
    """返回全部图文档载荷（字节列表）。"""
    top = parse(proto)
    f10s = [nd[2] for nd in all_of(top, 10)]
    if not f10s:
        for f2 in all_of(top, 2):
            f10s += [nd[2] for nd in all_of(parse(f2[2]), 10)]
    graphs = []
    for f10 in f10s:
        for f1a in all_of(parse(f10), 1):
            graphs += [nd[2] for nd in all_of(parse(f1a[2]), 1)]
    return graphs


def graph_tree(graph: bytes):
    return parse(graph)


def nodes(graph_nodes):
    """图的 f3 节点列表（树节点）。"""
    return all_of(graph_nodes, 3)


def node_index(nd_tree) -> int:
    f1 = first(nd_tree, 1)
    return varint_value(f1) if f1 is not None and f1[1] == 0 else None


def kernel_id(nd_tree):
    """节点 f3 kernel_ref 里的 runtime_id（f5）。"""
    f3 = first(nd_tree, 3)
    if f3 is None or f3[1] != 2:
        return None
    f5 = first(parse(f3[2]), 5)
    return varint_value(f5) if f5 is not None and f5[1] == 0 else None


def pins(nd_tree):
    """节点的 f4 引脚列表（树节点）。"""
    return [nd for nd in all_of(nd_tree, 4) if nd[1] == 2]


def pin_slot(pin_tree):
    """引脚 f1 shell_sig → (kind, index)，index 缺省 0。"""
    f1 = first(pin_tree, 1)
    if f1 is None or f1[1] != 2:
        return None
    kind = idx = 0
    for sf in parse(f1[2]):
        if sf[0] == 1 and sf[1] == 0:
            kind = varint_value(sf)
        elif sf[0] == 2 and sf[1] == 0:
            idx = varint_value(sf)
    return kind, idx


def pin_value(pin_tree):
    """引脚的 f3 TypedValue（树节点），无值返回 None。"""
    f3 = first(pin_tree, 3)
    return f3 if f3 is not None and f3[1] == 2 else None


def string_storage(tv_tree):
    """TypedValue 里的 f105 字符串存储 → 其 f1 字符串节点；无则 None。"""
    f105 = first(tv_tree, 105)
    if f105 is None or f105[1] != 2:
        return None
    f1 = first(parse(f105[2]), 1)
    return f1 if f1 is not None and f1[1] == 2 else None


def pin_edges(pin_tree):
    """引脚 f5 的全部连线 → [(目标节点index, 目标shell_sig, 目标kernel_sig)]。

    边存于源引脚、记录对端（目标）签名（docs/22 §3）：执行边对端 kind=1，
    数据边对端 kind=4。
    """
    out = []
    for e in all_of(pin_tree, 5):
        if e[1] != 2:
            continue
        el = parse(e[2])
        tgt = first(el, 1)
        sigs = (first(el, 2), first(el, 3))
        out.append((
            varint_value(tgt) if tgt is not None and tgt[1] == 0 else None,
            sigs[0][2] if sigs[0] is not None and sigs[0][1] == 2 else None,
            sigs[1][2] if sigs[1] is not None and sigs[1][1] == 2 else None,
        ))
    return out


def graph_guid(graph_nodes):
    """图身份 f1 ResourceLocator 的 f5 guid。"""
    f1 = first(graph_nodes, 1)
    if f1 is None or f1[1] != 2:
        return None
    f5 = first(parse(f1[2]), 5)
    return varint_value(f5) if f5 is not None and f5[1] == 0 else None


def graph_name(graph_nodes):
    """图名 f2（仅存在于视图层，docs/21 §5）。"""
    f2 = first(graph_nodes, 2)
    if f2 is None or f2[1] != 2:
        return None
    return f2[2].decode("utf-8", errors="replace")
