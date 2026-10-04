"""qxfmt.pbtree — 保序保编码的 protobuf 树编解码。

节点表示：``[field_no, wire_type, body]``——wire_type 0 存原始 varint 字节
（可能非最小编码，保序回放依赖这一点），2 存载荷字节，5/1 存定长字节。

嵌套长度前缀是字节手术的雷区：改一处串的长度会级联影响所有外层容器
的长度字节。正确做法是整树 parse → 定点修改 → 整树 emit（docs/22 §4）。
"""


STRICT = True
"""严格模式（2026-10-05 F019b 判例）：默认拒绝非法 protobuf——field 0 / 长度越界 /
截断 / 超10字节 varint。宽松时代这些被静默吞掉，乱码包过了门禁才被游戏拒收。
探索性解析疑似损坏数据时用 parse(b, strict=False)。"""


def parse(b: bytes, strict: bool | None = None):
    strict = STRICT if strict is None else strict
    out = []
    i = 0
    n = len(b)
    while i < n:
        tag, i = _read_varint(b, i, strict)
        f, wt = tag >> 3, tag & 7
        if strict and (f == 0 or f > 536_870_911):
            raise ValueError(f"非法字段号 {f} @ {i}")
        if wt == 0:
            vstart = i
            _, i = _read_varint(b, i, strict)
            out.append([f, wt, b[vstart:i]])
        elif wt == 2:
            ln, i = _read_varint(b, i, strict)
            if i + ln > n:
                if strict:
                    raise ValueError(f"f{f} 长度越界 @ {i}: 要 {ln} 只剩 {n - i}")
                out.append([f, wt, b[i:]])
                i = n
            else:
                out.append([f, wt, b[i:i + ln]])
                i += ln
        elif wt == 5:
            if i + 4 > n:
                if strict:
                    raise ValueError(f"f{f} f32 截断 @ {i}")
                out.append([f, wt, b[i:]]); i = n
            else:
                out.append([f, wt, b[i:i + 4]]); i += 4
        elif wt == 1:
            if i + 8 > n:
                if strict:
                    raise ValueError(f"f{f} f64 截断 @ {i}")
                out.append([f, wt, b[i:]]); i = n
            else:
                out.append([f, wt, b[i:i + 8]]); i += 8
        else:
            raise ValueError(f"非法 wiretype {wt} @ {i}")
    return out


def emit(nodes) -> bytes:
    out = bytearray()
    for f, wt, body in nodes:
        tag = _enc_varint((f << 3) | wt)
        if wt == 2:
            out += tag + _enc_varint(len(body)) + body
        else:
            out += tag + body
    return bytes(out)


def roundtrip(b: bytes) -> bool:
    """encode(parse(x)) == x —— 任何修改前必须为真（docs/01 §5）。"""
    return emit(parse(b)) == b


def children(nd):
    """把 len-delim 节点的 body 再解析一层。"""
    if nd[1] != 2:
        raise ValueError(f"f{nd[0]} 不是 len-delim")
    return parse(nd[2])


def set_body(nd, new_children) -> None:
    nd[2] = emit(new_children)


def first(tree, field):
    for nd in tree:
        if nd[0] == field:
            return nd
    return None


def all_of(tree, field):
    return [nd for nd in tree if nd[0] == field]


def varint_value(nd) -> int:
    v = 0
    for shift, b in enumerate(nd[2]):
        v |= (b & 0x7F) << (7 * shift)
    return v


def set_varint_value(nd, value: int) -> None:
    nd[2] = _enc_varint(value)


def _read_varint(b, i, strict=True):
    v = 0
    s = 0
    cnt = 0
    while True:
        if i >= len(b):
            raise ValueError(f"varint 截断 @ {i}")
        x = b[i]
        i += 1
        cnt += 1
        v |= (x & 0x7F) << s
        s += 7
        if not (x & 0x80):
            return v, i
        if strict and cnt >= 10:
            raise ValueError(f"varint 超10字节 @ {i}")


def _enc_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b7 = n & 0x7F
        n >>= 7
        out.append(b7 | (0x80 if n else 0))
        if not n:
            return bytes(out)
