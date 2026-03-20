#!/usr/bin/env python3
"""
Email Agent - 发送报告邮件给咱爸
"""
import subprocess
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from datetime import datetime


def get_password():
    result = subprocess.run(
        ["pass", "show", "hermes/email-smtp-password"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")[0]


def get_smtp_config():
    result = subprocess.run(
        ["pass", "show", "hermes/email-config"],
        capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().split("\n")
    config = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            config[k.strip()] = v.strip()
    return config


class EmailAgent:
    """邮件发送 Agent"""

    def __init__(self):
        self.config = get_smtp_config()
        self.smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = int(self.config.get("smtp_port", "587"))
        self.username = self.config.get("username", "")
        self.from_name = self.config.get("from_name", "基金报告机器人")
        self.password = get_password()

    def run(self, to_email: str, subject: str, html_body: str, attachments: list = None) -> bool:
        """
        发送邮件
        to_email: 收件人邮箱
        subject: 邮件主题
        html_body: HTML 格式的邮件正文
        attachments: 附件路径列表
        """
        print(f"[Email Agent] 📧 准备发送邮件到 {to_email}...")

        msg = MIMEMultipart("mixed")
        msg["From"] = self.username  # QQ邮箱只接受纯邮箱格式
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8").encode()
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
        msg["Message-ID"] = f"<fund-report-{datetime.now().strftime('%Y%m%d%H%M%S')}@qq.com>"

        # HTML 正文
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

        # 附件
        if attachments:
            for filepath in attachments:
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
                    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(filepath)}"'
                    msg.attach(part)
                    print(f"[Email Agent] ✅ 添加附件: {os.path.basename(filepath)}")

        # 发送
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, [to_email], msg.as_string())
            print(f"[Email Agent] ✅ 邮件发送成功！")
            return True
        except Exception as e:
            print(f"[Email Agent] ❌ 发送失败: {e}")
            return False


def send_fund_report(report_html: str, pdf_path: str = None, to_email: str = None):
    """便捷包装"""
    if to_email is None:
        result = subprocess.run(
            ["pass", "show", "hermes/dad-email"],
            capture_output=True, text=True, check=True
        )
        to_email = result.stdout.strip().split("\n")[0]

    agent = EmailAgent()
    subject = f"📊 基金投资周报 | {datetime.now().strftime('%Y年%m月%d日')}"

    attachments = [pdf_path] if pdf_path and os.path.exists(pdf_path) else None

    return agent.run(
        to_email=to_email,
        subject=subject,
        html_body=report_html,
        attachments=attachments
    )
