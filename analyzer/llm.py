"""大模型自然语言报告（OpenAI 兼容接口，默认 DeepSeek）。

未配置 API Key 时返回 None，由上层降级为模板化报告。
"""
import json

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DISCLAIMER


def _build_prompt(analysis: dict) -> str:
    # 只保留可序列化的关键字段，避免把整张新闻表塞进 prompt
    compact = {
        "name": analysis.get("name"),
        "code": analysis.get("code"),
        "industry": analysis.get("industry"),
        "total_score": analysis.get("total_score"),
        "rating": analysis.get("rating"),
        "veto": analysis.get("veto"),
        "fundamental": analysis.get("fundamental", {}),
        "valuation": analysis.get("valuation", {}),
        "macro": analysis.get("macro", {}),
    }
    payload = json.dumps(compact, ensure_ascii=False, default=str)

    return (
        "你是一名严谨的 A 股证券分析师。请基于以下三层量化分析结果，"
        "用中文写一份精炼的个股投资价值分析报告。\n\n"
        "要求：\n"
        "1. 先给出一句话总结论（值不值得关注/购买），语气客观、不夸大。\n"
        "2. 分三部分展开：①公司基本面 ②估值水平 ③宏观与政策环境，每部分 2-4 句，"
        "结合具体数字说明。\n"
        "3. 单独列出【主要风险】和【关键观察点】各 2-3 条。\n"
        "4. 最后附上免责声明，措辞与下面一致。\n"
        "5. 使用 Markdown 小标题，控制在 400 字以内，不要罗列原始 JSON。\n\n"
        f"量化分析结果：\n{payload}\n\n"
        f"免责声明：{DISCLAIMER}"
    )


def generate_report(analysis: dict):
    """生成自然语言报告；无 Key 或调用失败返回 None。"""
    if not LLM_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是专业的 A 股证券分析师，回答客观、克制、重视风险提示。"},
                {"role": "user", "content": _build_prompt(analysis)},
            ],
            temperature=0.4,
            max_tokens=1200,
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        print(f"[LLM 失败] {e}")
        return None
