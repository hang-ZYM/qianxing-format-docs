# 快速开始

`qxfmt` 是千星奇域（Miliastra Wonderland）关卡文件的工具链：容器读写、保序字节手术、图合成与格式校验。格式知识见 `docs/`（01 容器格式、03 数据模型、22 最小图正典、25 客户端图）。

## 安装

```bash
pip install -e .          # 或免安装：export PYTHONPATH=src
```

## 三步合成一张图

```bash
# 1. 模板合法性检查（修改前的硬前提：往返一致）
python -m qxfmt roundtrip templates/default_graph.gis

# 2. 模板手术：换打印文本 / 图名 / guid，产出新图文件
python -m qxfmt compose -t templates/default_graph.gis -o my_graph.gis \
    --text "你好，世界！" --guid 0x40000030

# 3. 规则校验（kind5 正典 / 泛型信封 / 信封完整）
python -m qxfmt verify my_graph.gis
```

三条命令全部离线运行，不接触任何游戏进程。`templates/default_graph.gis` 是编辑器默认新图的最小正典（事件节点→打印节点，自带执行边——docs/22）。

## 参数说明

| compose 参数 | 作用 | 注意 |
|---|---|---|
| `--text` | 替换打印节点文本 | 模板须含打印节点（kernel 1） |
| `--name` | 替换图名 | **对已有图改名会导致导入拒收**（docs/25 §3），只用于新图 |
| `--guid` | 替换图 guid | 用当前存档未占用的空段号，分配前先全档扫描（docs/22 §6） |

| verify 可选项 | 作用 |
|---|---|
| `--catalog pin目录.json` | 启用泛型槽裸值检查（目录格式见 src/qxfmt/verify.py 文档） |
| `--universe kernel表.json` | 启用未知 kernel 警告（装载时节点会被删除） |

## Python API

```python
from qxfmt.compose import Composer
from qxfmt.verify import verify_bytes

comp = Composer("templates/default_graph.gis")
comp.set_text("你好")            # 打印文本
comp.set_guid(0x40000030)        # 图 guid
out = comp.build()               # Container，往返验证已内建
out.save("my_graph.gis")
print(verify_bytes(out.to_bytes()))
```

## 边界（诚实清单）

- 合成的是**图文件**（.gis）；让它出现在编辑器里需要走官方导入通道，本工具不提供也不涉及注入方法。
- 模板手术目前覆盖：文本 / 图名 / guid。加节点、加边、黑板变量走 `qxfmt.pbtree` 的树原语自行扩展（结构参考 docs/03 §2、docs/22 §3）。
- verify 是**规则面**校验（能拦已知病灶形态），不等于装载判定；装载级确认见 docs/06 §10 的节点级差分方法。
