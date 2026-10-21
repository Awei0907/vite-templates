# Agent Course

从一次模型调用开始，按周做成一个可以 clone 运行的本地研究助手。当前是 **Week 0：能成功调用模型**。

接口使用 OpenAI 兼容的 `POST /chat/completions`。OpenAI、DeepSeek、Moonshot、OpenRouter，以及多数本地推理服务都可以用，只要基地址以 `/v1` 结尾。本周不安装 Agent 框架。

## 环境

- Python 3.11 或更高版本
- 一个可用的模型 API 密钥

## 配置

在 `agent-course` 目录执行：

```bash
cp .env.example .env
```

编辑 `.env`，只填入你自己的密钥。`.env` 已被忽略，不要把真实密钥提交到仓库。

```text
MODEL_API_KEY=你的密钥
MODEL_NAME=gpt-4o-mini
MODEL_BASE_URL=https://api.openai.com/v1
MODEL_TIMEOUT_SECONDS=30
```

`MODEL_BASE_URL` 不要带 `/chat/completions`。程序会自己接上这个路径。

## 运行

```bash
cd agent-course
python -m src.client "用一句话介绍你自己"
```

不写句子时，默认就是这句提示。标准输出只有模型回复。

## 失败时会看到什么

错误写到标准错误，进程退出码为 1。密钥即使被服务端回显，也会被替换成 `[REDACTED]`。

- 没填密钥：提示复制 `.env.example`
- 密钥被拒绝：`模型服务拒绝了密钥（HTTP 401）`
- 超过 `MODEL_TIMEOUT_SECONDS`：`请求超时`
- 地址不可达：`无法连接模型服务`

## 检查

Week 0 的自动检查不访问真实模型，只覆盖成功解析、错误密钥、超时和连接失败：

```bash
cd agent-course
python -m unittest discover -s tests -v
```

真实调用要等 `.env` 填好密钥后再执行上面的运行命令。

## 本周完成线

换一个目录 clone 仓库后，复制 `.env.example`，填入密钥，一条命令能拿到模型回复。对应标签是 `week-0`。

## 下一步

Week 1 才加入计算器工具和 observe-think-act 循环。在此之前保持这个文件只做一次对话调用。
