# 📊 基金投资周报生成器

> AI 驱动的自动化基金投资分析报告系统 — 数据采集 → 深度研究 → 邮件发送。本项目由 AI 辅助维护；配置、离线检查与实际执行分开。

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

配置文件默认读取 `~/.hermes/fund-report.yaml`。`HERMES_HOME` 可指定目录，
`FUND_REPORT_CONFIG` 可指定单个 YAML 文件；当前入口不自动加载 `.env`。
API Key 和 SMTP 凭据由配置中的 pass 引用读取，运行机器需要安装 pass。

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
  PROFILE=dad TEMPLATE=weekend_recap .venv/bin/python3 run_and_send_pipeline.py >> /var/log/fund-report.log 2>&1
```

#### 方式 B：Hermes Agent Cron（如果你用 Hermes）

```bash
hermes cron create \
  --name "每周六基金报告" \
  --schedule "0 8 * * 6" \
  --prompt "cd /path/to/fund-report-agent && PROFILE=dad TEMPLATE=weekend_recap .venv/bin/python3 run_and_send_pipeline.py"
```

---

## 配置参考

所有配置集中在 `~/.hermes/fund-report.yaml`：

```yaml
provider:
  active: aliyun
  aliyun:
    api_key_pass_key: hermes/aliyun-api-key
defaults:
  profile: dad
  template: weekend_recap
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
├── run_and_send_pipeline.py   # 兼容入口，委托 src.pipeline
├── src/
│   ├── pipeline.py            # 唯一执行链与 --check-config
│   ├── config.py              # 配置读取层（SSOT）
│   ├── data_agent.py          # AkShare 数据采集
│   ├── email_agent.py         # 邮件发送
│   ├── registry.py            # Provider/Template/Profile 注册表
│   └── research_agent.py      # AI 研究 Agent
├── references/               # 旧路径兼容包装，委托 src
├── Dockerfile                  # Docker 部署
├── requirements.txt
└── .env.example               # 环境变量模板
```

---

## 开发与离线验证

先执行 `python -m unittest discover -s tests -v`。测试使用临时 YAML 和替身，
不会采集外部数据、调用模型、读取 pass 或连接 SMTP。

`python run_and_send_pipeline.py --check-config` 只检查 YAML、注册名称和选择，
输出 provider/template/profile，不验证凭据或外部服务。选择顺序是
环境变量 `PROVIDER`、`TEMPLATE`、`PROFILE` 优先，其次 YAML 默认值。
根入口、`src/main.py` 和 `references` 入口均调用 `src.pipeline.main`；
只在 `src/` 修改实现。普通执行会采集、调用模型并发信，需在授权的宿主环境验证。
CI 在 master 分支及其 PR 上运行离线契约检查；通过不代表实际基金数据或报告结论正确。

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
