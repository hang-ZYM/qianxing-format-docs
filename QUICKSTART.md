# 12 分钟跑通

照着做完，你手上会有四样东西：一张自己合成的图文件（过了往返与规则两道校验）、四张从 BOM 画出来的施工图、一份从 `.gia` 里反提出来的 266 条实体清单，以及一次 229 条断言的模块库自测。

全程离线，不需要《原神》，不需要装任何第三方库（`qxfmt` 零依赖）；第 4 步之前只读文件、只写你自己的输出目录，不碰游戏进程。本文每条命令都在 Windows + Python 3.12 上实跑过，每条后面写清"你应该看到什么"。

## 前置

Python 3.8 以上；仓库本体（`git clone https://github.com/hang-ZYM/qianxing-format-docs.git`，或解压已有的目录）。下面所有命令都在**仓库根**（含 `pyproject.toml` 的那一层）执行。

## 第 1 步 · 装（1 分钟）

```bash
python -m pip install -e .
```

应看到最后一行：`Successfully installed qxfmt-0.1.0`。自检：

```bash
python -m qxfmt roundtrip templates/default_graph.gis
```

应看到：`[PASS] default_graph.gis type=6 proto=199B`

（不想改动环境，可改用 `PYTHONPATH=src python -m qxfmt ...`。注意 Python 的隔离模式 `-I` 会忽略 `PYTHONPATH`，两种方式不要混用。）

## 第 2 步 · 读一个真实文件（2 分钟）

`templates/` 里的三张图是从编辑器**原生创建**的存档里提取的真件，不是我们手搓的。先看最小的一张：

```bash
python -m qxfmt inspect templates/default_graph.gis
```

```
default_graph.gis: 1 图
  图0: name='测试添加节点图' guid=0x40000002
    #1 kernel=71  (流出口0)→[2]
    #2 kernel=1
```

怎么读：这就是**编辑器新建一张图时的默认内容**——`#1` 是事件节点（kernel 71 = 实体创建时），`#2` 是动作节点（kernel 1 = 打印字符串），`#1` 的流出口接 `#2` 的执行入口（`→[2]` 里的 2 是节点序号）。这张图为什么长这样见 `手册/22_最小图正典与模板.md` §1；节点/引脚/边 的字段全表见 `手册/03_数据模型总表.md` §2；kernel 编号词表见 `手册/07_节点大全.md`；三张模板各演示什么见 `templates/README.md`。

再看一张构型最全的：

```bash
python -m qxfmt inspect templates/branch_loop_vars.gis
```

应看到 `1 图`、`name='P5T_4_nok' guid=0x40000001`，下面 12 个节点、27 个引脚（分支 / 循环 / 图变量读写 / 查询链），接线读法与上面相同。

顺手读一个**不是图**的真实文件：

```bash
python -m qxfmt roundtrip examples/凯旋门_圣地.gia
```

应看到 `[PASS] 凯旋门_圣地.gia type=3 proto=162482B`。`type` 是容器头第 13–16 字节的文件类型码（布局见 `手册/01_容器格式.md` §2）。顺带记一句：模板 `.gis` 实测为 `6`，与该篇 §1 表里 `.gis` 记的 `2` 不同——那是模板提取件的实际取值。

## 第 3 步 · 生成最小产物（5 分钟）

### 3a. 合成一张图文件

```bash
mkdir out
python -m qxfmt compose -t templates/default_graph.gis -o out/my_graph.gis --text "你好" --guid 0x40000030
```

应看到三行（第三行起是工具对产物做的规则校验）：

```
模板: guid=0x40000002 name='测试添加节点图' nodes=2 kernels=[71, 1]
  图1张 节点2 引脚2
[PASS] 输出 out/my_graph.gis (223B)
```

怎么验证——往返 + 规则两道，再看改动落没落上：

```bash
python -m qxfmt roundtrip out/my_graph.gis   # 期望 [PASS] my_graph.gis type=6 proto=199B
python -m qxfmt verify out/my_graph.gis      # 期望 图1张 节点2 引脚2，后跟 [PASS] my_graph.gis
                                             # 注：verify 是规则面校验（拦已知病灶形态），不等于装载判定
python -m qxfmt inspect out/my_graph.gis     # 期望 guid=0x40000030（模板原本是 0x40000002）
```

说清边界：这是一个**图文件**（.gis），不是可玩关卡，也不能直接拷进游戏——它要进编辑器，见第 4 步。

### 3b. 从 BOM 画四张施工图

