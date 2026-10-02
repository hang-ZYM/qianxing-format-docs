"""qxfmt — 千星奇域（Miliastra Wonderland）关卡文件格式工具链。

容器读写（.gil/.gis/.gia）、保序 protobuf 树手术、节点图合成与格式校验。
格式知识见仓库 docs/ 目录（01 容器格式 / 03 数据模型 / 22 最小图正典）。
"""

__version__ = "0.1.0"

from .container import Container, MAGIC, TRAILER
from .pbtree import parse, emit

__all__ = ["Container", "MAGIC", "TRAILER", "parse", "emit", "__version__"]
