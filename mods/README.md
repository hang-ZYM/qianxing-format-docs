# mods/ — 文件侧创作模块库

> 模块 = 一个可调用函数，四要素内建：前置检查 → 确定性执行 → 后验验收 → 提交 / 回滚
> （通过则落新版本 + 写操作日志；拒绝则不落新版本、版本指针不动；日志两条分支都写，由 core 保证）。
> 接口标准见 [手册/30 任务分解与模块化方法论](../手册/30_任务分解与模块化方法论.md)。

## 模块一览

| 模块 | 功能 | 依赖面 |
|---|---|---|
| `graphgen.build` | 逻辑 IR（节点/边/文本）→ .gis 图件，后验=官方门禁四连 | 工具树（FULL） |
| `level.mount` | .gis 挂到关卡宿主 → 版本制 .gil，后验=V0-V7 出口校验 | 游戏目录关卡样本（或合成夹具） |
| `level.deploy` | 关卡 .gil → 游戏导入目录（字节一致落盘） | 游戏导入目录 |
| `level.judge` | 三相阻塞观察判决（等导入→等 .gia→找打印字节） | 游戏镜像/日志目录 |
| `level.checkpoint` / `level.rollback` / `log.query` | 版本与日志基础设施 | 无（纯本地） |
| `terrain.patch` | 地形定点手术（层位/坡/材质/水/路径），六前检+六后验 | 无（纯本地） |
| `entity.place` | 向关卡放置 prefab 实体（统一注册律 + 段位律） | 工具树（FULL） |
| `component.attach` | 向实体组件槽追加/替换一个组件条目（含光源/可见性生成器） | 工具树（FULL） |
| `env.set` / `env.direct` | 关卡环境（夜晚/白天/纯色）：整包移植预设 / 字段直写 | 游戏目录真实样本图（FULL） |
| `asset.package` / `asset.deploy` | 实体/元件 → .gia 资产包并落导入目录 | 工具树（FULL） |
| `element.build` | 从零构造元件体 → 打包元件方言 .gia | 工具树（FULL） |

## 配置（路径抽象）

模块库代码不含任何本机绝对路径；一切外部位置经 `mods/config.py` 解析。

### 状态根（模块库自己的领地）

```
QXYV2_ROOT 环境变量  >  默认 <仓库根>/_state/        （.gitignore，运行产物不入库）
```

下设 `state/`（oplog.jsonl 操作日志、tmp 槽、assets/）、`levels/`（关卡版本
`v<N>.gil` + `current.json` 指针）、`runs/`（.gis 中间产物）。

### 游戏目录（按优先级：调用参数 > 环境变量 > 常见默认路径探测 > 未找到）

| 环境变量 | 领域 | 默认探测（…/AppData/LocalLow/miHoYo/原神/BeyondLocal/ 下） |
|---|---|---|
| `QXY_GAME_EXPORT` | 导入目录（deploy 落点） | `Beyond_Local_Export/` |
| `QXY_GAME_MIRROR` | 导入镜像（judge 相1 观察面） | `<账号>/Beyond_Local_Save_Level/` |
| `QXY_GAME_SAVELEVEL` | 关卡样本来源（mount 底座/金样本） | `<账号>/Beyond_Local_Save_Level/` |
| `QXY_GAME_DEBUGLOG` | 试玩调试日志（judge 相2/3） | `<账号>/Beyond_Debug_Log/` |

- 探测不针对任何具体账号（`<账号>` 段按目录扫描）。
- 关卡样本：`level.mount` 正例需要本机游戏目录中的两个关卡文件
  `<savelevel>/1073742022/1073742022.gil`（骨架底座样本）与
  `<savelevel>/1073742025/1073742025.gil`（挂载/资源树金样本）。
- **未找到 ≠ 猜路径**：相关模块调用抛 `PreconditionError` 并附配置指引
  （前置不过=换路，不计失败）。

### 工具树（开发机可选依赖）

```
QXY_TOOL_ROOT 环境变量   （无默认探测——开源仓库不附带、不猜路径）
```

`graphgen.build` 与 `entity.place` 的执行/后验依赖本机研究工具（qxy 包：
图装配器、门禁四连、合成模板库、trial_gate）。未配置时相应模块调用如实
`PreconditionError`；其余模块（core/state/level.mount/deploy/judge/terrain）
零工具树可跑。

## 依赖

```bash
# qxfmt：仓库内置 src/qxfmt（自动自举；亦可 pip install -e .）
# 第三方（仅工具树链路需要）：
pip install blackboxprotobuf
```

## 自测（CORE/FULL 分层）

```bash
python -m mods.selftest          # CORE 必跑（无游戏目录/无工具树）；FULL 缺环境如实 SKIP
python -m mods.selftest --full   # 本机真实环境验收：FULL 缺环境即失败
python -m mods.test_terrain      # 也可单跑任一模块（mods.test_core/mount/deploy/graphgen/entity）
```

- **CORE**：夹具全部由 `tests/fixtures/synth.py` 合成（格式常量，零游戏资产）。
- **FULL**：需游戏目录关卡样本和/或工具树，在本机真实环境验证。

---
（本段为 v2.0 README 占位：mods/ 的定位叙述由主 README 统稿时合并。
本文件只讲模块库自身的配置与自测，不改仓库既有文档。）
