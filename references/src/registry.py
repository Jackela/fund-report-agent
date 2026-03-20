#!/usr/bin/env python3
"""
Registry 层 — 解耦 AI Provider / Template / Profile
符合 AI Coding 最佳实践：接口抽象 + 配置驱动 + 零硬编码

新增 Provider/Template/Profile 只需注册，不改核心引擎。
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Dict, Callable, Any, Optional


# ============================================================
# Pure Data Objects（无逻辑，只有结构）
# ============================================================

class TimeContext:
    """
    时间上下文 — 代码强制计算，禁止 AI 推理星期几。
    所有时间信息由这里注入 prompt，AI 只读不推理。
    """
    WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self, dt: Optional[datetime] = None):
        self.now = dt or datetime.now()
        self.report_dt = self.now.strftime("%Y年%m月%d日 %H:%M")
        self.weekday = self.WEEKDAY_CN[self.now.weekday()]
        self.date_str = self.now.strftime("%Y-%m-%d")
        self.is_weekend = self.now.weekday() >= 5
        self.hour = self.now.hour
        self.is_trading_close = (self.now.weekday() == 4 and self.hour >= 15) \
                                or self.now.weekday() in (5, 6)
        # 计算下一个工作日
        days_ahead = (7 - self.now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 3
        from datetime import timedelta
        next_date = self.now.replace(hour=0, minute=0, second=0, microsecond=0) \
                    + timedelta(days=days_ahead)
        next_wd = self.WEEKDAY_CN[(self.now.weekday() + days_ahead) % 7]
        self.next_trade_day = next_date.strftime("%Y-%m-%d（") + next_wd + "）"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "report_dt": self.report_dt,
            "weekday": self.weekday,
            "date_str": self.date_str,
            "next_trade_day": self.next_trade_day,
            "is_weekend": self.is_weekend,
            "is_trading_close": self.is_trading_close,
        }

    def inject(self) -> str:
        """时间约束 prompt fragment"""
        wd = self.weekday
        rdt = self.report_dt
        ntd = self.next_trade_day
        return (
            "\n\n【时间约束 — 禁止违反】\n"
            "- 报告生成时间：" + rdt + "（" + wd + "）\n"
            "- 今天就是【" + wd + "】，今天是【" + wd + "】！禁止写错星期几。\n"
            "- 下一个交易日：" + ntd + "\n"
        )


class DataUnitValidator:
    """
    数据单位校验 — Layer 1.5 Validation
    检查主力资金/北向资金等数值是否异常小（万元 vs 亿元）
    """
    @staticmethod
    def check(value: float, field: str, threshold: float = 1e8) -> bool:
        """threshold=1e8 即 1亿。主力资金 < 1亿视为可疑。"""
        if value is None:
            return False
        if abs(value) < threshold:
            print(f"  ⚠️ [单位警告] {field}={value:.0f}，可能单位异常（<{threshold:.0e}）")
            return True
        return False


# ============================================================
# Registry Pattern（运行时注入，零硬编码）
# ============================================================

class _Registry:
    """通用注册表基类 — 每个子类有独立的 _items"""
    _items: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, item: Any) -> None:
        if not hasattr(cls, '_items') or cls._items is _Registry._items:
            cls._items = {}  # 确保子类有独立字典
        cls._items[name] = item

    @classmethod
    def get(cls, name: str) -> Any:
        items = getattr(cls, '_items', {})
        if name not in items:
            available = list(items.keys())
            raise ValueError(f"[{cls.__name__}] 未注册: {name}，可用: {available}")
        return items[name]

    @classmethod
    def list_all(cls) -> Dict[str, Any]:
        return dict(getattr(cls, '_items', {}))

    @classmethod
    def names(cls) -> list:
        return list(getattr(cls, '_items', {}).keys())


class ProviderRegistry(_Registry):
    """AI Provider 注册表。"""
    _items = {}  # 独立字典


class TemplateRegistry(_Registry):
    """报告模板注册表。"""
    _items = {}  # 独立字典


class ProfileRegistry(_Registry):
    """受众画像注册表。"""
    _items = {}  # 独立字典


# ============================================================
# 具体实现（新增只需在这里注册）
# ============================================================

# --- Provider 实现 ---
class AliyunProvider:
    """阿里通义千问 Deep Research Provider"""

    def __init__(self, model: str = "qwen-deep-research"):
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import subprocess, os
            result = subprocess.run(
                ["pass", "show", "hermes/aliyun-api-key"],
                capture_output=True, text=True, check=True
            )
            api_key = result.stdout.strip().split("\n")[0]
            os.environ["DASHSCOPE_API_KEY"] = api_key
            import dashscope
            from dashscope import Generation
            self._client = Generation
            print(f"[AliyunProvider] ✅ 就绪 (model={self.model})")

    def research(self, query: str, clarifying: list = None) -> str:
        """两步式 Deep Research"""
        self._ensure_client()

        # 步骤1：收集反问
        messages = [{"role": "user", "content": query}]
        collected = []
        try:
            for resp in self._client.call(
                model=self.model, messages=messages,
                stream=True, enable_feedback=True,
            ):
                out = getattr(resp, "output", None) or {}
                msg = out.get("message", {})
                phase = msg.get("phase", "")
                content = msg.get("content", "")
                if phase == "question":
                    print(f"  [反问] {content[:60]}...")
                    collected.append(content)
                elif phase == "think":
                    print(f"  [思考] {content[:40]}...")
        except Exception as e:
            print(f"[AliyunProvider] ⚠️ 步骤1异常: {e}")

        # 步骤2：生成报告
        if clarifying if clarifying is not None else collected:
            qt = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(collected))
            messages = [
                {"role": "user", "content": query},
                {"role": "user", "content": f"研究反问：\n{qt}\n\n请生成完整报告。"}
            ]
        else:
            messages = [{"role": "user", "content": query},
                        {"role": "user", "content": "请生成完整报告。"}]

        chunks = []
        try:
            for resp in self._client.call(model=self.model, messages=messages, stream=True):
                out = getattr(resp, "output", None) or {}
                msg = out.get("message", {})
                content = msg.get("content", "")
                if content:
                    print(content, end="", flush=True)
                    chunks.append(content)
        except Exception as e:
            print(f"[AliyunProvider] ❌ 报告生成异常: {e}")
            return ""
        return "".join(chunks)


# --- Template 实现 ---
def weekly_close_template(data_context: str, tc: TimeContext) -> str:
    """
    周五收盘版模板 — 五交易日完整复盘
    """
    return (
        "【报告结构 — 周五收盘完整复盘版】\n\n"
        "## 一、宏观经济与政策周报\n"
        "基于提供的宏观数据（PMI、CPI/PPI、M2、汇率、LPR）：\n"
        "1. 本周制造业与非制造业PMI表现及经济趋势判断\n"
        "2. 通胀环境分析\n"
        "3. 货币金融环境（M2增速、汇率走向、LPR调整信号）\n"
        "4. 政策面：结合最新政策新闻，分析对A股的影响方向\n"
        "5. 给出宏观经济环境的**综合评分（1-5星）**\n\n"
        "## 二、A股市场技术面与资金面分析\n"
        "1. 主要指数一周表现：上证/深证/创业板/沪深300 的整周涨跌幅\n"
        "2. 领涨与领跌板块：本周最强和最弱行业，分析资金轮动逻辑\n"
        "3. 资金面分析：北向资金周累计、两融余额变化、主力资金流向\n"
        "4. 技术面：本周支撑/压力位，量价配合情况\n"
        "5. 市场情绪判断\n\n"
        "## 三、基金池深度分析\n"
        "1. 基金池整体特征\n"
        "2. 今年来/近1年表现最强的3支基金及原因\n"
        "3. 最符合'均衡配置+稳健成长'目标的基金\n"
        "4. 重点关注的2-3支基金（代码、名称、主要特点）\n\n"
        "## 四、综合投资建议（定性分析）\n"
        "1. 宏观策略：对不同类型基金（权益/债券/混合）的整体判断\n"
        "2. 板块方向：值得重点关注和应相对谨慎的板块\n"
        "3. 基金关注方向：重点基金类型（不给具体配比）\n"
        "4. 当前位置风险与机会概述\n\n"
        "## 五、风险提示\n"
        "1. 宏观风险 2. 市场风险 3. 基金特有风险 4. 风险控制建议\n"
        "【写作要求】全文不少于3000字，每条判断标注置信度🟢🟡🔴\n"
    )


def weekend_recap_template(data_context: str, tc: TimeContext) -> str:
    """
    周六早盘版模板 — 上周五收盘数据的完整回顾
    数据截止：上周五收盘（最完整的一周数据）
    """
    return (
        "【报告结构 — 周六完整复盘版（上周五收盘数据）】\n"
        "本报告基于上周收盘后的完整数据编写，数据质量最高。\n\n"
        "## 一、宏观经济与政策回顾\n"
        "1. 重点解读本周发布的宏观数据（PMI、CPI/PPI等）\n"
        "2. 货币与金融环境（M2、汇率、LPR）\n"
        "3. 政策面对A股的影响分析\n"
        "4. 宏观综合评分（1-5星）\n\n"
        "## 二、上周A股全周复盘\n"
        "1. 主要指数整周表现（附每日涨跌分解）\n"
        "2. 行业轮动：领涨/领跌板块及背后逻辑\n"
        "3. 资金面：北向资金周净流入/流出、两融变化\n"
        "4. 技术面：整周量价特征、关键支撑压力\n\n"
        "## 三、基金池综合评估\n"
        "1. 晨星五星基金池整体表现\n"
        "2. 本周/本月表现突出的基金及原因\n"
        "3. 均衡稳健型投资者应关注的基金类型\n\n"
        "## 四、投资方向定性分析\n"
        "1. 当前市场环境下各类基金的整体判断\n"
        "2. 值得关注的板块方向\n"
        "3. 下周重点观察事项\n\n"
        "## 五、风险提示\n"
        "【写作要求】全文不少于3000字，每条判断标注置信度🟢🟡🔴\n"
    )


def ad_hoc_template(data_context: str, tc: TimeContext) -> str:
    """
    临时调研模板 — 通用版，不预设结构
    """
    return (
        "【报告结构 — 通用调研版】\n"
        "请根据提供的数据，进行系统性分析并输出结构化报告。\n"
        "结构：\n"
        "1. 核心发现摘要（3-5条）\n"
        "2. 数据支撑的详细分析\n"
        "3. 趋势判断与风险提示\n"
        "4. 相关建议（如适用）\n"
        "【写作要求】分析必须有数据支撑，语言简洁专业\n"
    )


# --- Profile 实现 ---
class DadProfile:
    """
    稳健型投资者（爸）— 硬性过滤：删除配比数字
    """
    _RATIO_PATTERNS = [
        re.compile(r'\d{1,3}%\w*仓'),
        re.compile(r'配置[^\s，,，。；;]{0,20}\d{1,3}%'),
        re.compile(r'超配[^\s，,，。；;]{0,20}\d{1,3}%'),
        re.compile(r'低配[^\s，,，。；;]{0,20}\d{1,3}%'),
        re.compile(r'占比\d{1,3}%'),
        re.compile(r'\d{1,3}[/:]\d{1,3}\s*比例'),
        re.compile(r'\d+%'),
    ]

    @classmethod
    def filter(cls, report_md: str) -> str:
        original = report_md
        for pattern in cls._RATIO_PATTERNS:
            report_md = pattern.sub('[具体比例由投资者自行判断]', report_md)
        if report_md != original:
            print(f"[DadProfile] ⚠️ 已过滤配比数字")
        return report_md


class K7407Profile:
    """
    k7407 — 软件工程师，技术背景，成长型投资者
    - 风险承受较高，关注科技赛道（AI/半导体/新能源）
    - 偏好简洁直接的语言风格，少废话
    - 不过滤配比数字（能自行判断）
    """
    @classmethod
    def filter(cls, report_md: str) -> str:
        return report_md  # 不过滤，技术型用户自己判断


class GenericProfile:
    """
    通用型 — 不过滤，保留原始内容
    """
    @classmethod
    def filter(cls, report_md: str) -> str:
        return report_md


# ============================================================
# 注册（引擎启动时自动执行）
# ============================================================

def initialize():
    """初始化所有注册表。import 时自动调用。"""
    # Provider
    ProviderRegistry.register("aliyun", AliyunProvider())

    # Template
    TemplateRegistry.register("weekly_close", weekly_close_template)
    TemplateRegistry.register("weekend_recap", weekend_recap_template)
    TemplateRegistry.register("ad_hoc", ad_hoc_template)

    # Profile
    ProfileRegistry.register("dad", DadProfile)
    ProfileRegistry.register("k7407", K7407Profile)
    ProfileRegistry.register("generic", GenericProfile)


# 自动初始化
initialize()
