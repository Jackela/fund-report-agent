#!/usr/bin/env python3
"""
Fund Report Pipeline — Agent Skills 标准入口
references/run_and_send_pipeline.py

用法:
  PROVIDER=aliyun TEMPLATE=weekend_recap PROFILE=dad python3 run_and_send_pipeline.py
  TEMPLATE=ad_hoc PROFILE=generic python3 run_and_send_pipeline.py

配置统一从 ~/.hermes/fund-report.yaml 读取
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# ===================== 配置 =====================
OUTPUT_DIR = os.environ.get(
    "FUND_REPORT_OUTPUT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
)
MIN_REPORT_SIZE = 1024

# 运行时配置（环境变量注入）
PROVIDER = os.environ.get("PROVIDER", "aliyun")
TEMPLATE = os.environ.get("TEMPLATE", "weekend_recap")
PROFILE = os.environ.get("PROFILE", "dad")
# =============================================


def get_latest_report(output_dir: str) -> tuple[str, int]:
    """找最大报告文件（跳过空文件/失败文件）"""
    candidates = []
    for f in sorted(Path(output_dir).glob("report_*.md"),
                    key=lambda x: -x.stat().st_size):
        size = f.stat().st_size
        if size < MIN_REPORT_SIZE:
            print(f"  ⏭ 跳过空文件: {f.name} ({size}b)")
            continue
        candidates.append((size, str(f), f.name))
        break

    if not candidates:
        raise FileNotFoundError(
            f"❌ 未找到有效报告（>{MIN_REPORT_SIZE} bytes）\n"
            f"   请先运行: python3 run_and_send_pipeline.py"
        )

    size, filepath, name = candidates[0]
    print(f"\n📄 选中: {name} ({size/1024:.1f}KB)")
    return filepath, size


def md_to_html(md_path: str) -> str:
    """Markdown → HTML（使用 markdown2）"""
    try:
        import markdown2
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "markdown2"], check=True)
        import markdown2

    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read().strip()

    html_body = markdown2.markdown(md, extras=["fenced-code-blocks", "tables"])

    css = (
        "body{font-family:Microsoft YaHei,sans-serif;max-width:720px;margin:0 auto;"
        "padding:20px;line-height:1.7;color:#222}"
        "h1{font-size:22px;color:#1a1a2e;border-bottom:2px solid #1a1a2e;padding-bottom:8px}"
        "h2{font-size:18px;color:#16213e;margin-top:24px}"
        "h3{font-size:15px;color:#0f3460}"
        "table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}"
        "th{background:#1a1a2e;color:#fff;padding:8px 12px}"
        "td{border:1px solid #ddd;padding:7px 12px}"
        "tr:nth-child(even){background:#f9f9f9}"
        ".disclaimer{background:#fff3cd;border:1px solid #ffeeba;border-radius:6px;"
        "padding:12px;font-size:13px;color:#856404;margin-top:20px}"
    )

    today_str = datetime.now().strftime("%Y年%m月%d日")
    html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head><meta charset=\"utf-8\"><style>" + css + "</style></head>\n"
        "<body>\n"
        "<h1>📊 开放式基金每周研究报告</h1>\n"
        "<p><strong>生成日期</strong>: " + today_str + "</p>\n"
        "<hr/>\n"
        "<div class=\"disclaimer\">\n"
        "⚠️ <strong>免责声明</strong>：本报告由 AI 自动生成，数据来源："
        "AkShare / 东方财富 / 天天基金网 / Tavily。"
        "本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。\n"
        "</div>\n"
        "<hr/>\n"
        + html_body + "\n"
        "</body>\n"
        "</html>"
    )
    return html


def main():
    print("=" * 56)
    print(f"  Fund Report Pipeline")
    print(f"  Provider={PROVIDER}  Template={TEMPLATE}  Profile={PROFILE}")
    print("=" * 56)

    # 1. 设置 Python path（先于此文件的 import 动态生效）
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(root_dir, "src")
    sys.path.insert(0, src_dir)            # fund_report/src/  ← 找 config.py
    sys.path.insert(0, root_dir)           # fund_report/       ← 找 src.data_agent
    sys.path.insert(0, os.path.dirname(__file__))  # references/

    # 2. API Key（统一从 config.yaml → pass 读取）
    from config import get_api_key as _get_api_key
    try:
        api_key = _get_api_key(PROVIDER)
        os.environ["DASHSCOPE_API_KEY"] = api_key
        print("✅ API Key 读取成功")
    except Exception as e:
        print(f"❌ API Key 读取失败: {e}")
        sys.exit(1)

    # 3. 数据采集
    from src.data_agent import DataAgent

    print("\n[步骤1] 采集数据...")
    agent = DataAgent()
    agent.run()
    data_context = agent.export_for_research()
    print(f"✅ 数据采集完成 ({len(data_context)} 字)")

    # 3. Registry 加载
    from src.registry import (
        ProviderRegistry, TemplateRegistry, ProfileRegistry, TimeContext
    )

    print(f"\n[步骤2] Registry 加载...")
    print(f"  Provider: {PROVIDER}")
    print(f"  Template: {TEMPLATE}")
    print(f"  Profile:  {PROFILE}")

    # 4. TimeContext
    tc = TimeContext()
    print(f"  ⏰ {tc.report_dt}（{tc.weekday}）")

    # 5. 构建 Prompt（Core + Template）
    template_fn = TemplateRegistry.get(TEMPLATE)
    template_chunk = template_fn(data_context, tc)

    from src.research_agent import TimeContext as OldTC
    tc_old = OldTC()

    base_prompt = (
        "你是一位资深基金投资分析师，服务于高净值个人投资者（咱爸，银行从业背景，稳健型投资者）。\n\n"
        + tc_old.inject_warning() + "\n\n"
        "【数据时效性说明】\n"
        "- ✅ 可用数据：截至" + tc.report_dt + "之前已公布的宏观数据、两融余额等\n"
        "- ⚠️ 盘中数据：指数点位为盘中数据，收盘前可能有较大波动\n"
        "- ❌ 尚未公布：当日北向资金全日数据、基金净值\n"
        "- 请对每项市场数据标注'截至X月X日X:XX（盘中/收盘）'\n\n"
        "【数据处理原则】\n"
        "- 数据缺失时如实说明，不捏造推测\n"
        "- 严格引用数据原文，不自行推断数字\n\n"
        "---\n"
        + data_context + "\n"
        "---\n\n"
        + template_chunk + "\n\n"
        "【写作要求】\n"
        "1. 今天是【" + tc.weekday + "】，禁止写错星期几\n"
        "2. 每条判断标注置信度：🟢高置信 / 🟡中置信 / 🔴低置信\n"
        "3. 语言风格：专业但不晦涩，适合银行背景的投资者\n"
        "4. 全文不少于3000字\n"
        "5. **严禁出现具体配置比例（如'25%'、'40%'等），只做定性分析**\n"
    )

    # 6. AI 生成
    print(f"\n{'=' * 56}")
    print(f"[步骤3] 调用 {PROVIDER} Deep Research（{TEMPLATE} 模板）...")
    print("需要 1-5 分钟，请耐心等待...")
    print("=" * 56 + "\n")

    provider = ProviderRegistry.get(PROVIDER)
    raw_report = provider.research(base_prompt)

    # 7. Profile 后处理
    if raw_report:
        profile_cls = ProfileRegistry.get(PROFILE)
        report = profile_cls.filter(raw_report)
    else:
        report = ""
        print("[⚠️] AI 返回为空，跳过 profile 过滤")

    print("\n✅ 报告生成完成")

    # 8. 保存 Markdown
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(OUTPUT_DIR, f"report_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 开放式基金每周研究报告\n\n")
        f.write(f"**生成日期**: {datetime.now().strftime('%Y年%m月%d日')}\n\n")
        f.write(report)
    print(f"✅ 报告已保存: {md_path} ({len(report)} 字)")

    # 9. HTML 转换
    latest_path, size = get_latest_report(OUTPUT_DIR)
    print("\n[步骤4] Markdown → HTML...")
    html_body = md_to_html(latest_path)
    print(f"✅ HTML 转换完成 ({len(html_body)} 字节)")

    # 10. 发送邮件
    print("\n" + "=" * 56)
    print("[步骤5] 发送邮件...")
    print("=" * 56 + "\n")

    from src.email_agent import send_fund_report
    success = send_fund_report(report_html=html_body)

    print(f"\n{'=' * 56}")
    print(f"{'🎉 全部完成！' if success else '❌ 邮件发送失败'}")
    print(f"   Provider={PROVIDER} Template={TEMPLATE} Profile={PROFILE}")
    print(f"{'=' * 56}")


if __name__ == "__main__":
    main()
