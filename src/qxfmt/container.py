"""qxfmt.container — .gil/.gis/.gia 容器读写。

布局（docs/01）::

    [0:4]   payload_total  大端 uint32  = 文件总大小 - 4
    [4:8]   version        大端 uint32  = 1
    [8:12]  magic          大端 uint32  = 806
    [12:16] file_type      大端 uint32
    [16:20] proto_len      大端 uint32  = protobuf 载荷长度
    [20:]   protobuf 消息
    [末4B]  trailer        固定 00 00 06 79

历史上最常见的坑是把 payload_total 写成"文件大小"或"proto_len+20"——
它比文件总大小恰好多算了一个 trailer（即 total = size - 4）。
"""
import struct

MAGIC = 806
TRAILER = bytes.fromhex("00000679")


class Container:
    def __init__(self, file_type: int, proto: bytes):
        self.file_type = file_type
        self.proto = proto

    @property
    def header(self):
        return [len(self.proto) + 20, 1, MAGIC, self.file_type, len(self.proto)]

    def to_bytes(self) -> bytes:
        out = struct.pack(">5I", *self.header) + self.proto + TRAILER
        total = struct.unpack(">I", out[:4])[0]
        assert total == len(out) - 4, f"payload_total={total} 应为 {len(out) - 4}"
        assert len(out) == 20 + len(self.proto) + 4
        return out

    def save(self, path) -> int:
        data = self.to_bytes()
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    @classmethod
    def load(cls, path) -> "Container":
        with open(path, "rb") as f:
            data = f.read()
        h = struct.unpack(">5I", data[:20])
        assert h[2] == MAGIC, f"非本格式容器: 魔数={h[2]}"
        assert data[-4:] == TRAILER, f"尾部异常: {data[-4:].hex()}"
        assert h[0] == len(data) - 4, f"payload_total 异常: {h[0]} vs {len(data) - 4}"
        assert h[4] == len(data) - 24, f"proto_len 异常: {h[4]}"
        return cls(h[3], data[20:20 + h[4]])

    @classmethod
    def repair(cls, path) -> "Container":
        """读取头部字段不全可信的文件（长度字段沿用旧值的历史产物），
        按实际内容重建容器。用于吸收手工工具留下的畸形件。"""
        with open(path, "rb") as f:
            data = f.read()
        h = struct.unpack(">5I", data[:20])
        assert h[2] == MAGIC, f"非本格式容器: 魔数={h[2]}"
        proto = data[20:len(data) - 4]
        return cls(h[3], proto)
