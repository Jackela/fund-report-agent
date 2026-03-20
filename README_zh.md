# 📊 基金投资周报生成器

> AI 驱动的自动化基金投资分析报告系统 — 数据采集 → 深度研究 → 邮件发送，开箱即用。

[![GitHub Stars](https://img.shields.io/github/stars/Jackela/fund-report-agent)](https://github.com/Jackela/fund-report-agent/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## 功能特性

- **🔍 全自动数据采集** — 通过 AkShare 采集宏观经济指标（PMI/CPI/PPI/M2/LPR）、A股指数、申万行业涨跌、北向资金、两融余额、晨星5星基金池等
- **🧠 深度研究报告生成** — 调用阿里通义千问 Deep Research（Qwen-Deep-Research），结合数据上下文自动生成3000+字结构化分析报告
- **📧 邮件自动发送** — 支持 Cron 定时任务，周六早8点自动生成并发送到指定邮箱
- **🎯 多用户画像支持** — 预设 DadProfile（稳健型，过滤配比数字）和 K7407Profile（成长型，完整内容）
- **⚙️ 配置即代码** — 所有配置集中在 `~/.hermes/fund-report.yaml`，支持多账户、多报告模板
- **🔒 安全第一** — API Key 和密码通过 `pass`（或环境变量）管理，不硬编码

---

## 系统架构

```
数据采集 (AkShare)
    ↓
Prompt 构建 (Template + Profile + TimeContext)
    ↓
AI 深度研究 (阿里通义千问 Deep Research)
    ↓
内容过滤 (Profile 后处理)
    ↓
Markdown → HTML
    ↓
邮件发送 (SMTP)
```

---

## 快速开始

### 环境要求

- Python 3.10+
- [pass](https://www.passwordstore.org/) (可选，密钥管理用)
- AI API Key（阿里通义千问 / DeepSeek / OpenAI 等）

### 1. 安装依赖

```bash
git clone https://github.com/Jackela/fund-report-agent.git
cd fund-report-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置密钥

**方式一：pass store（推荐）**

```bash
pass init your-gpg-id
pass insert hermes/aliyun-api-key      # 阿里云 API Key
pass insert hermes/email-smtp-password  # 邮箱授权码
pass insert hermes/email-config        # SMTP 配置（见下）
```

`pass insert hermes/email-config` 内容格式：
```
smtp_host: smtp.qq.com
smtp_port: 587
username: your-email@qq.com
from_name: 基金报告机器人
```

**方式二：环境变量**

```bash
cp .env.example .env
# 编辑 .env，填入真实值
```

### 3. 运行一次报告

```bash
# 爸的版本（稳健型，过滤配比）
PROFILE=dad TEMPLATE=weekend_recap python3 run_and_send_pipeline.py

# 自己的版本（成长型）
PROFILE=k7407 TEMPLATE=weekend_recap python3 run_and_send_pipeline.py
```

> 首次运行需要 2-5 分钟（数据采集 + AI 生成）

### 4. 设置定时任务（每周自动跑）

#### 方式 A：系统 crontab

```bash
# 每周六早上8点运行
0 8 * * 6 cd /path/to/fund-report-agent && \
  .venv/bin/python3 run_and_send_pipeline.py \
  PROFILE=dad TEMPLATE=weekend_recap >> /var/log/fund-report.log 2>&1
```

#### 方式 B：Hermes Agent Cron（如果你用 Hermes）

```bash
hermes cron create \
  --name "每周六基金报告" \
  --schedule "0 8 * * 6" \
  --prompt "cd /path/to/fund-report-agent && .venv/bin/python3 run_and_send_pipeline.py PROFILE=dad TEMPLATE=weekend_recap"
```

---

## 配置参考

所有配置集中在 `~/.hermes/fund-report.yaml`：

```yaml
profiles:
  dad:
    email: "your-dad@email.com"
    background: "银行从业，稳健型投资者"
    risk_tolerance: "中等"
  k7407:
    email: "your@email.com"
    background: "软件工程师，成长型投资者"
    risk_tolerance: "较高"

jobs:
  - id: weekly-to-dad
    schedule: "0 8 * * 6"       # 每周六 08:00
    profile: dad
    template: weekend_recap
    enabled: true
```

---

## 目录结构

```
.
├── run_and_send_pipeline.py   # 主入口脚本
├── src/
│   ├── config.py              # 配置读取层（SSOT）
│   ├── data_agent.py          # AkShare 数据采集
│   ├── email_agent.py         # 邮件发送
│   ├── registry.py            # Provider/Template/Profile 注册表
│   └── research_agent.py      # AI 研究 Agent
├── references/                 # 备份参考实现
├── Dockerfile                  # Docker 部署
├── requirements.txt
└── .env.example               # 环境变量模板
```

---

## 自定义扩展

### 添加新的 AI Provider

在 `src/registry.py` 中注册：

```python
class MyProvider:
    model = "my-model"
    def research(self, query): ...

ProviderRegistry.register("myprovider", MyProvider)
```

### 添加新的报告模板

在 `src/registry.py` 中添加模板函数：

```python
def my_template(data_context: str, tc: TimeContext) -> str:
    return "【报告结构】..."

TemplateRegistry.register("my_template", my_template)
```

### 添加新的用户画像

```python
class MyProfile:
    @classmethod
    def filter(cls, report_md: str) -> str:
        return report_md  # 自定义过滤逻辑

ProfileRegistry.register("myprofile", MyProfile)
```

---

## 依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| dashscope | ≥1.14 | 阿里云百炼 API |
| akshare | ≥1.13 | A股/宏观数据采集 |
| markdown2 | ≥2.0 | Markdown → HTML |
| pyyaml | ≥6.0 | 配置文件解析 |
| yagmail | ≥0.15 | 邮件发送（可选） |
| pdfkit | ≥1.0 | PDF 生成（可选，需 wkhtmltopdf）|

---

## 免责声明

本项目仅供学习和研究使用。AI 生成的报告仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。

---

## License

MIT © Jackela
