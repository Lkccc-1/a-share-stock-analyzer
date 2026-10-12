"""全局配置：评分权重、评级阈值、LLM 设置等。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Streamlit Cloud 部署时密钥通过 st.secrets 暴露；本地用环境变量 / .env。
# 用 try 包裹，兼容无 Streamlit 的纯命令行场景（如冒烟测试）。
try:
    import streamlit as st

    _SECRETS = dict(st.secrets)
except Exception:  # noqa: BLE001
    _SECRETS = {}


def _cfg(key, default=""):
    """优先取 Streamlit 密钥，其次取环境变量。"""
    val = _SECRETS.get(key)
    if val not in (None, ""):
        return val
    return os.getenv(key, default)

# ---------- 评分权重（三层总计 100） ----------
WEIGHTS = {
    "fundamental": {
        "total": 40,            # 第一层：公司基本面
        "industry_position": 15,  # 行业地位与商业模式
        "financial_health": 15,   # 财务健康度
        "management": 10,         # 管理层与实际控制人
    },
    "valuation": {
        "total": 35,            # 第二层：估值水平
        "absolute": 11,         # 绝对估值（PE/PB）
        "history": 13,          # 历史分位数（自可比、均值回归，最稳健，权重略高）
        "growth": 11,           # 成长性价比（PEG）
    },
    "macro": {
        "total": 25,            # 第三层：宏观与政策
        "cycle": 15,            # 宏观经济周期
        "policy": 10,           # 政策信号
    },
}

# ---------- 评级阈值（综合得分 → 评级） ----------
RATING_THRESHOLDS = [
    (85, "强烈推荐"),
    (70, "推荐"),
    (55, "中性"),
    (40, "谨慎"),
    (0, "回避"),
]

# ---------- 硬风险（触发一票否决 / 红色预警） ----------
VETO_KEYWORDS = ("ST", "*ST", "退")

# ---------- LLM（OpenAI 兼容接口，默认 DeepSeek） ----------
LLM_API_KEY = _cfg("DEEPSEEK_API_KEY") or _cfg("LLM_API_KEY") or ""
LLM_BASE_URL = _cfg("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = _cfg("LLM_MODEL", "deepseek-chat")

APP_NAME = "A股智能股票分析器"
DISCLAIMER = "本工具输出仅供研究学习与交流，不构成任何投资建议。股市有风险，投资需谨慎。"