```bash
mkdir out
python src/archdraw.py examples/凯旋门_圣地_BOM.json --out out
```

应看到四行 `written: out/凯旋门v6U_*.svg`，产出正立面 / 侧立面 / 平面 / 拱券大样四张 SVG。

怎么验证：用浏览器打开 `out/` 里四张图，和仓库 `examples/` 下的同名文件比——**逐字节相同**（字节数 47635 / 7864 / 31635 / 4219）。

两点如实说明：`--out` 的目录必须已存在（脚本不建目录）；命令**末尾会打印一段 `NameError: name 'draw_detail' is not defined` 的回溯并以非零码退出**——那是脚本 `__main__` 块引用了一个不存在的函数，四张 SVG 在此之前已经写出，产物不受影响。

### 3c. 从 .gia 反提出实体清单

```bash
python src/gia_extract.py examples/凯旋门_圣地.gia --json out/bom.json
```

应看到 `实体数: 266` 与 `written: out/bom.json`；`out/bom.json` 是 266 条 `{guid, name, pos, scale, ...}`。格式与字段语义见 `手册/29_实体BOM工作流与反向提取.md`。（3b 用的 BOM 是另一种形态——带 `meta`/`parts`/`role` 的设计件，两者不是同一套字段。）

### 3d. 一条命令跑完模块库自测

```bash
python -m mods.selftest
```

应看到每个模块一行 `[selftest] OK ...`，末行 `[selftest] 结果：全部通过（CORE；FULL 未见环境者已如实 SKIP）`，合计 **229 条断言 PASS**。其中 `SKIP [FULL]` 的四组（entity / component / asset / element）缺的是本机工具树，属正常。

## 第 4 步 · 进编辑器看（到此为止）

到第 3 步为止，产物都停在磁盘上。让图出现在编辑器里要走**官方导入通道**，需要两样本仓不附带的东西：游戏本体，以及本机游戏目录里的关卡样本（`level.mount` 的底座/金样本，路径由环境变量 `QXY_GAME_SAVELEVEL` 指，见 `mods/README.md`）。没有它们时挂载会如实前置失败——现在就可以试：

```bash
python -c "from mods import level; print(level.level_mount(graph_gis='out/my_graph.gis', host_guid=0x41400001, graph_guid=0x40000030, category=20000).error)"
```

预期这一行：

```
PRECONDITION: 骨架底座样本不可得：配置游戏目录（环境变量 QXY_GAME_SAVELEVEL，见 mods/config）或注入 assemble.DEFAULT_BASE
```

"缺什么就报什么"是这套模块的契约，不是失败。编辑器侧的具体操作（导入、试玩、读日志）以本仓既有材料为准，本文不另编：`手册/02_文件体系与编辑器行为.md`（编辑器行为定律）、`手册/27_gia资产包格式与导入通道.md`、`manuals/16_交付通道与地图现场.md`。

## 下一步去哪

| 你是 | 走这条 |
|---|---|
| 创作者 | README → 本文 → `docs/05_关卡的逻辑.md` → 按需查 `手册/` |
| AI / 自动化工程师 | README → `docs/03_两岸一桥.md` → `docs/06_模块化.md` → `docs/07_任务分解.md` → `mods/MODULES.md` |
| 逆向 / 数据开发者 | README → `手册/README.md`（索引）→ `guide/概念指南.md` |

## 跑不通怎么办

- `No module named qxfmt`：没装，或不在仓库根执行。重跑第 1 步。
- `FileNotFoundError: templates/...`：当前目录不是仓库根。
- `PYTHONPATH=src` 不生效：你加了 `-I`（隔离模式忽略环境变量），去掉它或改用安装。
- `qxfmt` 的中文输出乱码：它把输出固定成 UTF-8，GBK 控制台下会乱。先 `chcp 65001`，或换 Windows Terminal / VS Code / Git Bash，或设 `PYTHONUTF8=1`。
- `src/` 下脚本（archdraw / gia_extract）的中文输出乱码：反过来——它们按控制台默认编码输出，UTF-8 终端里要设 `PYTHONUTF8=1`。
- `archdraw.py` 末尾的 `NameError`：见 3b，产物已写出，可忽略该回溯。
- 3b 报 `FileNotFoundError: ...svg`：`--out` 指向的目录不存在，先 `mkdir`。
- `mods.selftest` 里出现 `SKIP [FULL]`：正常，缺的是游戏目录或工具树，CORE 断言不受影响。
