"""权威信息源整合。

提供：
  - 权威信息源直链（证监会 / 交易所 / 巨潮 / 证券时报 / 上海证券报 / 中国证券网）
  - 个股新闻（AkShare 聚合，含权威媒体来源）
  - 权威来源新闻筛选
"""
import pandas as pd

# 权威信息源（供用户交叉核实）
AUTHORITY_SOURCES = [
    ("中国证监会官网", "http://www.csrc.gov.cn"),
    ("上海证券交易所", "http://www.sse.com.cn"),
    ("深圳证券交易所", "http://www.szse.cn"),
    ("北京证券交易所", "https://www.bse.cn"),
    ("巨潮资讯网（公告）", "http://www.cninfo.com.cn"),
    ("证券时报", "https://www.stcn.com"),
    ("上海证券报", "https://www.cnstock.com"),
    ("中国证券网", "https://www.cnstock.com"),
]

_AUTHORITY_KEYS = ["证券时报", "上海证券报", "中国证券网", "证监会", "上海证券交易所", "深圳证券交易所", "巨潮", "财联社", "中证网"]


def authority_links():
    return AUTHORITY_SOURCES


def filter_authority(news_df):
    """筛选来自权威媒体的新闻。"""
    if news_df is None or news_df.empty:
        return None
    src_col = None
    for c in ("文章来源", "来源", "媒体"):
        if c in news_df.columns:
            src_col = c
            break
    if src_col is None:
        return news_df.head(20)
    mask = news_df[src_col].astype(str).apply(lambda x: any(k in x for k in _AUTHORITY_KEYS))
    return news_df[mask] if mask.any() else news_df.head(20)
