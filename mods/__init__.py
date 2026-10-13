# -*- coding: utf-8 -*-
"""千星奇域文件侧模块库（mods）。

模块 = 可调用单元，接口标准（前置检查 / 确定性执行 / 后验验收 / 自动日志 /
版本回滚语义）见仓库 docs/30《任务分解与模块化方法论》。

子模块：
    core       基础设施（Result / 异常体系 / 版本制 / 操作日志）
    state      状态类模块（level.checkpoint / level.rollback / log.query）
    config     路径与环境抽象（状态根 / 游戏目录 / 工具树）
    graphgen   graphgen.build —— 造图
    level      level.mount —— 关卡装配挂载
    deploy     level.deploy / level.judge —— 部署与试玩判决
    terrain    terrain.patch —— 地形定点手术
    entity     entity.place —— 放置实体
    selftest   测试入口（python -m mods.selftest [--full]）

依赖：
    qxfmt            仓库内置（src/qxfmt），core 导入时自动自举路径
    blackboxprotobuf 第三方（pip install blackboxprotobuf；仅工具树相关模块需要）

环境变量见 config 模块 docstring 与 mods/README.md。
"""
