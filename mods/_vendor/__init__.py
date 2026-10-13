# -*- coding: utf-8 -*-
"""mods/_vendor — 外部成熟工具的只读依赖副本（vendored）。

纪律：mods/ 各模块只 import 包装，不改这里的语义。每个副本相对原件的
差异仅「路径抽象」（见各文件头部 [VENDORED-DIFF] 标注）：

    assemble.py       装配器 v1（关卡装配 + V0-V7 出口校验 + P 位扫描器）
    terrain_patch.py  地形手术 v1（TerrainPatcher：层位/坡/材质/水/路径）
"""
