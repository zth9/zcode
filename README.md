# zcode

`zcode` 是一个通用的 CLI Agent 入门项目。

它想做的事情很简单：参考 `Claude Code` 一类工具的交互方式，但主动砍掉大量工程化细节，只保留最核心的设计思想，用一个更容易读懂、更容易自己动手扩展的最小实现，来探索和学习 `harness` 的搭建过程。

项目灵感来自 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)。如果你也对 Agent、工具调用、上下文拼装和模型驱动的执行循环感兴趣，这个仓库就是一个合适的起点。

享受搭建 harness 的过程吧。

## 这个项目关注什么

`zcode` 关注的是一个 CLI Agent 最本质的几件事：

- 如何接收用户输入并组织成模型可消费的上下文
- 如何设计一个清晰的 agent loop
- 如何把工具调用纳入循环，而不是把工具写成零散脚本
- 如何让模型输出驱动下一步动作
- 如何在尽量少的代码里保留可观察、可调试、可演化的结构

换句话说，这不是一个“功能尽量全”的产品型项目，而是一个“结构尽量清楚”的学习型项目。

## 刻意简化的部分

为了把注意力放在核心机制上，`zcode` 会刻意弱化或暂时忽略这些能力：

- 复杂的权限系统
- 大而全的工具生态
- 面向生产环境的稳定性治理
- 复杂的状态持久化与恢复

这些都很重要，但不适合放进一个 harness 入门项目的第一阶段。

## 想保留下来的核心设计思想

即使做了大量简化，`zcode` 仍然希望保留下面这些关键思路：

1. **一切围绕 loop 展开**

   Agent 的本质不是一次请求响应，而是一个持续循环：

   - 读取用户目标
   - 构造上下文
   - 请求模型
   - 解析动作
   - 执行工具
   - 回填 observation
   - 直到结束

2. **工具是 agent 的一部分，不是外挂**

   工具调用不是“额外加点脚本”，而是 agent 推理过程中的标准动作。模型、工具、观察结果、下一轮推理，应该天然连成一个闭环。

3. **优先保留可读性**

   相比一开始就追求抽象层次和可扩展性，`zcode` 更看重：

   - 新手能不能顺着代码读下去
   - 关键流程能不能一眼定位
   - 每一步输入输出是否足够明确

4. **先有最小可运行，再谈能力叠加**

   比起一开始就设计“完美架构”，更实际的路径通常是：

   - 先跑通最小 loop
   - 再补工具协议
   - 再补上下文管理
   - 再补错误处理和可观测性

## 当前仓库结构

当前仓库已经有一个最小可运行的 agent loop：

```text
.
├── .env.example
├── pyproject.toml
├── README.md
└── src
    └── zcode
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        ├── agent.py
        ├── shell.py
        └── tools.py
```

这个布局里，`src` 只是源码根目录，真正的 Python 包是 `zcode`。为了把学习成本压到更低，当前实现故意把“只会被单点调用一次的 helper”折回核心文件，只保留真正有独立复杂度的模块：

- 导入路径稳定，不再把 `src` 误当成业务包名
- `cli.py` 负责 CLI 入口、参数解析、环境变量读取和 REPL
- `agent.py` 负责 system prompt、单轮请求、tool result 回填和核心 loop
- `tools.py` 负责工具抽象和当前最小的 `bash` 工具
- `shell.py` 单独保留 shell 执行与输出截断逻辑

其中几个关键模块的职责现在是这样划分的：

- `src/zcode/cli.py`：负责 CLI 入口、参数解析和 REPL
- `src/zcode/agent.py`：负责 system prompt、模型请求、工具执行和核心 agent loop
- `src/zcode/tools.py`：定义统一的工具抽象并实现当前最小的 `bash` 工具
- `src/zcode/shell.py`：负责 shell 执行辅助

整体上仍然只覆盖第一阶段最关键的几件事：

- 从 `.env` 读取模型配置
- 通过 Anthropic 兼容接口请求模型
- 提供一个最小的 `bash` 工具
- 在 `tool_use -> tool_result -> 再次请求模型` 之间循环
- 支持 REPL 和一次性命令两种运行方式

这正符合这个项目的目标：从一个足够小但已经能跑起来的起点出发，把 CLI Agent 的核心部件一步步补出来，而不是先堆出一个复杂框架。

## 推荐阅读顺序

如果你是第一次读这个仓库，最省力的方式不是按文件名逐个看，而是顺着一次真实请求的路径往下走：

1. 先看 `src/zcode/cli.py`
2. 从 `main()` 看到 `run_once()`
3. 再进入 `src/zcode/agent.py` 里的 `agent_loop()`
4. 看清楚 `request_turn()` 如何发起单轮模型请求
5. 再看 `collect_tool_results()` 和 `execute_tool_call()` 如何处理 `tool_use`
6. 最后看 `src/zcode/tools.py` 和 `src/zcode/shell.py`，理解工具如何真正落到本地命令执行

如果只想抓主干，可以把一次完整链路理解成：

`用户输入 -> cli.py -> agent_loop() -> 模型返回 tool_use 或文本 -> 执行工具 -> 回填 tool_result -> 继续下一轮`

这样读的好处是，你会先看见“这个 harness 到底怎么跑起来”，再回头看各个局部实现，而不是一开始就陷进零散 helper 里。

## 环境配置

先安装依赖。一个最简单的本地启动方式是：

```bash
python3 -m venv .venv
source .venv/bin/activate.fish
pip install -r requirements.txt
```

这里的 `requirements.txt` 会安装当前项目本身，也就是等价于执行：

```bash
pip install -e .
```

目前 `.env.example` 里预留了最基本的模型接入参数：

```env
# 使用任何支持 anthropic 协议的端点
# claude、glm、minimax、kimi 均可
ANTHROPIC_BASE_URL=
ANTHROPIC_AUTH_TOKEN=
MODEL_ID=
```

这意味着 `zcode` 的实验方向会偏向：

- 用统一的协议接入不同模型服务
- 把注意力放在 agent harness 本身，而不是绑定某一家平台 SDK

## 运行方式

配置好 `.env` 之后，可以直接运行：

```bash
zcode
```

或者：

```bash
python3 -m zcode
```

也可以用一次性 prompt 的方式执行：

```bash
zcode "帮我看看当前目录结构"
```

## 适合谁

这个项目适合下面几类人：

- 想从零理解 CLI Agent 是怎么跑起来的
- 想学习 harness 的基本组织方式
- 想自己做一个轻量版 `Claude Code` 风格工具
- 不想一上来就被大型工程细节淹没

## 后续可以逐步补上的内容

如果继续往前做，一个自然的演进顺序可能是：

1. 增加文件系统读写等更明确的工具边界
2. 抽离 provider、prompt、tool registry 等模块
3. 增加更完整的消息历史和 observation 表达
4. 增加基础日志、调试输出和错误恢复
5. 增加更清晰的安全策略和命令白名单机制
6. 在最小 loop 之上继续探索任务拆解、记忆和多 agent 能力

## 一句话总结

`zcode` 不是为了复制一个完整的 `Claude Code`，而是为了把它背后最值得学习的那部分东西，用更小、更透明、更适合动手实验的方式重新搭起来。
