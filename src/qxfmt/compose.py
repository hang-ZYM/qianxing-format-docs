"""qxfmt.compose — 模板手术合成器（docs/22 §4-§5 的代码化）。

在一张合法模板图上做定点修改（打印文本 / 图名 / 图 guid），整树重编码输出。
修改前的往返验证（encode(parse(x)) == x）是硬前提——不成立的模板直接拒绝。
"""
from .container import Container
from .pbtree import parse, emit, roundtrip, first, set_varint_value
from . import graph as G


class ComposeError(Exception):
    pass


class Composer:
    def __init__(self, template_path: str):
        self.container = Container.load(template_path)
        if not roundtrip(self.container.proto):
            raise ComposeError("模板 proto 往返验证失败：解析器与该文件不一致，拒绝手术")
        self._proto_tree = parse(self.container.proto)
        f10 = first(self._proto_tree, 10)
        if f10 is None or f10[1] != 2:
            raise ComposeError("模板里找不到图库（f10）")
        self._entry_list = parse(f10[2])
        self._f10 = f10
        entry = first(self._entry_list, 1)
        if entry is None or entry[1] != 2:
            raise ComposeError("模板里找不到图条目（f10.f1）")
        self._doc_list = parse(entry[2])
        self._entry = entry
        doc = first(self._doc_list, 1)
        if doc is None or doc[1] != 2:
            raise ComposeError("模板里找不到图文档（f10.f1.f1）")
        if not roundtrip(doc[2]):
            raise ComposeError("图文档往返验证失败")
        self._graph_list = parse(doc[2])
        self._doc = doc

    # ---- 读取 ----

    @property
    def graph(self):
        return self._graph_list

    def info(self) -> str:
        ns = [n for n in self.graph if n[0] == 3 and n[1] == 2]
        kernels = []
        for n in ns:
            kernels.append(G.kernel_id(parse(n[2])))
        return (f"guid=0x{G.graph_guid(self.graph) or 0:X} "
                f"name={G.graph_name(self.graph)!r} "
                f"nodes={len(ns)} kernels={kernels}")

    # ---- 手术 ----

    def set_text(self, text: str) -> None:
        """替换打印节点（kernel 1）的文本参数。"""
        for n in self.graph:
            if n[0] != 3 or n[1] != 2:
                continue
            node_list = parse(n[2])
            if G.kernel_id(node_list) != G.PRINT_KERNEL:
                continue
            for pin in G.pins(node_list):
                pin_list = parse(pin[2])
                tv = G.pin_value(pin_list)
                if tv is None:
                    continue
                tv_list = parse(tv[2])
                f105 = first(tv_list, 105)
                if f105 is None or f105[1] != 2:
                    continue
                inner = parse(f105[2])
                s = first(inner, 1)
                if s is None or s[1] != 2:
                    continue
                s[2] = text.encode("utf-8")
                f105[2] = emit(inner)
                tv[2] = emit(tv_list)
                pin[2] = emit(pin_list)
                n[2] = emit(node_list)
                return
        raise ComposeError("模板里没有带字符串参数的打印节点")

    def set_name(self, name: str) -> None:
        f2 = first(self.graph, 2)
        if f2 is None or f2[1] != 2:
            raise ComposeError("图文档里没有名字字段（f2）")
        f2[2] = name.encode("utf-8")

    def set_guid(self, guid: int) -> None:
        f1 = first(self.graph, 1)
        if f1 is None or f1[1] != 2:
            raise ComposeError("图文档里没有身份定位符（f1）")
        loc = parse(f1[2])
        f5 = first(loc, 5)
        if f5 is None or f5[1] != 0:
            raise ComposeError("图身份定位符里没有 guid（f5）")
        set_varint_value(f5, guid)
        f1[2] = emit(loc)

    # ---- 输出 ----

    def build(self) -> Container:
        self._doc[2] = emit(self._graph_list)
        self._entry[2] = emit(self._doc_list)
        self._f10[2] = emit(self._entry_list)
        proto = emit(self._proto_tree)
        if not roundtrip(proto):
            raise ComposeError("输出往返验证失败（不应发生）")
        return Container(self.container.file_type, proto)
