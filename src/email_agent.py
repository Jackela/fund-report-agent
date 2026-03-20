#!/usr/bin/env python3
"""
Email Agent - 发送报告邮件
所有配置统一从 ~/.hermes/fund-report.yaml 读取（通过 config.py）
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import Header
from datetime import datetime

from config import get_smtp_config, get_recipients, get_default_profile


class EmailAgent:
    """邮件发送 Agent"""

    def __init__(self):
        cfg = get_smtp_config()
        self.smtp_host = cfg["smtp_host"]
        self.smtp_port = cfg["smtp_port"]
        self.username = cfg["username"]
        self.from_name = cfg["from_name"]
        self.password = cfg["password"]

    def run(self, to_emails: list[str], subject: str, html_body: str,
            attachments: list = None) -> bool:
        """
        发送邮件
        to_emails:  收件人邮箱列表
        subject:    邮件主题
        html_body:  HTML 格式的邮件正文
        attachments: 附件路径列表
        """
        print(f"[Email Agent] 📧 准备发送邮件到 {to_emails}...")

        msg = MIMEMultipart("mixed")
        msg["From"] = self.username
        msg["To"] = ", ".join(to_emails)
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
                server.sendmail(self.username, to_emails, msg.as_string())
            print(f"[Email Agent] ✅ 邮件发送成功！")
            return True
        except Exception as e:
            print(f"[Email Agent] ❌ 发送失败: {e}")
            return False


def send_fund_report(report_html: str, pdf_path: str = None,
                     profile: str = None) -> bool:
    """
    便捷包装 — 收件人从 config.yaml 的 profiles 读取

    profile: 从 ~/.hermes/fund-report.yaml 读取对应邮箱
             默认读取 PROFILE 环境变量 或 default_profile
    """
    if profile is None:
        profile = os.environ.get("PROFILE", get_default_profile())

    recipients = get_recipients(profile)
    if not recipients:
        raise ValueError(f"profile '{profile}' 没有配置邮箱")

    agent = EmailAgent()
    subject = f"📊 基金投资周报 | {datetime.now().strftime('%Y年%m月%d日')} | {profile}"

    attachments = [pdf_path] if pdf_path and os.path.exists(pdf_path) else None

    return agent.run(
        to_emails=recipients,
        subject=subject,
        html_body=report_html,
        attachments=attachments,
    )
