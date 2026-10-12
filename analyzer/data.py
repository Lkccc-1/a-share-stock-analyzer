"""数据采集层：AkShare 封装 + 容错 + 简单 TTL 缓存。

所有外部接口均按名称安全调用：接口不存在或抛异常时返回 None，由上层优雅降级。
"""
import json
import time
import warnings
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

warnings.filterwarnings("ignore")

_CACHE = {}


def _cached(key, ttl, fn):
    """带 TTL 的内存缓存。"""
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (now, val)
    return val


def _safe(name, *args, default=None, **kwargs):
    """按名称安全调用 akshare 接口；接口不存在或异常时打印告警并返回 default。"""
    fn = getattr(ak, name, None) if isinstance(name, str) else name
    if fn is None:
        print(f"[数据源失败] {name}: 接口不存在")
        return default
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"[数据源失败] {name}: {e}")
        return default


# ---------------- 行情 / 标的 ----------------

def get_all_spot():
    """全市场 A 股实时行情（优先东方财富，失败回退新浪），列名统一为 code/name。

    注：新浪回退源不含 PE/PB/总市值，仅供名称与价格查询。
    """
    def _f():
        df = _safe("stock_zh_a_spot_em")
        if df is None or df.empty:
            df = _safe("stock_zh_a_spot")
        if df is not None and not df.empty:
            df = df.rename(columns={"代码": "code", "名称": "name"})
            # 新浪回退源代码带交易所前缀（sh/sz/bj），统一为 6 位纯数字
            df["code"] = df["code"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
        return df

    return _cached("spot_all", 120, _f)


def get_code_name_map():
    spot = get_all_spot()
    if spot is None or spot.empty:
        return {}
    return dict(zip(spot["code"].astype(str), spot["name"].astype(str)))


def normalize_symbol(inp):
    """把用户输入（代码 / 名称 / 带交易所前缀）规范化为 6 位代码。"""
    if not inp:
        return None
    s = str(inp).strip().lower()
    for p in ("sh", "sz", "bj"):
        if s.startswith(p):
            s = s[2:]
            break
    if s.isdigit() and len(s) == 6:
        return s
    m = get_code_name_map()
    for code, name in m.items():
        if name == inp.strip():
            return code
    for code, name in m.items():
        if inp.strip() in name:
            return code
    return None


def get_stock_spot(code):
    """单只股票实时行情快照（dict）。"""
    spot = get_all_spot()
    if spot is None or spot.empty:
        return None
    row = spot[spot["code"].astype(str) == str(code)]
    return row.iloc[0].to_dict() if not row.empty else None


def get_history(code, days=250):
    """前复权日线（用于画 K 线/走势）。"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    return _safe(
        "stock_zh_a_hist",
        symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq",
    )


def get_company_profile(code):
    """公司基本信息 → 统一 dict（公司名称/行业/上市日期/主营业务）。

    优先东方财富，失败回退巨潮资讯网（权威源，且不受东方财富反爬限流影响）。
    """
    # 东方财富：item/value 两列结构
    df = _safe("stock_individual_info_em", symbol=code)
    if df is not None and not df.empty and {"item", "value"}.issubset(df.columns):
        d = dict(zip(df["item"].astype(str), df["value"].astype(str)))
        return {
            "公司名称": d.get("股票简称"),
            "行业": d.get("行业"),
            "上市日期": d.get("上市时间"),
            "主营业务": None,
        }
    # 巨潮资讯网：单行、列式结构（含所属行业 / 主营业务 / 机构简介）
    df = _safe("stock_profile_cninfo", symbol=code)
    if df is not None and not df.empty:
        row = df.iloc[0].to_dict()
        return {
            "公司名称": row.get("公司名称"),
            "行业": row.get("所属行业"),
            "上市日期": row.get("上市日期"),
            "主营业务": row.get("主营业务"),
        }
    return None


# ---------------- 财务 / 估值 ----------------

def get_financial_indicator(code):
    """财务指标（新浪），含 ROE/毛利率/净利率/资产负债率/现金流等。"""
    start = datetime.now().year - 6
    return _safe("stock_financial_analysis_indicator", symbol=code, start_year=str(start))


def get_valuation_history(code):
    """个股 PE(TTM)/PB 近五年历史（百度股市通），用于历史分位与当前估值。"""
    pe = _safe("stock_zh_valuation_baidu", symbol=code, indicator="市盈率(TTM)", period="近五年")
    pb = _safe("stock_zh_valuation_baidu", symbol=code, indicator="市净率", period="近五年")
    return {"pe_ttm": pe, "pb": pb}


# ---------------- 新闻 / 质押 ----------------

def _fetch_news_em(symbol):
    """直接调用东方财富搜索接口拉取个股新闻。

    独立实现原因：akshare 1.19.1 的 stock_news_em 在清洗 HTML 时用了
    `str.replace(r"\\u3000", regex=True)`，在 pandas 3.0 下触发正则非法转义而崩溃。
    这里改用纯字符串替换（regex=False），规避该问题。
    """
    try:
        from curl_cffi import requests as req
    except Exception:  # noqa: BLE001
        import requests as req

    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_param = {
        "uid": "",
        "keyword": symbol,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": 100,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    params = {
        "cb": "callback",
        "param": json.dumps(inner_param, ensure_ascii=False),
        "_": str(int(time.time() * 1000)),
    }
    headers = {
        "accept": "*/*",
        "referer": "https://so.eastmoney.com/news/s?keyword=" + symbol,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    }
    r = req.get(url, params=params, headers=headers, timeout=15)
    text = r.text
    # 剥离 JSONP 包裹：callback({...})
    i, j = text.find("("), text.rfind(")")
    payload = text[i + 1 : j] if i != -1 and j > i else text
    data = json.loads(payload)
    items = (data.get("result") or {}).get("cmsArticleWebOld") or []
    if not items:
        return None

    df = pd.DataFrame(items)
    df = df.rename(columns={"date": "发布时间", "mediaName": "文章来源", "title": "新闻标题", "content": "新闻内容"})
    df["新闻链接"] = "http://finance.eastmoney.com/a/" + df.get("code", "").astype(str) + ".html"
    df["关键词"] = symbol

    # 清洗 HTML 标签与空白（纯字符串替换，规避正则引擎问题）
    for col in ("新闻标题", "新闻内容"):
        if col not in df.columns:
            continue
        s = df[col].astype(str)
        for pat, rep in (("<em>", ""), ("</em>", ""), ("　", ""), ("\r\n", " "), ("\n", " ")):
            s = s.str.replace(pat, rep, regex=False)
        df[col] = s

    cols = ["关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def get_news(code):
    """个股新闻（东方财富聚合，含权威媒体来源）。"""
    return _safe(_fetch_news_em, code)


def get_pledge(code):
    """个股最新质押比例(%)；近 10 个自然日逐日尝试，取最近有数据的一天。

    不在质押名单中 → 视为无质押，返回 0.0；近 10 日均无数据 → None。
    """
    today = datetime.now()
    for i in range(10):
        d = (today - timedelta(days=i)).strftime("%Y%m%d")
        df = _safe("stock_gpzy_pledge_ratio_em", date=d)
        if df is None or df.empty:
            continue
        row = df[df["股票代码"].astype(str).str.pad(6, side="left", fillchar="0") == str(code)]
        return float(row.iloc[0]["质押比例"]) if not row.empty else 0.0
    return None


# ---------------- 行业 / 宏观 ----------------

def get_industry_boards():
    """行业板块行情。"""
    return _cached("boards", 300, lambda: _safe("stock_board_industry_name_em"))


def get_macro_data():
    """宏观指标（PMI / GDP / CPI / 货币供应），一次性拉取并缓存。"""
    def _f():
        return {
            "pmi": _safe("macro_china_pmi"),
            "gdp": _safe("macro_china_gdp"),
            "cpi": _safe("macro_china_cpi"),
            "m2": _safe("macro_china_money_supply"),
        }

    return _cached("macro", 3600, _f)


def market_median():
    """全市场市盈率 / 市净率中位数（剔除非正数），作为估值对比基准。"""
    spot = get_all_spot()
    if spot is None or spot.empty:
        return None, None
    res = {}
    for col in ("市盈率-动态", "市净率"):
        if col not in spot.columns:
            res[col] = None
            continue
        s = pd.to_numeric(spot[col], errors="coerce")
        s = s[s > 0]
        res[col] = float(s.median()) if not s.empty else None
    return res.get("市盈率-动态"), res.get("市净率")
