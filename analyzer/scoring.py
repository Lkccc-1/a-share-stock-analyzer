"""综合评分与评级：三层加权 + 硬风险一票否决。"""
from .config import RATING_THRESHOLDS, VETO_KEYWORDS, WEIGHTS
from .utils import clamp, rating_of, weighted


def apply(report):
    """把三层得分合成为总分与评级，并写入硬风险预警。

    期望 report 中已含：fundamental.score / valuation.score / macro.score / name / warnings。
    """
    f = report.get("fundamental", {}).get("score")
    v = report.get("valuation", {}).get("score")
    m = report.get("macro", {}).get("score")

    w = WEIGHTS
    total, _ = weighted([
        (f, w["fundamental"]["total"]),
        (v, w["valuation"]["total"]),
        (m, w["macro"]["total"]),
    ])
    report["total_score"] = round(total, 1) if total is not None else None

    name = report.get("name") or ""
    report.setdefault("warnings", [])
    veto = None
    if any(k in name.upper() for k in VETO_KEYWORDS):
        veto = "ST / 退市风险警示股，风险极高"
    pledge = report.get("fundamental", {}).get("management", {}).get("detail", {}).get("质押比例(%)")
    if pledge is not None and pledge >= 50:
        report["warnings"].append(f"股权质押比例高达 {pledge:.1f}%，存在较大平仓 / 控制权风险")

    if veto:
        report["veto"] = veto
        report["rating"] = "回避"
        report["total_score"] = min(report["total_score"] or 0, 30)
    else:
        report["veto"] = None
        report["rating"] = rating_of(report["total_score"], RATING_THRESHOLDS)

    return report
