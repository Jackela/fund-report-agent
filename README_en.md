# 📊 Fund Report Agent

> AI-powered automated fund investment weekly report generator — data collection → deep research → email delivery, ready to run.

[![GitHub Stars](https://img.shields.io/github/stars/Jackela/fund-report-agent)](https://github.com/Jackela/fund-report-agent/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## Features

- **🔍 Fully Automated Data Collection** — Collects macro indicators (PMI/CPI/PPI/M2/LPR), A-share indices, Shenwan industry data, northbound funds, margin balance, and Morningstar 5-star fund pools via AkShare
- **🧠 Deep Research Report Generation** — Uses Alibaba Cloud's Qwen-Deep-Research model to generate 3000+ word structured analysis reports with data context
- **📧 Automatic Email Delivery** — Cron-scheduled to run every Saturday 8 AM and send reports to configured email addresses
- **🎯 Multi-Profile Support** — DadProfile (conservative, filters allocation ratios) and K7407Profile (growth-oriented, full content)
- **⚙️ Configuration as Code** — All config centralized in `~/.hermes/fund-report.yaml`, supporting multiple accounts and report templates
- **🔒 Security First** — API keys and passwords managed via `pass` or environment variables, never hardcoded

---

## System Architecture

```
Data Collection (AkShare)
    ↓
Prompt Construction (Template + Profile + TimeContext)
    ↓
AI Deep Research (Alibaba Cloud Qwen-Deep-Research)
    ↓
Content Filtering (Profile post-processing)
    ↓
Markdown → HTML
    ↓
Email Delivery (SMTP)
```

---

## Quick Start

### Requirements

- Python 3.10+
- [pass](https://www.passwordstore.org/) (optional, for key management)
- AI API Key (Alibaba Cloud / DeepSeek / OpenAI etc.)

### 1. Install Dependencies

```bash
git clone https://github.com/Jackela/fund-report-agent.git
cd fund-report-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Secrets

**Option A: pass store (recommended)**

```bash
pass init your-gpg-id
pass insert hermes/aliyun-api-key      # Alibaba Cloud API Key
pass insert hermes/email-smtp-password  # Email authorization code
pass insert hermes/email-config         # SMTP config (see below)
```

`pass insert hermes/email-config` content:
```
smtp_host: smtp.qq.com
smtp_port: 587
username: your-email@qq.com
from_name: Fund Report Bot
```

**Option B: Environment Variables**

```bash
cp .env.example .env
# Edit .env and fill in real values
```

### 3. Run a Report

```bash
# Dad's version (conservative, filtered ratios)
PROFILE=dad TEMPLATE=weekend_recap python3 run_and_send_pipeline.py

# Your own version (growth-oriented)
PROFILE=k7407 TEMPLATE=weekend_recap python3 run_and_send_pipeline.py
```

> First run takes 2-5 minutes (data collection + AI generation)

### 4. Set Up Cron Job (Automatic Weekly Run)

#### Option A: System crontab

```bash
# Every Saturday 8 AM
0 8 * * 6 cd /path/to/fund-report-agent && \
  .venv/bin/python3 run_and_send_pipeline.py \
  PROFILE=dad TEMPLATE=weekend_recap >> /var/log/fund-report.log 2>&1
```

#### Option B: Hermes Agent Cron (if you use Hermes)

```bash
hermes cron create \
  --name "Weekly Fund Report to Dad" \
  --schedule "0 8 * * 6" \
  --prompt "cd /path/to/fund-report-agent && .venv/bin/python3 run_and_send_pipeline.py PROFILE=dad TEMPLATE=weekend_recap"
```

---

## Configuration

All configuration is centralized in `~/.hermes/fund-report.yaml`:

```yaml
profiles:
  dad:
    email: "dad@example.com"
    background: "Bank employee, conservative investor"
    risk_tolerance: "medium"
  k7407:
    email: "you@example.com"
    background: "Software engineer, growth investor"
    risk_tolerance: "high"

jobs:
  - id: weekly-to-dad
    schedule: "0 8 * * 6"       # Every Saturday 08:00
    profile: dad
    template: weekend_recap
    enabled: true
```

---

## Project Structure

```
.
├── run_and_send_pipeline.py   # Main entry script
├── src/
│   ├── config.py              # Config reader (SSOT)
│   ├── data_agent.py          # AkShare data collection
│   ├── email_agent.py         # Email delivery
│   ├── registry.py            # Provider/Template/Profile registry
│   └── research_agent.py      # AI research agent
├── references/                 # Backup reference implementations
├── Dockerfile                  # Docker deployment
├── requirements.txt
└── .env.example               # Environment variable template
```

---

## Customization

### Add a New AI Provider

Register in `src/registry.py`:

```python
class MyProvider:
    model = "my-model"
    def research(self, query): ...

ProviderRegistry.register("myprovider", MyProvider)
```

### Add a New Report Template

Add template function in `src/registry.py`:

```python
def my_template(data_context: str, tc: TimeContext) -> str:
    return "【Report Structure】..."

TemplateRegistry.register("my_template", my_template)
```

### Add a New User Profile

```python
class MyProfile:
    @classmethod
    def filter(cls, report_md: str) -> str:
        return report_md  # custom filtering logic

ProfileRegistry.register("myprofile", MyProfile)
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| dashscope | ≥1.14 | Alibaba Cloud API |
| akshare | ≥1.13 | A-share / macro data |
| markdown2 | ≥2.0 | Markdown → HTML |
| pyyaml | ≥6.0 | Config file parsing |
| yagmail | ≥0.15 | Email sending (optional) |
| pdfkit | ≥1.0 | PDF generation (optional) |

---

## Disclaimer

This project is for learning and research purposes only. AI-generated reports are for reference only and do not constitute any investment advice. Investments involve risks; decisions should be made cautiously.

---

## License

MIT © Jackela
