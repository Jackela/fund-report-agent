#!/usr/bin/env python3
"""
Research Agent - 调用阿里通义千问 Deep Research 生成专业研报
基于全维度真实数据，生成机构级周报

架构：Mixin 模式
  Layer 1: Core Engine（通用 topic-agnostic）
  Layer 2: Template Mixin（运行时注入 prompt fragment）
  Layer 3: Profile Mixin（运行时注入后处理过滤器）
"""
import subprocess
import os
import sys
import re
from datetime import datetime


# ===================== Mixin 层 =====================


class TimeContext:
    """
    Layer 1 的一部分：强制时间上下文注入。
    禁止 AI 自己算星期几，所有时间信息由这里计算后注入。
    """
    WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self):
        self.now = datetime.now()
        self.report_dt = self.now.strftime("%Y年%m月%d日 %H:%M")
        self.weekday = self.WEEKDAY_CN[self.now.weekday()]
        self.date_str = self.now.strftime("%Y-%m-%d")
        self.is_weekend = self.now.weekday() >= 5
        # 计算下一个交易日（如果今天是周五，下一个是周一）
        days_ahead = (7 - self.now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 3  # 周末重复运行 → 周三
        next_date = self.now.replace(hour=0, minute=0, second=0, microsecond=0) \
                    + __import__("datetime").timedelta(days=days_ahead)
        next_weekday_name = self.WEEKDAY_CN[(self.now.weekday() + days_ahead) % 7]
        self.next_trade_day = next_date.strftime("%Y-%m-%d（") + next_weekday_name + "）"

    def as_dict(self) -> dict:
        return {
            "report_dt": self.report_dt,
            "weekday": self.weekday,
            "date_str": self.date_str,
            "next_trade_day": self.next_trade_day,
            "is_weekend": self.is_weekend,
        }

    def inject_warning(self) -> str:
        """注入时间强约束 prompt fragment"""
        wd = self.weekday
        rdt = self.report_dt
        ntd = self.next_trade_day
        return (
            "\n\n【时间强约束 — 禁止违反】\n"
            "- 报告生成时间：" + rdt + "（" + wd + "）\n"
            "- 今天就是【" + wd + "】，今天是【" + wd + "】！\n"
            "- 报告里**任何地方**提到星期几，都必须是【" + wd + "】或对应的工作日。\n"
            "- 绝对禁止写'本周三'、'本周四'等错误表述（今天是" + wd + "）。\n"
            "- 下一个交易日：" + ntd + "\n"
        )


class DadProfileMixin:
    """
    Layer 3: Profile Mixin（稳健型投资者版本）
    硬性过滤：删除所有具体配置比例，替换为定性描述。
    """
    # 匹配各种比例/配比格式
    _RATIO_PATTERNS = [
        re.compile(r'\d{1,3}%\w*仓'),               # 25%仓位、40%权益
        re.compile(r'配置[^\s，,，。；;]{0,20}\d{1,3}%'),   # 配置25%、配置40%债券
        re.compile(r'超配[^\s，,，。；;]{0,20}\d{1,3}%'),   # 超配30%
        re.compile(r'低配[^\s，,，。；;]{0,20}\d{1,3}%'),   # 低配20%
        re.compile(r'占比\d{1,3}%'),                  # 占比40%
        re.compile(r'\d+%'),                           # 最宽泛兜底：任何数字+%，用于捕获遗漏
        re.compile(r'[\d七二三四五六八九十百]{1,3}[/:][\d七二三四五六八九十百]{1,3}\s*比例'),  # 七三比例、5:5比例
    ]

    @classmethod
    def filter(cls, report_md: str) -> str:
        """后处理过滤：删除所有具体配比数字"""
        original = report_md
        for pattern in cls._RATIO_PATTERNS:
            report_md = pattern.sub('[具体比例由投资者自行判断]', report_md)

        if report_md != original:
            print(f"[Dad Profile] ⚠️ 过滤了 {sum(1 for _ in cls._RATIO_PATTERNS)} 类配比数字 → 已替换为定性描述")
        return report_md


def get_api_key(pass_path: str) -> str:
    result = subprocess.run(
        ["pass", "show", pass_path],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip().split("\n")[0]


class ResearchAgent:
    """AI 研究 Agent - 调用阿里通义千问 Deep Research"""

    def __init__(self, model="qwen-deep-research"):
        self.model = model

        api_key = get_api_key("hermes/aliyun-api-key")
        os.environ["DASHSCOPE_API_KEY"] = api_key

        try:
            import dashscope
            from dashscope import Generation
            self.dashscope = dashscope
            self.Generation = Generation
        except ImportError:
            print("[Research Agent] ❌ dashscope 未安装，运行: pip install dashscope")
            sys.exit(1)

        print(f"[Research Agent] ✅ DashScope SDK 就绪 (model: {model})")

    def run(self, data_context: str, profile: str = "dad") -> str:
        """
        主流程：调用阿里通义千问 Deep Research 生成完整专业研报

        Args:
            data_context: 全维度数据上下文
            profile: 'dad'（稳健型投资者）或 'generic'（通用）
        """
        print("[Research Agent] 📝 构建专业研报 prompt...")

        # Layer 1: TimeContext 强制注入（禁止 AI 自己算星期几）
        tc = TimeContext()
        print(f"[Research Agent] ⏰ 时间上下文: {tc.report_dt}（{tc.weekday}）")

        prompt = self._build_prompt(data_context, tc)

        # 两步式调用（Deep Research 特性）
        print("[Research Agent] 🔍 步骤1：发起研究请求...")
        clarifying = self._collect_clarifying_questions(prompt)
        print(f"[Research Agent] 收到 {len(clarifying)} 个反问...")

        print("[Research Agent] 📄 步骤2：生成完整研究报告...")
        report = self._generate_final_report(prompt, clarifying)

        # Layer 3: Profile Mixin 后处理过滤
        if profile == "dad":
            print("[Research Agent] 🛡️ 应用 DadProfileMixin 过滤...")
            report = DadProfileMixin.filter(report)

        print("[Research Agent] ✅ 报告生成完成")
        return report

    def _build_prompt(self, data_context: str, tc: TimeContext) -> str:
        # 强制注入时间约束（在所有内容最前面，后面任何 prompt 段落都不得与此处矛盾）
        time_block = tc.inject_warning()

        base = (
            "你是一位资深基金投资分析师，服务于高净值个人投资者（咱爸，银行从业背景，稳健型投资者）。\n\n"
            + time_block + "\n\n"
            "【数据时效性说明 — 必须在报告中明确标注每项数据的截止时间】\n"
            "本报告生成于" + tc.report_dt + "（" + tc.weekday + "），数据时效性如下，请据此判断数据适用范围：\n"
            "- ✅ 可用数据：截至" + tc.report_dt + "之前已公布的宏观数据（PMI、LPR、M2、CPI/PPI等）、两融余额、ETF份额等\n"
            "- ⚠️ 盘中数据：指数点位、行业涨跌幅为" + tc.report_dt + "上午或盘中数据，**下午可能有较大波动，收盘数据需以当日15:00为准**\n"
            "- ❌ 尚未公布（生成时不可用）：当日北向资金全日数据、基金净值（通常晚间才公布）\n"
            "- 请在报告正文中，对每项市场数据标注'截至X月X日X:XX（盘中/收盘/早盘）'\n\n"
            "【数据处理原则】\n"
            "- 如果某个数据字段标注'暂无数据'或'此数据暂不可用'，分析时应主动说明'由于XX数据暂不可用，无法对该维度做出判断'，而不是捏造或推测数据。\n"
            "- 对于基金净值、指数涨跌幅等具体数值，必须严格引用数据原文，不得自行推断具体数字。\n"
            "- 保持客观中立：数据说话，数据缺失的部分如实告知读者，不留隐患。\n\n"
            "请基于以下**全维度真实数据**，生成一份**机构级周度投资研究报告**。\n\n"
            "---\n"
            + data_context + "\n"
            "---\n\n"
            "【报告结构要求】严格按以下五部分输出，每部分内容不少于300字：\n\n"
            "## 一、宏观经济与政策周报\n"
            "基于提供的宏观数据（PMI、CPI/PPI、M2、汇率、LPR）：\n"
            "1. 本周制造业与非制造业PMI表现及经济趋势判断\n"
            "2. 通胀环境分析（CPI/PPI剪刀差及对政策的影响）\n"
            "3. 货币金融环境（M2增速、汇率走向、LPR调整信号）\n"
            "4. 政策面：结合最新政策新闻，分析对A股的影响方向\n"
            "5. 给出宏观经济环境的**综合评分（1-5星）**和**简要结论**\n\n"
            "## 二、A股市场技术面与资金面分析\n"
            "基于提供的指数数据、行业涨跌、资金流向数据：\n"
            "1. 主要指数一周表现：上证/深证/创业板/沪深300 的涨跌幅分析\n"
            "2. 领涨与领跌板块：找出最强和最弱行业，分析资金轮动逻辑\n"
            "3. 资金面分析：北向资金、两融余额、主力资金流向的综合判断\n"
            "4. 技术面：主要支撑/压力位，量价配合情况\n"
            "5. 市场情绪判断：**风险偏好（高/中/低）、外资动向（流入/流出）**\n\n"
            "## 三、基金池深度分析\n"
            "基于20支晨星5星基金的数据：\n"
            "1. 基金池整体特征：类型分布、仓位范围、收益表现\n"
            "2. 今年来/近1年表现最强的3支基金及原因分析\n"
            "3. 哪些基金当前最符合'均衡配置+稳健成长'的投资目标\n"
            "4. 重点关注：结合当前市场风格，最值得关注的2-3支基金（给出代码、名称、主要特点）\n\n"
            "## 四、综合投资建议（定性分析为主，不给具体配比数字）\n"
            "1. **宏观策略**：当前市场环境下，对不同类型基金（权益/债券/混合）的整体判断\n"
            "2. **板块方向**：哪些行业/主题当前值得重点关注，哪些应相对谨慎\n"
            "3. **基金关注方向**：结合基金池数据，指出值得进一步了解的重点基金类型\n"
            "4. **择时提示**：当前位置的整体风险与机会概述\n\n"
            "## 五、风险提示\n"
            "列出当前投资面临的主要风险：\n"
            "1. 宏观风险（海外加息、地缘政治等）\n"
            "2. 市场风险（估值偏高、情绪过热等）\n"
            "3. 基金特有风险（规模过大、换手率过低等）\n"
            "4. 风险控制建议\n\n"
            "---\n"
            "【写作要求】\n"
            "1. 所有分析必须有数据支撑，引用数据时注明数据名称\n"
            "2. 今天是【" + tc.weekday + "】，任何情况下都不要写错星期几\n"
            "3. 每条判断标注置信度：🟢高置信 / 🟡中置信 / 🔴低置信\n"
            "4. 语言风格：专业但不晦涩，适合银行背景的投资者阅读\n"
            "5. 全文不少于3000字，结构清晰，层次分明\n"
            "6. **严禁在报告中出现具体配置比例（如'25%'、'40%权益'等），只做定性方向分析**\n"
        )
        return base


    def _collect_clarifying_questions(self, prompt: str) -> list:
        """收集反问（Deep Research 步骤1）"""
        messages = [{"role": "user", "content": prompt}]
        collected = []

        try:
            for resp in self.Generation.call(
                model=self.model,
                messages=messages,
                stream=True,
                enable_feedback=True,
            ):
                if hasattr(resp, 'output') and resp.output:
                    msg = resp.output.get('message', {})
                    phase = msg.get('phase', '')
                    content = msg.get('content', '')

                    if phase == 'question':
                        print(f"  [反问] {content[:80]}...")
                        collected.append(content)
                    elif phase == 'think':
                        print(f"  [思考] {content[:60]}...")

        except Exception as e:
            print(f"[Research Agent] ⚠️ 步骤1 异常: {e}，跳过")
            collected = []

        return collected

    def _generate_final_report(self, prompt: str, clarifying: list) -> str:
        """生成最终报告（Deep Research 步骤2）"""
        if clarifying:
            questions_text = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(clarifying))
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": f"研究过程中的反问：\n{questions_text}\n\n请基于以上数据和反问，生成完整的机构级投资研究报告。"}
            ]
        else:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": "请生成完整的机构级投资研究报告。"}
            ]

        chunks = []
        try:
            for resp in self.Generation.call(
                model=self.model,
                messages=messages,
                stream=True,
            ):
                if hasattr(resp, 'output') and resp.output:
                    msg = resp.output.get('message', {})
                    content = msg.get('content', '')
                    if content:
                        print(content, end='', flush=True)
                        chunks.append(content)

        except Exception as e:
            print(f"[Research Agent] ❌ 报告生成异常: {e}")
            return ""

        return ''.join(chunks)
