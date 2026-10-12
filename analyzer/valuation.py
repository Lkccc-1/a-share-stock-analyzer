"""第二层：估值水平分析。

三个子维度：
  - 绝对估值（PE / PB / 股息率）
  - 历史分位数（当前估值处于自身历史的位置）
  - 成长性价比（PEG = PE / 净利增速）
"""
import pandas as pd

from .config import WEIGHTS
from .utils import latest_value, num, range_score, weighted


def _latest_positive(df):
    """百度估值序列 (date, value) → 最新值（仅正数）。"""
    if df is None or df.empty or "value" not in df.columns:
        return None
    d = df.copy()
    if "date" in d.columns:
        d = d.sort_values("date")
    s = pd.to_numeric(d["value"], errors="coerce").dropna()
    s = s[s > 0]
    return float(s.iloc[-1]) if not s.empty else None


def _percentile(df):
    """最新值在其近五年历史中的分位数（0-100），越小越便宜。"""
    if df is None or df.empty or "value" not in df.columns:
        return None
    d = df.copy()
    if "date" in d.columns:
        d = d.sort_values("date")
    s = pd.to_numeric(d["value"], errors="coerce").dropna()
    s = s[s > 0]
    if s.empty:
        return None
    latest = float(s.iloc[-1])
    return float((s <= latest).mean()) * 100.0


def _score_absolute(pe, pb, ps, dv):
    """绝对估值：PE/PB/PS/股息率，越低越好（亏损 PE、负 PB/PS 单独低分处理）。"""
    if pe is None or pe <= 0:
        s_pe = 25  # 无法用 PE 衡量（亏损）
    else:
        s_pe = range_score(pe, [(-1e9, 10, 90), (10, 20, 80), (20, 30, 68), (30, 50, 48), (50, 80, 32), (80, 1e9, 22)], 50)

    if pb is not None and pb <= 0:
        s_pb = 25  # 负净资产
    else:
        s_pb = range_score(pb, [(-1e9, 1, 86), (1, 2, 76), (2, 4, 60), (4, 8, 44), (8, 1e9, 30)], 50) if pb is not None else None

    if ps is not None and ps <= 0:
        s_ps = 25
    else:
        s_ps = range_score(ps, [(-1e9, 1, 90), (1, 3, 78), (3, 6, 62), (6, 10, 45), (10, 1e9, 30)], 50) if ps is not None else None

    s_dv = range_score(dv, [(-1e9, 0.5, 30), (0.5, 1.5, 45), (1.5, 2.5, 60), (2.5, 4, 76), (4, 1e9, 88)], 50) if dv is not None else None

    score, _ = weighted([(s_pe, 40), (s_pb, 25), (s_ps, 20), (s_dv, 15)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {"PE": pe, "PB": pb, "PS": ps, "股息率(%)": dv},
    }


def _score_history(pe_pct, pb_pct):
    """历史分位：分位越低越便宜。"""
    s_pe = range_score(pe_pct, [(-1e9, 20, 90), (20, 40, 76), (40, 60, 60), (60, 80, 40), (80, 1e9, 25)], 55) if pe_pct is not None else None
    s_pb = range_score(pb_pct, [(-1e9, 20, 90), (20, 40, 76), (40, 60, 60), (60, 80, 40), (80, 1e9, 25)], 55) if pb_pct is not None else None
    score, _ = weighted([(s_pe, 55), (s_pb, 45)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {"PE历史分位(%)": pe_pct, "PB历史分位(%)": pb_pct},
    }


def _score_growth(pe, growth):
    """成长性价比：PEG + 净利增速水平（负增长按下滑幅度分级，不再一刀切）。"""
    s_growth = range_score(
        growth,
        [(-1e9, -30, 15), (-30, -10, 25), (-10, 0, 40), (0, 5, 45), (5, 15, 60), (15, 30, 75), (30, 1e9, 90)],
        50,
    ) if growth is not None else None

    if pe is not None and pe > 0 and growth is not None and growth > 0:
        peg = pe / growth
        s_peg = range_score(peg, [(-1e9, 0.5, 92), (0.5, 1, 80), (1, 1.5, 66), (1.5, 2.5, 45), (2.5, 1e9, 25)], 50)
    elif growth is not None and growth <= 0:
        peg = None
        # 亏损/负增长无法用 PEG，按下滑幅度分级惩罚：轻微下滑 > 显著下滑 > 大幅下滑
        s_peg = 40 if growth > -10 else (25 if growth > -30 else 15)
    else:
        peg = None
        s_peg = 25  # 数据缺失

    score, _ = weighted([(s_peg, 60), (s_growth, 40)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {"PEG": peg, "净利增速(%)": growth},
    }


def analyze_valuation(spot, val_hist, fin):
    """第二层总入口。val_hist 为 data.get_valuation_history() 返回的 {'pe_ttm': df, 'pb': df}。"""
    val_hist = val_hist or {}
    pe_hist = val_hist.get("pe_ttm")
    pb_hist = val_hist.get("pb")

    pe = _latest_positive(pe_hist)
    pb = _latest_positive(pb_hist)
    # 百度源暂无 PS / 股息率，缺数据时优雅降级（对应子项不参与加权）
    ps = None
    dv = None

    # 百度缺失时回退到行情快照
    if pe is None and spot:
        pe = num(spot.get("市盈率-动态"))
    if pb is None and spot:
        pb = num(spot.get("市净率"))

    pe_pct = _percentile(pe_hist)
    pb_pct = _percentile(pb_hist)

    growth = latest_value(fin, "净利润增长率(%)", "净利润增长率")

    absolute = _score_absolute(pe, pb, ps, dv)
    history = _score_history(pe_pct, pb_pct)
    growth_res = _score_growth(pe, growth)

    w = WEIGHTS["valuation"]
    score, _ = weighted([
        (absolute["score"], w["absolute"]),
        (history["score"], w["history"]),
        (growth_res["score"], w["growth"]),
    ])

    return {
        "absolute": absolute,
        "history": history,
        "growth": growth_res,
        "score": round(score, 1) if score is not None else None,
        "pe": pe, "pb": pb, "ps": ps, "dv": dv,
    }
