"""个股分析流水线：拉数 → 三层分析 → 综合评分 → 组装报告。"""
from . import data, fundamentals, macro, scoring, valuation


def analyze_stock(code):
    """对单只股票跑完整三层分析，返回结构化报告 dict。"""
    code = str(code)

    spot = data.get_stock_spot(code)
    name = (spot or {}).get("name") or data.get_code_name_map().get(code) or code

    fin = data.get_financial_indicator(code)
    val_hist = data.get_valuation_history(code)
    profile = data.get_company_profile(code)
    hist = data.get_history(code, days=250)
    news_df = data.get_news(code)
    pledge_pct = data.get_pledge(code)

    industry = (profile or {}).get("行业")
    main_business = (profile or {}).get("主营业务")
    listing_date = (profile or {}).get("上市日期")

    f = fundamentals.analyze_fundamentals(fin, pledge_pct)
    v = valuation.analyze_valuation(spot, val_hist, fin)
    m = macro.analyze_macro(data.get_macro_data(), news_df)

    pe_med, pb_med = data.market_median()

    report = {
        "code": code,
        "name": name,
        "industry": industry,
        "main_business": main_business,
        "listing_date": listing_date,
        "spot": spot,
        "history": hist,
        "news": news_df,
        "fundamental": f,
        "valuation": v,
        "macro": m,
        "market_ref": {"pe_median": pe_med, "pb_median": pb_med},
        "warnings": [],
    }
    scoring.apply(report)
    return report
