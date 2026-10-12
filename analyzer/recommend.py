"""推荐选股模块。

三种模式：
  1. 条件选股（基于全市场实时行情快筛，快）
  2. 行业热榜（板块涨跌幅排行）
  3. 自选池评分（对少量股票跑完整三层分析，慢，建议 ≤ 20 只）
"""
import pandas as pd

from . import data


# 预置股票池（code, 名称）。用于「精选股票池」一键批量评分。
# 选股以三层深度评分为主，不再依赖美国服务器拿不到的全市场 PE/PB 快筛与实时行业板块数据。
PRESET_POOLS = {
    "核心资产池": [
        ("600519", "贵州茅台"), ("000858", "五粮液"), ("600036", "招商银行"),
        ("601318", "中国平安"), ("600900", "长江电力"), ("000333", "美的集团"),
        ("600887", "伊利股份"), ("601088", "中国神华"), ("600276", "恒瑞医药"),
        ("601398", "工商银行"), ("000001", "平安银行"), ("600030", "中信证券"),
    ],
    "高股息池": [
        ("601088", "中国神华"), ("600900", "长江电力"), ("600019", "宝钢股份"),
        ("601398", "工商银行"), ("601939", "建设银行"), ("600036", "招商银行"),
        ("000895", "双汇发展"), ("600028", "中国石化"), ("601857", "中国石油"),
        ("600548", "深高速"),
    ],
    "成长股池": [
        ("300750", "宁德时代"), ("002594", "比亚迪"), ("688981", "中芯国际"),
        ("300059", "东方财富"), ("002475", "立讯精密"), ("601012", "隆基绿能"),
        ("600584", "长电科技"), ("002415", "海康威视"), ("600570", "恒生电子"),
        ("300124", "汇川技术"),
    ],
    "行业龙头池": [
        ("600519", "贵州茅台"), ("600036", "招商银行"), ("601318", "中国平安"),
        ("300750", "宁德时代"), ("002594", "比亚迪"), ("600900", "长江电力"),
        ("000333", "美的集团"), ("600276", "恒瑞医药"), ("600887", "伊利股份"),
        ("601088", "中国神华"), ("600030", "中信证券"), ("688981", "中芯国际"),
    ],
}


def quick_screen(pe_min=None, pe_max=None, pb_max=None, min_mcap=None, exclude_st=True, top_n=30):
    """基于实时行情的快速条件选股（新浪回退源无 PE/PB/市值，缺失列自动跳过）。"""
    spot = data.get_all_spot()
    if spot is None or spot.empty:
        return None

    df = spot.copy()
    has_pe = "市盈率-动态" in df.columns
    has_pb = "市净率" in df.columns
    has_mcap = "总市值" in df.columns
    if has_pe:
        df["市盈率-动态"] = pd.to_numeric(df["市盈率-动态"], errors="coerce")
    if has_pb:
        df["市净率"] = pd.to_numeric(df["市净率"], errors="coerce")
    if has_mcap:
        df["总市值"] = pd.to_numeric(df["总市值"], errors="coerce")

    if exclude_st and "name" in df.columns:
        df = df[~df["name"].astype(str).str.contains("ST|退", na=False)]

    if has_pe and pe_min is not None:
        df = df[df["市盈率-动态"] >= pe_min]
    if has_pe and pe_max is not None:
        df = df[df["市盈率-动态"] <= pe_max]
    if has_pb and pb_max is not None:
        df = df[df["市净率"] <= pb_max]
    if has_mcap and min_mcap is not None:
        df = df[df["总市值"] >= min_mcap * 1e8]  # 亿元 → 元

    if has_mcap:
        df = df.sort_values("总市值", ascending=False)
    df = df.head(top_n)

    cols = ["code", "name", "最新价", "涨跌幅", "市盈率-动态", "市净率", "总市值", "换手率", "60日涨跌幅"]
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def industry_hot(top_n=15):
    """行业板块热榜（按涨跌幅）。"""
    boards = data.get_industry_boards()
    if boards is None or boards.empty:
        return None
    df = boards.copy()
    df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    df = df.sort_values("涨跌幅", ascending=False).head(top_n)
    cols = ["板块名称", "涨跌幅", "总市值", "换手率", "上涨家数", "下跌家数", "领涨股票"]
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def score_watchlist(codes):
    """对自选股票池跑完整分析，返回按总分排序的摘要。"""
    from . import pipeline

    rows = []
    for code in codes:
        try:
            r = pipeline.analyze_stock(code)
            rows.append({
                "code": r["code"],
                "name": r["name"],
                "总分": r["total_score"],
                "评级": r["rating"],
                "基本面": r["fundamental"]["score"],
                "估值": r["valuation"]["score"],
                "宏观": r["macro"]["score"],
            })
        except Exception as e:  # noqa: BLE001
            rows.append({"code": code, "name": code, "总分": None, "评级": "分析失败", "错误": str(e)})
    df = pd.DataFrame(rows)
    if not df.empty and "总分" in df.columns:
        df = df.sort_values("总分", ascending=False)
    return df
