"""第三层：宏观与政策环境分析。

两个子维度：
  - 宏观经济周期（PMI / GDP / CPI / M2）
  - 政策信号（基于近期新闻关键词的粗略政策温度）
"""
import pandas as pd

from .config import WEIGHTS
from .utils import clamp, latest_value, range_score, weighted

_POS_POLICY = ["降准", "降息", "政策利好", "支持", "扶持", "补贴", "放宽", "鼓励", "规划", "振兴", "利好"]
_NEG_POLICY = ["收紧", "监管", "处罚", "整治", "限制", "遏制", "风险警示", "降温", "约谈"]


def _cycle_score(macro):
    """宏观周期打分：PMI 权重最高，GDP 与 CPI 辅助。"""
    pmi = latest_value(macro.get("pmi"), "制造业-指数", "制造业-指数(经季节调整)")
    gdp = latest_value(macro.get("gdp"), "国内生产总值-同比增长", "国内生产总值-同比")
    cpi = latest_value(macro.get("cpi"), "全国-同比增长", "全国-同比")
    m2 = latest_value(macro.get("m2"), "货币和准货币(M2)-同比增长", "M2-同比增长")

    s_pmi = range_score(pmi, [(-1e9, 48, 35), (48, 50, 50), (50, 52, 70), (52, 55, 82), (55, 1e9, 90)], 50)
    s_gdp = range_score(gdp, [(-1e9, 2, 40), (2, 4, 55), (4, 6, 70), (6, 8, 85), (8, 1e9, 90)], 55)
    s_cpi = range_score(cpi, [(-1e9, 0, 45), (0, 2, 60), (2, 3, 85), (3, 5, 65), (5, 1e9, 40)], 60)
    s_m2 = range_score(m2, [(-1e9, 8, 55), (8, 12, 75), (12, 1e9, 60)], 60) if m2 is not None else None

    score, _ = weighted([(s_pmi, 35), (s_gdp, 30), (s_cpi, 25), (s_m2, 10)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {"PMI": pmi, "GDP增速(%)": gdp, "CPI(%)": cpi, "M2增速(%)": m2},
    }


def _policy_score(news_df):
    """基于个股近期新闻的政策温度（粗略，仅供方向性参考）。"""
    if news_df is None or news_df.empty:
        return 55
    title_col = "新闻标题" if "新闻标题" in news_df.columns else news_df.columns[0]
    text = " ".join(news_df[title_col].astype(str).tolist())
    pos = sum(text.count(k) for k in _POS_POLICY)
    neg = sum(text.count(k) for k in _NEG_POLICY)
    if pos + neg == 0:
        return 55
    return round(clamp(55 + (pos - neg) * 8))


def analyze_macro(macro, news_df):
    """第三层总入口。macro 为 data.get_macro_data() 返回的 dict。"""
    cycle = _cycle_score(macro)
    policy = _policy_score(news_df)

    w = WEIGHTS["macro"]
    score, _ = weighted([(cycle["score"], w["cycle"]), (policy, w["policy"])])

    return {
        "cycle": cycle,
        "policy": {"score": policy},
        "score": round(score, 1) if score is not None else None,
    }
