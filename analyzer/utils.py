"""通用小工具：数值转换、区间打分、加权合成、指标取值。"""
import math

import pandas as pd


def num(v):
    """安全转 float，失败返回 None。兼容 "-"、空串等脏数据。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def clamp(x, lo=0.0, hi=100.0):
    if x is None:
        return None
    return max(lo, min(hi, x))


def range_score(value, ranges, default=50.0):
    """区间打分。

    ranges: [(lo, hi, score), ...]，前闭后开区间，value 落在哪个区间返回哪个分。
    """
    v = num(value)
    if v is None:
        return default
    for lo, hi, s in ranges:
        if lo <= v < hi:
            return float(s)
    return float(default)


def weighted(parts):
    """加权合成。parts: [(score, weight), ...]，权重为 0 或分数为 None 的自动跳过。

    返回 (合成得分, 有效权重和)。全空时返回 (None, 0)。
    """
    total_w = 0.0
    acc = 0.0
    for s, w in parts:
        if s is None:
            continue
        total_w += float(w)
        acc += float(s) * float(w)
    if total_w == 0:
        return None, 0.0
    return acc / total_w, total_w


def latest_value(df, *colnames):
    """从 DataFrame 中取最新一期的指标值（按日期/月份/季度列或索引排序后取末行）。

    兼容列名差异：依次尝试 colnames 中存在的列。
    """
    if df is None or getattr(df, "empty", True):
        return None
    d = df.copy()
    for dcol in ("日期", "月份", "季度", "报告期"):
        if dcol in d.columns:
            d = d.set_index(dcol)
            break
    try:
        d = d.sort_index()
    except Exception:
        pass
    for cn in colnames:
        if cn in d.columns:
            s = pd.to_numeric(d[cn], errors="coerce").dropna()
            if not s.empty:
                return float(s.iloc[-1])
    return None


def rating_of(score, thresholds):
    """根据得分和阈值表返回评级。thresholds: [(下限, 评级), ...] 从高到低。"""
    if score is None:
        return "未知"
    for lo, name in thresholds:
        if score >= lo:
            return name
    return thresholds[-1][1]
