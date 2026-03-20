#!/usr/bin/env python3
"""
Data Agent 完整版
- 基于系统性诊断确认可用的数据源
- 正确处理数据排序方向（oldest→newest vs newest→oldest）
- 正确处理列索引
"""
import akshare as ak
import pandas as pd
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ============== 工具函数 ==============

def safe_fetch(name: str, fn, *args, retries: int = 2, delay: float = 1.0, **kwargs) -> Optional[pd.DataFrame]:
    """安全获取数据，自动重试"""
    for attempt in range(retries):
        try:
            result = fn(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and not result.empty:
                print(f"  ✅ {name}: {result.shape[0]}行")
                return result
            print(f"  ⚠️ {name}: 空数据")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                print(f"  ❌ {name}: {str(e)[:70]}")
                return None


def validate_unit_suspicious(value: float, field: str, threshold: float = 1e8) -> bool:
    """
    数据单位校验：检查数值是否异常小（可能单位写错：万 vs 亿）。
    返回 True 表示数据可疑，False 表示正常。

    A股主力资金正常都是 亿 为单位，单个行业净流入几亿~几百亿。
    如果值 < threshold（默认1亿），说明可能用了万元单位。
    """
    if value is None:
        return False
    if abs(value) < threshold:
        print(f"  ⚠️ [单位警告] 字段「{field}」={value:.0f}，可能单位异常（<{threshold:.0e}视为可疑，疑为万元当亿元）")
        return True
    return False


def get_latest(df: Optional[pd.DataFrame], prefer_tail: bool = True) -> Optional[pd.Series]:
    """
    获取最新一行数据。
    - oldest→newest 排序（如 CPI/PPI/社融/RRR）：用 iloc[0]
    - newest→oldest 排序（如 SHIBOR/LPR）：用 iloc[-1]
    默认 prefer_tail=True：新数据在尾部时使用
    """
    if df is None or df.empty:
        return None
    return df.iloc[-1] if prefer_tail else df.iloc[0]


def find_col(df: pd.DataFrame, *keywords: str) -> Optional[str]:
    """根据关键词找列名（按优先级返回第一个匹配）"""
    cols = df.columns.tolist()
    for kw in keywords:
        for c in cols:
            if kw in str(c):
                return c
    return None


def safe_val(val) -> Optional[float]:
    """安全获取数值"""
    if val is None:
        return None
    try:
        f = float(val)
        return None if pd.isna(f) else f
    except:
        return None


def fmt(val) -> str:
    """格式化显示"""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


# ============== Data Agent 主类 ==============

class DataAgent:
    """全维度数据采集 Agent"""

    def __init__(self):
        self.data: Dict = {}
        self.warnings: List[str] = []

    def run(self) -> Dict:
        print("[Data Agent] 开始数据采集...")

        # 1. 宏观数据
        print("\n[宏观数据]")
        self.data["macro"] = {
            "pmi": self._get_pmi(),
            "cpi": self._get_cpi(),
            "ppi": self._get_ppi(),
            "m2": self._get_m2(),
            "lpr": self._get_lpr(),
            "shibor": self._get_shibor(),
            "rrr": self._get_rrr(),
            "new_financial_credit": self._get_new_financial_credit(),
            "fx": self._get_fx(),
        }

        # 2. 市场数据
        print("\n[市场数据]")
        self.data["market"] = {
            "indices": self._get_index_performance(),
            "sectors": self._get_sector_performance(),
            "north_flow": self._get_north_flow(),
            "margin": self._get_margin(),
        }

        # 3. 基金池
        print("\n[基金池]")
        self.data["fund_pool"] = self._get_fund_pool()
        self.data["fund_details"] = self._get_fund_details()

        # 4. 政策新闻
        print("\n[政策新闻]")
        self.data["policy_news"] = self._search_policy_news()

        self.data["fetch_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.data["warnings"] = self.warnings

        self._print_summary()
        return self.data

    # ========== 宏观数据 ==========

    def _get_pmi(self) -> Optional[Dict]:
        """
        PMI：制造业 + 非制造业
        数据排序：oldest→newest（最新在 iloc[0]）
        列: ['月份', '制造业-指数', '制造业-同比增长', '非制造业-指数', '非制造业-同比增长']
        """
        df = safe_fetch("PMI", ak.macro_china_pmi)
        if df is None:
            return None
        # 最新数据在 iloc[0]（oldest→newest）
        r = get_latest(df, prefer_tail=False)
        return {
            "制造业PMI": safe_val(r.iloc[1]),
            "非制造业PMI": safe_val(r.iloc[3]),
            "日期": str(r.iloc[0]),
            "来源": "国家统计局",
        }

    def _get_cpi(self) -> Optional[Dict]:
        """
        CPI：居民消费价格指数
        数据排序：oldest→newest（最新在 iloc[0]）
        列: ['月份', '全国-当月', '全国-同比增长', '全国-环比增长', '全国-累计', ...]
        """
        df = safe_fetch("CPI", ak.macro_china_cpi)
        if df is None:
            return None
        r = get_latest(df, prefer_tail=False)
        return {
            "当月指数": safe_val(r.iloc[1]),
            "同比": safe_val(r.iloc[2]),
            "环比": safe_val(r.iloc[3]),
            "日期": str(r.iloc[0]),
            "来源": "国家统计局",
        }

    def _get_ppi(self) -> Optional[Dict]:
        """
        PPI：工业生产者出厂价格指数
        数据排序：oldest→newest（最新在 iloc[0]）
        列: ['月份', '当月', '当月同比增长', '累计']
        """
        df = safe_fetch("PPI", ak.macro_china_ppi)
        if df is None:
            return None
        r = get_latest(df, prefer_tail=False)
        return {
            "当月指数": safe_val(r.iloc[1]),
            "同比": safe_val(r.iloc[2]),
            "累计": safe_val(r.iloc[3]),
            "日期": str(r.iloc[0]),
            "来源": "国家统计局",
        }

    def _get_m2(self) -> Optional[Dict]:
        """
        M2 货币供应量
        数据排序：newest→oldest（iloc[0]最新）
        使用 macro_china_money_supply（macro_china_supply_of_money 有 demjson bug）
        """
        # 先试旧接口，出错则用备选
        df = safe_fetch("M2广义货币", ak.macro_china_supply_of_money)
        if df is None:
            # 备选接口
            df = safe_fetch("M2月度", ak.macro_china_money_supply)
            if df is None:
                return None
            # 列名不同：['月份', '货币和准货币(M2)-数量(亿元)', ...]
            r = get_latest(df, prefer_tail=True)  # newest→oldest
            return {
                "M2绝对量_亿元": safe_val(r.iloc[1]),
                "M2同比": safe_val(r.iloc[2]),
                "M1绝对量": safe_val(r.iloc[3]),
                "M1同比": safe_val(r.iloc[4]),
                "日期": str(r.iloc[0]),
                "来源": "中国人民银行",
            }
        # 原始接口
        r = get_latest(df, prefer_tail=False)
        return {
            "M2绝对量_亿元": safe_val(r.iloc[1]),
            "M2同比": safe_val(r.iloc[2]),
            "M1绝对量": safe_val(r.iloc[3]),
            "M1同比": safe_val(r.iloc[4]),
            "日期": str(r.iloc[0]),
            "来源": "中国人民银行",
        }

    def _get_lpr(self) -> Optional[Dict]:
        """
        LPR 贷款市场报价利率
        数据排序：oldest→newest（最新在 iloc[-1]）
        列: ['TRADE_DATE', 'LPR1Y', 'LPR5Y', 'RATE_1', 'RATE_2']
        """
        df = safe_fetch("LPR", ak.macro_china_lpr)
        if df is None:
            return None
        # 最新在 tail
        r = get_latest(df, prefer_tail=True)
        return {
            "1年期LPR": safe_val(r.iloc[1]),
            "5年期LPR": safe_val(r.iloc[2]),
            "日期": str(r.iloc[0]),
            "来源": "中国人民银行",
        }

    def _get_shibor(self) -> Optional[Dict]:
        """
        SHIBOR 银行间拆借利率
        数据排序：newest→oldest（最新在 iloc[-1]）
        列: ['日期', 'O/N-定价', 'O/N-涨跌幅', '1W-定价', '1W-涨跌幅', ...]
        """
        df = safe_fetch("SHIBOR", ak.macro_china_shibor_all)
        if df is None:
            return None
        r = get_latest(df, prefer_tail=True)
        return {
            "隔夜O/N": safe_val(r.iloc[1]),
            "1周": safe_val(r.iloc[3]),
            "1月": safe_val(r.iloc[13]) if len(r) > 13 else None,
            "日期": str(r.iloc[0]),
            "来源": "全国银行间同业拆借中心",
        }

    def _get_rrr(self) -> Optional[Dict]:
        """
        存款准备金率
        数据排序：oldest→newest（iloc[0]最新，iloc[-1]最旧）
        列: [公布时间, 生效时间, 大型机构-调整前, 大型机构-调整后, 调整幅度, ...]
        """
        df = safe_fetch("存款准备金率", ak.macro_china_reserve_requirement_ratio)
        if df is None:
            return None
        r = get_latest(df, prefer_tail=False)
        return {
            "大型机构_调整后": safe_val(r.iloc[3]),
            "中小机构_调整后": safe_val(r.iloc[6]) if len(r) > 6 else None,
            "公布时间": str(r.iloc[0]),     # 公布时间
            "生效时间": str(r.iloc[1]),     # 生效时间（更重要的日期）
            "调整幅度": safe_val(r.iloc[4]),
            "来源": "中国人民银行",
        }

    def _get_new_financial_credit(self) -> Optional[Dict]:
        """
        社会融资规模
        数据排序：oldest→newest（最新在 iloc[0]）
        列: ['月份', '当月', '当月-同比增长', '当月-环比增长', '累计', '累计-同比增长']
        """
        df = safe_fetch("社融", ak.macro_china_new_financial_credit)
        if df is None:
            return None
        r = get_latest(df, prefer_tail=False)
        return {
            "当月_亿元": safe_val(r.iloc[1]),
            "当月同比": safe_val(r.iloc[2]),
            "累计": safe_val(r.iloc[4]),
            "日期": str(r.iloc[0]),
            "来源": "中国人民银行",
        }

    def _get_fx(self) -> Optional[Dict]:
        """
        美元/人民币汇率
        """
        df = safe_fetch("汇率", ak.fx_spot_quote)
        if df is None:
            return None
        usd_row = df[df.iloc[:, 0].astype(str).str.contains("USD/CNY", na=False)]
        if usd_row is None or usd_row.empty:
            return None
        r = get_latest(usd_row, prefer_tail=True)
        return {
            "USD_CNY买价": safe_val(r.iloc[1]),
            "USD_CNY卖价": safe_val(r.iloc[2]),
            "来源": "中国外汇交易中心",
        }

    # ========== 市场数据 ==========

    def _get_index_performance(self) -> List[Dict]:
        """
        主要指数表现
        使用 stock_zh_index_daily（不依赖 eastmoney push）
        指数代码: sh000001=上证, sz399001=深证, sz399006=创业板, sh000300=沪深300, sh000016=上证50
        """
        # 上证、深证、创业板、沪深300、上证50、科创50
        index_map = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
            "sh000300": "沪深300",
            "sh000016": "上证50",
        }
        results = []
        for symbol, name in index_map.items():
            df = safe_fetch(f"指数_{name}", ak.stock_zh_index_daily, symbol=symbol)
            if df is not None and not df.empty:
                # 数据按日期升序排列（最旧→最新）
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                close = safe_val(latest.get("close", 0))
                prev_close = safe_val(prev.get("close", 0))
                if close and prev_close:
                    change = round(close - prev_close, 2)
                    change_pct = round((change / prev_close) * 100, 2)
                    results.append({
                        "name": name,
                        "code": symbol,
                        "close": close,
                        "change": change,
                        "change_pct": change_pct,
                        "date": str(latest.get("date", "")),
                    })
        return results

    def _get_sector_performance(self) -> Dict:
        """
        申万行业涨跌 + 主力资金流
        使用 stock_board_industry_summary_ths（替代 eastmoney push 版）
        """
        gainers, losers = [], []
        inflow, outflow = [], []

        # 申万行业涨跌排行（thunderscores）
        df = safe_fetch("申万行业涨跌", ak.stock_board_industry_summary_ths)
        if df is not None:
            change_col = find_col(df, "涨跌幅")
            name_col = find_col(df, "板块", "行业", "名称")
            flow_col = find_col(df, "净流入")
            if change_col and name_col:
                df_sorted = df.sort_values(change_col, ascending=False)
                gainers = [
                    {"行业": str(row[name_col]), "涨跌幅": f"{safe_val(row[change_col]):.2f}%"}
                    for _, row in df_sorted.head(10).iterrows()
                    if safe_val(row[change_col]) is not None
                ]
                losers = [
                    {"行业": str(row[name_col]), "涨跌幅": f"{safe_val(row[change_col]):.2f}%"}
                    for _, row in df_sorted.tail(10).iterrows()
                    if safe_val(row[change_col]) is not None
                ]
            # 主力资金流
            if flow_col:
                df_sorted = df.sort_values(flow_col, ascending=False)
                for _, row in df_sorted.iterrows():
                    v = safe_val(row[flow_col])
                    if v is not None and v > 0:
                        inflow.append({"行业": str(row[name_col]), "主力净流入": round(v, 0)})
                    elif v is not None and v < 0:
                        outflow.append({"行业": str(row[name_col]), "主力净流出": round(abs(v), 0)})

        return {
            "涨跌幅前10": gainers,
            "涨跌幅后10": losers,
            "主力净流入": inflow[:5],
            "主力净流出": outflow[:5],
        }

    def _get_north_flow(self) -> Optional[Dict]:
        """
        北向资金 - 优先使用历史日线数据（收盘后汇总），避免盘中快照误导。
        数据来源:
          - 主要: ak.stock_hsgt_hist_em（历史日线，有"当日成交净买额"）
          - 备选: ak.stock_hsgt_fund_flow_summary_em（今日盘中快照，仅报告中午前参考）
        """
        # 优先取历史日线数据（最近一个有净买额的交易日）
        df_hist = safe_fetch("北向资金历史", ak.stock_hsgt_hist_em, symbol="北向资金")
        result = {
            "日期": None,
            "沪股通_净买入_亿": None,
            "深股通_净买入_亿": None,
            "来源": "港交所/上交所",
            "备注": None,
        }

        if df_hist is not None:
            # 找最新一个有净买额的数据行（最近完整交易日）
            valid = df_hist[df_hist["当日成交净买额"].notna()]
            if not valid.empty:
                latest = valid.iloc[-1]
                result["日期"] = str(latest["日期"])
                result["沪股通_净买入_亿"] = None   # 历史日线数据是合计北向，暂不拆分
                result["深股通_净买入_亿"] = None
                # 记录合计值
                net = safe_val(latest["当日成交净买额"])
                result["北向合计_净买入_亿"] = round(net, 2) if net is not None else None

        # 如果历史数据陈旧（超过5个交易日仍无数据），说明数据暂不可用
        if result["日期"]:
            from datetime import datetime, timedelta
            try:
                latest_date = datetime.strptime(str(result["日期"])[:10], "%Y-%m-%d")
                days_diff = (datetime.now() - latest_date).days
                if days_diff > 5:
                    result["备注"] = f"数据暂不可用（最近完整数据为{result['日期']}，距今{days_diff}个交易日）"
                    result["日期"] = None
                    result["北向合计_净买入_亿"] = None
            except Exception:
                pass

        # 无论历史数据是否有效，仍补充今日盘中快照（仅供参考）
        df_today = safe_fetch("北向资金_今日盘中", ak.stock_hsgt_fund_flow_summary_em)
        if df_today is not None:
            cols = df_today.columns.tolist()
            # 找沪股通北向和深股通北向
            sh_df = df_today[df_today["板块"].astype(str).str.contains("沪股通", na=False) &
                             df_today["资金方向"].astype(str).str.contains("北向", na=False)]
            sz_df = df_today[df_today["板块"].astype(str).str.contains("深股通", na=False) &
                             df_today["资金方向"].astype(str).str.contains("北向", na=False)]
            today_net = 0.0
            for sub_df, label in [(sh_df, "沪股通"), (sz_df, "深股通")]:
                if not sub_df.empty:
                    net_col = find_col(sub_df, "净买", "净流入", "成交净买额")
                    if net_col:
                        v = safe_val(sub_df.iloc[-1][net_col]) or 0
                        today_net += v
            result["今日盘中_北向合计_亿"] = round(today_net, 2)
            if result["备注"] is None and result["日期"] is None:
                result["备注"] = "今日盘中数据，仅供参考；完整日数据请以下一交易日更新为准"
        else:
            result["备注"] = "数据暂不可用，请以下一交易日数据为准"

        return result

    def _get_margin(self) -> Optional[Dict]:
        """
        两融余额 - 合并沪深两市融资余额
        数据来源: ak.macro_china_market_margin_sh (上交所) + ak.macro_china_market_margin_sz (深交所)
        数据排列: oldest→newest (iloc[0]=最旧, iloc[-1]=最新)
        金额单位: 元，需除以1e8转为亿元
        """
        df_sh = safe_fetch("两融余额_沪", ak.macro_china_market_margin_sh)
        df_sz = safe_fetch("两融余额_深", ak.macro_china_market_margin_sz)
        if df_sh is None or df_sz is None:
            return None

        # 数据 oldest→newest，iloc[-1]=最新，iloc[-2]=上日
        r_sh_new = df_sh.iloc[-1]
        r_sh_prev = df_sh.iloc[-2] if len(df_sh) > 1 else r_sh_new
        r_sz_new = df_sz.iloc[-1]
        r_sz_prev = df_sz.iloc[-2] if len(df_sz) > 1 else r_sz_new

        # 融资余额列，单位：元
        sh_new = safe_val(r_sh_new["融资余额"]) or 0
        sh_prev = safe_val(r_sh_prev["融资余额"]) or 0
        sz_new = safe_val(r_sz_new["融资余额"]) or 0
        sz_prev = safe_val(r_sz_prev["融资余额"]) or 0

        total_new = sh_new + sz_new
        total_prev = sh_prev + sz_prev
        date_str = str(r_sh_new["日期"])   # 沪深同日期

        return {
            "融资余额_亿": round(total_new / 1e8, 2),
            "较上日_亿": round((total_new - total_prev) / 1e8, 2),
            "上交所_亿": round(sh_new / 1e8, 2),
            "深交所_亿": round(sz_new / 1e8, 2),
            "日期": date_str,
            "来源": "沪深交易所",
        }

    # ========== 基金池 ==========

    def _get_fund_pool(self) -> List[Dict]:
        """晨星5星基金池"""
        print("  正在获取晨星评级数据...")
        try:
            df = ak.fund_rating_all()
        except Exception as e:
            self.warnings.append(f"晨星评级获取失败: {e}")
            print(f"  ❌ 晨星评级获取失败: {e}")
            return []

        cols = df.columns.tolist()
        code_col = find_col(df, "代码")
        name_col = find_col(df, "简称", "名称")
        type_col = find_col(df, "类型")
        # 重要：优先匹配 '晨星'（更精确），否则匹配任何含'评级'的列
        rating_col = find_col(df, "晨星") or find_col(df, "评级")
        mgr_col = find_col(df, "经理")
        comp_col = find_col(df, "公司")

        if not code_col or not rating_col:
            print(f"  ❌ 列名不匹配: {cols}")
            print(f"     rating_col={rating_col}, code_col={code_col}")
            return []

        try:
            df[rating_col] = pd.to_numeric(df[rating_col], errors="coerce")
            five = df[df[rating_col] == 5.0].copy()
        except Exception as e:
            self.warnings.append(f"5星筛选失败: {e}")
            return []

        if type_col:
            kw = ["混合", "灵活", "平衡", "偏股", "FOF", "股票"]
            mask = five[type_col].astype(str).apply(lambda t: any(k in str(t) for k in kw))
            five = five[mask]

        pool = []
        for _, row in five.head(20).iterrows():
            pool.append({
                "code": str(row.get(code_col, "")),
                "name": str(row.get(name_col, "")),
                "type": str(row.get(type_col, "")) if type_col else "",
                "rating": int(row[rating_col]) if pd.notna(row[rating_col]) else 0,
                "manager": str(row.get(mgr_col, "")) if mgr_col else "",
                "company": str(row.get(comp_col, "")) if comp_col else "",
            })

        print(f"  ✅ 基金池: {len(pool)} 支5星基金")
        return pool

    def _get_fund_details(self) -> List[Dict]:
        """获取基金净值和行业配置（限制10支避免过慢）"""
        pool = self.data.get("fund_pool", [])
        details = []
        for fund in pool[:10]:
            code, name = fund["code"], fund["name"]
            detail = {**fund, "nav": None, "nav_date": None, "top_industry": None}

            # 净值走势
            try:
                df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
                if df_nav is not None and not df_nav.empty:
                    latest = df_nav.iloc[-1]
                    detail["nav"] = safe_val(latest.iloc[1])
                    detail["nav_date"] = str(latest.iloc[0])
            except:
                pass

            # 行业配置
            try:
                df_ind = ak.fund_portfolio_industry_allocation_em(symbol=code)
                if df_ind is not None and not df_ind.empty:
                    detail["top_industry"] = str(df_ind.iloc[0].iloc[1]) if len(df_ind.columns) > 1 else None
            except:
                pass

            details.append(detail)

        return details

    # ========== 政策新闻 ==========

    def _search_policy_news(self) -> List[Dict]:
        """Tavily 搜索政策新闻"""
        try:
            key = subprocess.run(
                ["pass", "show", "hermes/tavily-api-key"],
                capture_output=True, text=True, check=True
            ).stdout.strip().split("\n")[0]
        except:
            print("  ❌ Tavily API Key 未配置")
            return []

        import requests
        queries = [
            "中国货币政策最新动态 2026年3月",
            "A股市场政策 证监会 央行 利好",
            "财政政策产业政策 两会 最新",
        ]
        results = []
        for q in queries:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={"api_key": key, "query": q, "max_results": 3},
                    timeout=15
                )
                if resp.status_code == 200:
                    for r in resp.json().get("results", [])[:3]:
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("content", "")[:200],
                        })
            except Exception as e:
                print(f"  ❌ Tavily: {q[:20]} - {str(e)[:50]}")
        print(f"  ✅ 政策新闻: {len(results)} 条")
        return results[:9]

    # ========== 摘要 & 导出 ==========

    def _print_summary(self):
        m = self.data["macro"]
        mk = self.data["market"]
        print(f"\n[采集摘要]")
        ok = lambda d: "✅" if d else "❌"
        print(f"  宏观: PMI({ok(m.get('pmi'))}) CPI({ok(m.get('cpi'))}) "
              f"PPI({ok(m.get('ppi'))}) M2({ok(m.get('m2'))}) "
              f"LPR({ok(m.get('lpr'))}) SHIBOR({ok(m.get('shibor'))}) "
              f"汇率({ok(m.get('fx'))}) 社融({ok(m.get('new_financial_credit'))})")
        print(f"  市场: 指数({len(mk.get('indices', []))}支) "
              f"行业({len(mk.get('sectors', {}).get('涨跌幅前10', []))}条) "
              f"北向({ok(mk.get('north_flow'))}) 两融({ok(mk.get('margin'))})")
        print(f"  基金: {len(self.data.get('fund_pool', []))} 支池 | "
              f"{len(self.data.get('fund_details', []))} 支详情")
        print(f"  新闻: {len(self.data.get('policy_news', []))} 条")
        if self.warnings:
            print(f"  警告({len(self.warnings)}): " + "; ".join(self.warnings[:3]))

    def export_for_research(self) -> str:
        """导出给 Deep Research 的格式化数据"""
        m = self.data.get("macro", {})
        mk = self.data.get("market", {})
        funds = self.data.get("fund_pool", [])
        details = self.data.get("fund_details", [])
        policy = self.data.get("policy_news", [])

        lines = []
        lines.append(f"【数据采集时间】{self.data.get('fetch_time')} | 来源: AkShare / 东方财富 / 天天基金网 / Tavily")
        lines.append("")

        # 一、宏观经济
        lines.append("=" * 65)
        lines.append("一、宏观经济数据")
        lines.append("=" * 65)

        def mac(key: str, label: str):
            d = m.get(key)
            if not d:
                lines.append(f"【{label}】暂无数据")
                return
            date = d.get("日期", "")
            parts = [f"{k}={fmt(v)}" for k, v in d.items()
                     if k not in ("日期", "来源") and v is not None]
            lines.append(f"【{label}】（{date}）{' | '.join(parts)} | {d.get('来源','')}")

        mac("pmi", "制造业与非制造业PMI")
        mac("cpi", "CPI居民消费价格指数")
        mac("ppi", "PPI工业生产者出厂价格指数")
        mac("m2", "M2广义货币供应量")
        mac("lpr", "LPR贷款市场报价利率")
        mac("shibor", "SHIBOR银行间拆借利率")
        mac("rrr", "存款准备金率")
        mac("new_financial_credit", "社会融资规模")
        mac("fx", "USD/CNY汇率")
        lines.append("")

        # 二、市场数据
        lines.append("=" * 65)
        lines.append("二、主要指数与行业表现")
        lines.append("=" * 65)

        indices = mk.get("indices", [])
        if indices:
            for idx in indices:
                sign = "+" if idx["change_pct"] >= 0 else ""
                lines.append(
                    f"【{idx['name']}】收盘={idx['close']} | "
                    f"涨跌={sign}{idx['change']} ({sign}{idx['change_pct']}%)"
                )
        else:
            lines.append("【主要指数】暂无数据")

        sectors = mk.get("sectors", {})
        if sectors.get("涨跌幅前10"):
            lines.append("")
            lines.append("【申万行业涨幅前10】")
            for i, s in enumerate(sectors["涨跌幅前10"], 1):
                lines.append(f"  {i:2d}. {s['行业']:15s} {s['涨跌幅']}")
        if sectors.get("涨跌幅后10"):
            lines.append("")
            lines.append("【申万行业跌幅前10】")
            for i, s in enumerate(sectors["涨跌幅后10"], 1):
                lines.append(f"  {i:2d}. {s['行业']:15s} {s['涨跌幅']}")

        flow_in = sectors.get("主力净流入", [])
        flow_out = sectors.get("主力净流出", [])
        if flow_in:
            lines.append("")
            lines.append("【主力资金净流入前5】（单位：亿元）")
            for item in flow_in:
                val_raw = safe_val(item.get("主力净流入"))
                # AkShare thunder 数据单位是万元，需要转换为亿元（÷10000）
                val_yi = round(val_raw / 10000.0, 2) if val_raw is not None else None
                unit_note = ""
                if val_yi is not None:
                    # 校验：单个行业主力净流入，正常范围在 0.1~50亿元，超出提示核实
                    if val_yi > 100 or val_yi < -100:
                        print(f"  ⚠️ [金额核实] {item['行业']} 主力净流入={val_yi}亿元，请确认数据来源是否正确")
                        unit_note = " ⚠️请核实"
                lines.append(
                    f"  {item['行业']:15s} +{val_yi:.2f} 亿元{unit_note}" if val_yi else f"  {item['行业']} N/A"
                )
        if flow_out:
            lines.append("")
            lines.append("【主力资金净流出前5】（单位：亿元）")
            for item in flow_out:
                val_raw = safe_val(item.get("主力净流出"))
                # AkShare thunder 数据单位是万元，需要转换为亿元（÷10000）
                val_yi = round(val_raw / 10000.0, 2) if val_raw is not None else None
                unit_note = ""
                if val_yi is not None:
                    if val_yi > 100 or val_yi < -100:
                        print(f"  ⚠️ [金额核实] {item['行业']} 主力净流出={val_yi}亿元，请确认数据来源是否正确")
                        unit_note = " ⚠️请核实"
                lines.append(
                    f"  {item['行业']:15s} {val_yi:.2f} 亿元{unit_note}" if val_yi else f"  {item['行业']} N/A"
                )

        nf = mk.get("north_flow")
        lines.append("")
        if nf and nf.get("北向合计_净买入_亿") is not None:
            # 有可用数据
            net = nf.get("北向合计_净买入_亿", 0)
            sign = "+" if net > 0 else ""
            lines.append(f"【北向资金】（{nf.get('日期','N/A')}）合计净买入: {sign}{net:.2f}亿元")
        elif nf and nf.get("备注"):
            # 数据不可用，明确告知 AI 跳过此字段
            lines.append(f"【北向资金】（{nf.get('备注','')}）此数据暂不可用，分析时无需引用。")
        else:
            lines.append("【北向资金】暂无数据，分析时无需引用此字段。")

        margin = mk.get("margin")
        if margin:
            chg = margin.get("较上日_亿", 0)
            sign = "+" if chg and chg > 0 else ""
            lines.append(f"【两融余额】（{margin.get('日期','N/A')}）"
                         f"{fmt(margin.get('融资余额_亿'))}亿元 | 较上日: {sign}{fmt(chg)}亿元")
        lines.append("")

        # 三、政策新闻
        lines.append("=" * 65)
        lines.append("三、最新政策与市场新闻")
        lines.append("=" * 65)
        if policy:
            for i, p in enumerate(policy[:9], 1):
                lines.append(f"【{i}】{p['title']}")
                lines.append(f"   {p['snippet'][:120]}...")
        else:
            lines.append("暂无数据")
        lines.append("")

        # 四、基金池
        lines.append("=" * 65)
        lines.append(f"四、晨星5星基金池（共{len(funds)}支）")
        lines.append("=" * 65)
        lines.append(f"| 基金名称              | 代码    | 类型      | 星级 | 最新净值 | 重仓行业     |")
        lines.append(f"|----------------------|---------|-----------|------|---------|-------------|")
        for f in funds:
            detail = next((d for d in details if d["code"] == f["code"]), {})
            nav_str = fmt(detail.get("nav")) if detail.get("nav") else "N/A"
            ind_str = (detail.get("top_industry") or "N/A")[:12]
            lines.append(
                f"| {f['name'][:20]:20s} | {f['code'][:6]:>6s} | "
                f"{f['type'][:8]:8s} | ⭐×{f['rating']} | {nav_str:>7s} | {ind_str:12s} |"
            )
        lines.append("")
        if self.warnings:
            lines.append("⚠️ 数据采集警告:")
            for w in self.warnings[:5]:
                lines.append(f"  - {w}")

        return "\n".join(lines)
