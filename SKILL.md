---
name: fund-report
version: 1.0.0
description: AI 驱动的基金/投资研究报告自动生成系统 — 调用阿里通义千问 Deep Research，基于 AkShare 实时数据，自动采集、分析、生成专业研报并发送邮件。支持多 Provider / 多 Template / 多 Profile，Registry 架构完全解耦。
author: k7407
tags: [finance, china-a-shares, deep-research, email-automation, cron, akshare, investment-report]
triggers:
  - "生成基金报告"
  - "基金周报"
  - "投资研究报告"
  - "/fundreport"
  - "cron:每周六08:00"
category: productivity
license: MIT
homepage: https://github.com/k7407/fund-report
repository: https://github.com/k7407/fund-report
issues: https://github.com/k7407/fund-report/issues
---

# Fund Report System

> 符合 Agent Skills 开放标准（agentskills.io）的基金研究报告自动生成系统。
> 适用于 Hermite Agent、VS Code Agent、Claude Code、Cursor、OpenHands 等所有支持 skills 标准的 AI 编程工具。

---

## 功能概述

- **自动数据采集**：AkShare 实时获取 A 股指数、行业涨跌、北向资金、两融余额、宏观数据
- **AI 深度研究**：调用阿里通义千问 Deep Research（qwen-deep-research）
- **多模板切换**：周五收盘版 / 周六完整复盘版 / 通用调研版
- **受众画像适配**：`dad` 过滤配比数字，`generic` 保留原始
- **时间防幻觉**：TimeContext 代码强制注入，禁止 AI 推理星期几
- **邮件自动发送**：配置 SMTP 后自动发送，支持 QQ 邮箱 / Gmail / 任意 SMTP

---

## 配置（安装时由 AI Agent 自动询问）

```json
{
  "api_key": {
    "type": "string",
    "required": true,
    "secret": true,
    "description": "阿里云 DashScope API Key（格式 sk-...）"
  },
  "email_password": {
    "type": "string",
    "required": true,
    "secret": true,
    "description": "SMTP 授权码（QQ邮箱设置→账户→POP3/SMTP→生成授权码）"
  },
  "receiver_email": {
    "type": "string",
    "required": true,
    "format": "email",
    "description": "报告收件人邮箱"
  },
  "template": {
    "type": "string",
    "default": "weekend_recap",
    "enum": ["weekly_close", "weekend_recap", "ad_hoc"]
  },
  "profile": {
    "type": "string",
    "default": "dad",
    "enum": ["dad", "generic"]
  }
}
```

### 环境变量注入

```bash
# 必需
export DASHSCOPE_API_KEY="sk-..."

# 可选（默认 weekend_recap + dad）
export TEMPLATE="weekend_recap"
export PROFILE="dad"
export FUND_REPORT_OUTPUT="/path/to/output"
```

---

## 运行方式

### 直接运行

```bash
# 默认：阿里 + 周六完整复盘版 + 爸画像
python3 references/run_and_send_pipeline.py

# 切换模板
TEMPLATE=weekly_close python3 references/run_and_send_pipeline.py

# 通用调研（无受众约束）
TEMPLATE=ad_hoc PROFILE=generic python3 references/run_and_send_pipeline.py
```

### Docker 运行

```bash
docker build -t fund-report .
docker run --rm \
  -e DASHSCOPE_API_KEY=sk-xxx \
  -e EMAIL_PASSWORD=xxxx \
  -e RECEIVER_EMAIL=dad@example.com \
  -e TEMPLATE=weekend_recap \
  -e PROFILE=dad \
  fund-report
```

### Cron 定时

```bash
# 每周六早 8 点（UTC+8）
0 8 * * 6 cd /opt/fund-report && TEMPLATE=weekend_recap PROFILE=dad python3 references/run_and_send_pipeline.py >> /var/log/fund-report.log 2>&1
```

---

## 架构（Registry 模式）

