"""第一层：公司基本面分析。

三个子维度：
  - 行业地位与商业模式（ROE / 毛利率 / 净利润增速）
  - 财务健康度（资产负债率 / 流动比率 / 利润含金量 / 股息发放率）
  - 管理层与实际控制人（股权质押比例）
"""
from .config import WEIGHTS
from .utils import clamp, latest_value, range_score, weighted


def _score_industry_position(fin):
    """行业地位与商业模式：盈利能力 + 议价能力 + 成长性。"""
    roe = latest_value(fin, "加权净资产收益率(%)", "净资产收益率(%)", "加权净资产收益率", "净资产收益率")
    gm = latest_value(fin, "销售毛利率(%)", "销售毛利率")
    growth = latest_value(fin, "净利润增长率(%)", "净利润增长率")

    s_roe = range_score(roe, [(-1e9, 0, 15), (0, 5, 32), (5, 10, 52), (10, 15, 70), (15, 20, 85), (20, 1e9, 95)], 50)
    s_gm = range_score(gm, [(-1e9, 15, 35), (15, 25, 50), (25, 40, 65), (40, 60, 80), (60, 1e9, 90)], 50)
    s_growth = range_score(growth, [(-1e9, -30, 15), (-30, -10, 25), (-10, 0, 40), (0, 5, 45), (5, 15, 60), (15, 30, 75), (30, 1e9, 90)], 50)

    score, _ = weighted([(s_roe, 40), (s_gm, 30), (s_growth, 30)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {"ROE(%)": roe, "毛利率(%)": gm, "净利增速(%)": growth},
    }


def _score_financial_health(fin):
    """财务健康度：杠杆 + 流动性 + 利润含金量 + 股东回报。"""
    debt = latest_value(fin, "资产负债率(%)", "资产负债率")
    current = latest_value(fin, "流动比率", "流动比率(倍)")
    cash_np = latest_value(fin, "经营现金净流量与净利润的比率(%)", "经营现金净流量与净利润比率", "经营现金净流量对净利润比率")
    payout = latest_value(fin, "股息发放率(%)", "股息发放率")

    s_debt = range_score(debt, [(-1e9, 30, 92), (30, 50, 82), (50, 65, 62), (65, 80, 40), (80, 1e9, 20)], 50)
    # 流动比率单调非降：≥1.5 即视为流动性充裕（88），不再因过高而反向扣分
    # （“资金闲置低效”已由 ROE 在行业地位维度体现，此处只衡量偿债安全性）
    s_current = range_score(
        current,
        [(-1e9, 0.7, 30), (0.7, 1.0, 50), (1.0, 1.5, 72), (1.5, 2.5, 88), (2.5, 1e9, 88)],
        50,
    )
    s_cash = range_score(cash_np, [(-1e9, 0, 25), (0, 50, 45), (50, 100, 70), (100, 1e9, 90)], 50)
    s_payout = range_score(payout, [(-1e9, 0, 30), (0, 20, 45), (20, 40, 60), (40, 60, 75), (60, 1e9, 85)], 50)

    score, _ = weighted([(s_debt, 30), (s_current, 25), (s_cash, 25), (s_payout, 20)])
    return {
        "score": round(score, 1) if score is not None else None,
        "detail": {
            "资产负债率(%)": debt,
            "流动比率": current,
            "经营现金流/净利(%)": cash_np,
            "股息发放率(%)": payout,
        },
    }


def _score_management(pledge_pct):
    """管理层与实际控制人：以股权质押比例为主要可量化风险信号。"""
    s = range_score(pledge_pct, [(-1e9, 10, 90), (10, 30, 68), (30, 50, 42), (50, 1e9, 15)], 65) if pledge_pct is not None else 65
    return {
        "score": round(clamp(s), 1),
        "detail": {"质押比例(%)": pledge_pct},
    }


def analyze_fundamentals(fin, pledge_pct):
    """第一层总入口，返回各子维度得分与合成得分。"""
    ip = _score_industry_position(fin)
    fh = _score_financial_health(fin)
    mg = _score_management(pledge_pct)

    w = WEIGHTS["fundamental"]
    score, _ = weighted([
        (ip["score"], w["industry_position"]),
        (fh["score"], w["financial_health"]),
        (mg["score"], w["management"]),
    ])

    return {
        "industry_position": ip,
        "financial_health": fh,
        "management": mg,
        "score": round(score, 1) if score is not None else None,
    }