```
references/
├── run_and_send_pipeline.py   ← 主入口（Agent 调用这里）
└── src/
    ├── registry.py            ← Registry 层
    │   ├── ProviderRegistry   → AI 提供商（aliyun）
    │   ├── TemplateRegistry   → 报告模板（weekly_close / weekend_recap / ad_hoc）
    │   └── ProfileRegistry   → 受众画像（dad / generic）
    ├── research_agent.py       ← TimeContext + Mixin
    ├── data_agent.py           ← AkShare 数据采集
    └── email_agent.py          ← 邮件发送
```

### 运行时注入示例

```python
from references.src.registry import ProviderRegistry, TemplateRegistry, ProfileRegistry, TimeContext

# Provider
provider = ProviderRegistry.get("aliyun")

# Template（接收 TimeContext）
tc = TimeContext()
template_fn = TemplateRegistry.get("weekend_recap")
template_chunk = template_fn(data_context, tc)

# Profile（后处理过滤）
profile_cls = ProfileRegistry.get("dad")
report = profile_cls.filter(raw)
```

---

## Provider 注册表

| Name | 说明 | 状态 |
|------|------|------|
| `aliyun` | 阿里通义千问 Deep Research（默认） | ✅ |
| `perplexity` | Perplexity Sonar | 🚧 待接入 |

### 新增 Provider

```python
from references.src.registry import ProviderRegistry

class MyProvider:
    def research(self, query: str, clarifying: list = None) -> str:
        # 调用逻辑
        return result

ProviderRegistry.register("my_provider", MyProvider())
```

---

## Template 注册表

| Name | 说明 | 推荐场景 |
|------|------|---------|
| `weekly_close` | 周五盘中版 | 周五 18:00 运行 |
| `weekend_recap` | 周六完整复盘版（默认） | 周六 08:00 运行 |
| `ad_hoc` | 通用调研版 | 临时研究 |

### 新增 Template

```python
from references.src.registry import TemplateRegistry, TimeContext

def my_template(data_context: str, tc: TimeContext) -> str:
    return "自定义 prompt fragment..."

TemplateRegistry.register("my_template", my_template)
```

---

## Profile 注册表

| Name | 过滤规则 | 适用 |
|------|---------|------|
| `dad` | 删除所有 `%` 配比数字 | 稳健型投资者（默认） |
| `generic` | 不过滤 | 临时调研 |

### 新增 Profile

```python
from references.src.registry import ProfileRegistry

class MyProfile:
    @classmethod
    def filter(cls, report_md: str) -> str:
        import re
        return re.sub(r'激进表述', '[已过滤]', report_md)

ProfileRegistry.register("my_profile", MyProfile())
```

---

## 交互式配置（config/schema.json）

当支持 Agent Skills 的平台（如 Hermite）安装此技能时，会根据 `config/schema.json` 自动询问用户配置以下字段：

1. `api_key` — DashScope API Key（加密输入）
2. `email_password` — SMTP 授权码（加密输入）
3. `receiver_email` — 收件人邮箱
4. `template` — 报告模板（枚举选择）
5. `profile` — 受众画像（枚举选择）

---

## 依赖

```txt
# requirements.txt
akshare>=1.14.0
dashscope>=1.20.0
markdown2>=2.5.0
pdfkit>=1.0.0

# 系统包
sudo apt install wkhtmltopdf fonts-noto-cjk
```

---

## 目录结构

```
fund-report/
├── SKILL.md                    ← 本文件（Agent Skills 标准）
├── README.md                   ← 人类友好说明
├── Dockerfile                  ← 容器化部署
├── requirements.txt            ← Python 依赖
├── .gitignore
│
├── config/
│   └── schema.json             ← 交互式配置 schema
│
├── references/                ← 代码资源（SKILL.md 引用这里）
│   ├── run_and_send_pipeline.py   ← 主入口
│   └── src/
│       ├── __init__.py
│       ├── registry.py           ← Registry 层
│       ├── research_agent.py      ← TimeContext + Mixin
│       ├── data_agent.py          ← AkShare 数据
│       └── email_agent.py         ← 邮件发送
│
└── output/                    ← 报告输出（gitignore）
```
