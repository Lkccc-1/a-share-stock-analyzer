"""A股智能股票分析器 —— Streamlit 主界面。"""
import streamlit as st
import plotly.graph_objects as go

from analyzer import data, llm, news as news_mod, pipeline, recommend
from analyzer.config import APP_NAME, DISCLAIMER, WEIGHTS

# ---------------- 视觉规范（dataviz 参考调色板） ----------------
BLUE = "#2a78d6"          # 主色（categorical slot 1 / sequential blue）
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide")


# ---------------- 工具函数 ----------------

@st.cache_data(ttl=600, show_spinner=False)
def _analyze(code):
    return pipeline.analyze_stock(code)


def _rating_status(rating):
    if rating in ("强烈推荐", "推荐"):
        return "good", "🟢"
    if rating == "中性":
        return "warning", "🟡"
    if rating == "谨慎":
        return "serious", "🟠"
    return "critical", "🔴"


def _fmt(v, nd=2):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _detail_text(d):
    if not d:
        return ""
    return "　·　".join(f"{k} = {_fmt(v, 2) if isinstance(v, (int, float)) else v}" for k, v in d.items() if v is not None)


def score_gauge(score, status_color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score if score is not None else 0,
        number={"font": {"size": 46, "color": INK}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED},
            "bar": {"color": status_color, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [{"range": [0, 100], "color": GRID}],
        },
    ))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=10, b=10))
    return fig


def layer_bar(labels, values):
    """三层得分横向条形图（单色蓝，直接标注数值）。"""
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=BLUE, width=0.55,
        text=[f"{v:.0f}" if v is not None else "—" for v in values],
        textposition="outside", textfont=dict(color=INK, size=14),
        hovertemplate="%{y}: %{x:.1f}<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 108], showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK))
    fig.update_layout(height=200, margin=dict(l=10, r=50, t=10, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def price_chart(hist):
    if hist is None or hist.empty:
        return None
    fig = go.Figure(go.Scatter(
        x=hist["日期"], y=hist["收盘"], mode="lines",
        line=dict(color=BLUE, width=2),
        hovertemplate="%{x}<br>收盘 %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=260, margin=dict(l=20, r=20, t=10, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED), zeroline=False),
    )
    return fig


def template_report(r):
    f, v, m = r["fundamental"], r["valuation"], r["macro"]
    return "\n".join([
        f"### {r['name']}（{r['code']}）分析结论",
        f"综合评分 **{r['total_score']}**，评级 **{r['rating']}**。",
        "",
        "#### ① 公司基本面",
        f"- 行业地位与商业模式：**{f['industry_position']['score']} 分**　{_detail_text(f['industry_position']['detail'])}",
        f"- 财务健康度：**{f['financial_health']['score']} 分**　{_detail_text(f['financial_health']['detail'])}",
        f"- 管理层与实际控制人：**{f['management']['score']} 分**　{_detail_text(f['management']['detail'])}",
        "",
        "#### ② 估值水平",
        f"- 绝对估值：**{v['absolute']['score']} 分**　{_detail_text(v['absolute']['detail'])}",
        f"- 历史分位数：**{v['history']['score']} 分**　{_detail_text(v['history']['detail'])}",
        f"- 成长性价比：**{v['growth']['score']} 分**　{_detail_text(v['growth']['detail'])}",
        "",
        "#### ③ 宏观与政策环境",
        f"- 经济周期：**{m['cycle']['score']} 分**　{_detail_text(m['cycle']['detail'])}",
        f"- 政策信号：**{m['policy']['score']} 分**",
        "",
        f"> {DISCLAIMER}",
    ])


# ---------------- 渲染：个股分析 ----------------

def render_stock_analysis(code):
    with st.spinner("正在拉取数据并分析（首次拉取全市场行情可能较慢，请稍候）..."):
        r = _analyze(code)
    if r is None or r.get("spot") is None and r.get("total_score") is None:
        st.error("未找到该股票或数据源异常，请检查代码后重试。")
        return

    st.subheader(f"{r['name']}（{r['code']}） · {r.get('industry') or '行业未知'}"
                 + (f" · {r['listing_date']}上市" if r.get("listing_date") else ""))
    if r.get("veto"):
        st.error("🚨 硬风险预警：" + r["veto"])

    spot = r.get("spot") or {}
    status, icon = _rating_status(r["rating"])

    # KPI 行
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("综合评分", f"{r['total_score']}" if r["total_score"] is not None else "—")
    k2.metric("评级", f"{icon} {r['rating']}")
    k3.metric("最新价", spot.get("最新价"))
    k4.metric("市盈率(动)", _fmt(spot.get("市盈率-动态")))
    k5.metric("市净率", _fmt(spot.get("市净率")))
    k6.metric("总市值", f"{_fmt(spot.get('总市值', 0) / 1e8, 0)}亿" if spot.get("总市值") else "—")

    if not all(k in spot for k in ("市盈率-动态", "市净率", "总市值")):
        st.caption("注：实时行情已回退备用源，市盈率/市净率/总市值暂缺；估值请以「② 估值水平 · 明细」为准。")

    left, right = st.columns([1, 1.4])
    with left:
        st.plotly_chart(score_gauge(r["total_score"], STATUS[status]), use_container_width=True)
    with right:
        st.markdown("**三层得分**（基本面 40% · 估值 35% · 宏观政策 25%）")
        st.plotly_chart(layer_bar(
            ["宏观与政策", "估值水平", "公司基本面"],
            [r["macro"]["score"], r["valuation"]["score"], r["fundamental"]["score"]],
        ), use_container_width=True)

    fig_price = price_chart(r.get("history"))
    if fig_price:
        st.markdown("**近一年股价走势（前复权）**")
        st.plotly_chart(fig_price, use_container_width=True)

    # 各层明细
    with st.expander("① 公司基本面 · 明细", expanded=True):
        f = r["fundamental"]
        c1, c2, c3 = st.columns(3)
        c1.metric("行业地位与商业模式", f["industry_position"]["score"])
        c1.caption(_detail_text(f["industry_position"]["detail"]))
        if r.get("main_business"):
            st.caption(f"**主营业务**：{r['main_business']}")
        c2.metric("财务健康度", f["financial_health"]["score"])
        c2.caption(_detail_text(f["financial_health"]["detail"]))
        c3.metric("管理层与实际控制人", f["management"]["score"])
        c3.caption(_detail_text(f["management"]["detail"]))

    with st.expander("② 估值水平 · 明细"):
        v = r["valuation"]
        c1, c2, c3 = st.columns(3)
        c1.metric("绝对估值", v["absolute"]["score"])
        c1.caption(_detail_text(v["absolute"]["detail"]))
        c2.metric("历史分位数", v["history"]["score"])
        c2.caption(_detail_text(v["history"]["detail"]))
        c3.metric("成长性价比", v["growth"]["score"])
        c3.caption(_detail_text(v["growth"]["detail"]))
        mref = r.get("market_ref") or {}
        if mref.get("pe_median") is None and mref.get("pb_median") is None:
            st.caption("全市场中位数参考：东方财富行情暂不可用，暂无（估值对比基准缺失，不影响个股评分）。")
        else:
            st.caption(
                f"全市场中位数参考：市盈率 {_fmt(mref.get('pe_median'))} · 市净率 {_fmt(mref.get('pb_median'))}"
            )

    with st.expander("③ 宏观与政策环境 · 明细"):
        m = r["macro"]
        c1, c2 = st.columns(2)
        c1.metric("经济周期", m["cycle"]["score"])
        c1.caption(_detail_text(m["cycle"]["detail"]))
        c2.metric("政策信号", m["policy"]["score"])
        c2.caption("基于近期新闻关键词的粗略政策温度（方向性参考）")

    # AI 报告
    st.markdown("---")
    st.subheader("🤖 AI 分析报告")
    with st.spinner("生成自然语言报告..."):
        report_text = llm.generate_report(r)
    if report_text:
        st.markdown(report_text)
    else:
        st.info("未配置大模型 API Key（或调用失败），已降级为模板化报告。配置方法见「使用说明」。")
        st.markdown(template_report(r))

    # 权威信息源 + 新闻
    st.markdown("---")
    st.subheader("📰 权威信息源与相关新闻")
    ndf = r.get("news")
    if ndf is not None and not ndf.empty:
        auth = news_mod.filter_authority(ndf)
        for _, row in auth.head(8).iterrows():
            title = str(row.get("新闻标题", ""))
            url = row.get("新闻链接", "")
            src = row.get("文章来源", "")
            t = row.get("发布时间", "")
            if title and url and str(url).startswith("http"):
                st.markdown(f"- [{title}]({url})　·　{src}　·　{t}")
    else:
        st.caption("未获取到新闻。")

    st.caption("**去权威源核实**：" + "　·　".join(f"[{n}]({u})" for n, u in news_mod.authority_links()))
    st.warning(DISCLAIMER)


# ---------------- 渲染：推荐选股 ----------------

def render_recommend():
    st.subheader("条件选股（基于全市场实时行情快筛）")
    c1, c2, c3, c4 = st.columns(4)
    pe_min = c1.number_input("市盈率下限", 0, 2000, 0)
    pe_max = c2.number_input("市盈率上限", 0, 2000, 30)
    pb_max = c3.number_input("市净率上限", 0.0, 100.0, 5.0)
    min_mcap = c4.number_input("总市值下限(亿)", 0, 100000, 100)
    exclude_st = st.checkbox("剔除 ST / 退市风险股", value=True)

    if st.button("开始筛选", type="primary"):
        with st.spinner("检测数据源..."):
            spot_ok = data.spot_has_valuation_fields()
        if not spot_ok:
            st.warning(
                "⚠️ 东方财富全市场行情当前暂不可用（已回退新浪，缺少市盈率/市净率/市值字段），"
                "条件选股暂时无法筛选。请改用下方「自选池深度评分」（个股评分不受影响）。"
            )
        else:
            with st.spinner("筛选中..."):
                df = recommend.quick_screen(
                    pe_min=pe_min or None, pe_max=pe_max or None,
                    pb_max=pb_max or None, min_mcap=min_mcap or None,
                    exclude_st=exclude_st, top_n=30,
                )
            if df is None or df.empty:
                st.info("无符合条件的股票，请放宽条件。")
            else:
                st.dataframe(df, use_container_width=True)
                st.caption("快筛仅使用实时行情字段（PE/PB/市值等）；如需深度评分，请复制代码到下方自选池批量分析。")

    st.divider()
    st.subheader("行业热榜（按涨跌幅）")
    boards = recommend.industry_hot()
    if boards is None or boards.empty:
        st.info("行业板块数据暂不可用。")
    else:
        st.dataframe(boards, use_container_width=True)

    st.divider()
    st.subheader("自选池深度评分（三层完整分析）")
    watch = st.text_area("输入股票代码，逗号/空格/换行分隔（建议 ≤ 20 只）", placeholder="600519, 000858, 300750")
    if st.button("批量分析", type="primary"):
        codes = [c for c in watch.replace(",", " ").replace("，", " ").split() if c]
        if not codes:
            st.warning("请先输入股票代码。")
        else:
            with st.spinner(f"正在分析 {len(codes)} 只股票（每只需拉取多路数据，请耐心等待）..."):
                df = recommend.score_watchlist(codes[:20])
            st.dataframe(df, use_container_width=True)


# ---------------- 渲染：宏观环境 ----------------

def render_macro():
    st.subheader("宏观经济指标（最新一期）")
    macro = data.get_macro_data()
    from analyzer.utils import latest_value

    pmi = latest_value(macro.get("pmi"), "制造业-指数", "制造业-指数(经季节调整)")
    gdp = latest_value(macro.get("gdp"), "国内生产总值-同比增长", "国内生产总值-同比")
    cpi = latest_value(macro.get("cpi"), "全国-同比增长", "全国-同比")
    m2 = latest_value(macro.get("m2"), "货币和准货币(M2)-同比增长", "M2-同比增长")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("制造业 PMI", _fmt(pmi))
    c2.metric("GDP 同比增速(%)", _fmt(gdp))
    c3.metric("CPI 同比(%)", _fmt(cpi))
    c4.metric("M2 同比增速(%)", _fmt(m2))

    st.caption(
        "PMI > 50 为扩张区间；GDP 增速与 CPI 用于判断经济周期（复苏/过热/滞胀/衰退）；"
        "M2 增速反映货币宽松程度。宏观环境对个股判断较间接，故作为背景修正项参与评分。"
    )
    st.caption("宏观周期在个股评分中的权重为 15%，政策信号权重为 10%。")


# ---------------- 主入口 ----------------

def main():
    st.title("📈 " + APP_NAME)
    st.caption("三层分析框架：公司基本面 → 估值水平 → 宏观与政策，并整合权威信息源交叉验证。")

    with st.sidebar:
        st.header("个股分析")
        inp = st.text_input("输入股票代码或名称", placeholder="如 600519 / 贵州茅台")
        if st.button("开始分析", type="primary", use_container_width=True):
            if not inp.strip():
                st.warning("请输入股票代码或名称。")
            else:
                code = data.normalize_symbol(inp)
                if code is None:
                    st.error("未识别到该股票，请确认代码或名称。")
                else:
                    st.session_state["analyze_code"] = code
        st.divider()
        w = WEIGHTS
        st.caption(
            f"评分权重：基本面 {w['fundamental']['total']}% · 估值 {w['valuation']['total']}% · 宏观政策 {w['macro']['total']}%"
        )
        src = getattr(data, "spot_source", lambda: None)()
        st.caption(f"行情数据源：{src or '尚未拉取'}")
        st.caption(DISCLAIMER)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 个股分析", "⭐ 推荐选股", "🌐 宏观环境", "ℹ️ 使用说明"])

    with tab1:
        code = st.session_state.get("analyze_code")
        if code:
            render_stock_analysis(code)
        else:
            st.info("在左侧输入股票代码或名称，点击「开始分析」。例如：600519（贵州茅台）、000858（五粮液）、300750（宁德时代）。")

    with tab2:
        render_recommend()

    with tab3:
        render_macro()

    with tab4:
        st.markdown("""
### 使用说明

**功能**
1. **个股分析**：输入代码或名称，输出三层量化评分 + 综合评级 + AI 报告 + 相关新闻。
2. **推荐选股**：条件快筛、行业热榜、自选池深度评分三种模式。
3. **宏观环境**：PMI / GDP / CPI / M2 最新指标。

**三层分析框架**
- **第一层 · 公司基本面（40%）**：行业地位与商业模式、财务健康度、管理层与实际控制人。
- **第二层 · 估值水平（35%）**：传统估值（PE/PB/股息率）+ 进阶估值（PS/PEG）+ 历史分位数。
- **第三层 · 宏观与政策（25%）**：经济周期 + 政策信号。

**评级**：强烈推荐 / 推荐 / 中性 / 谨慎 / 回避；ST/退市等硬风险触发一票否决。

**配置大模型报告（可选）**
1. 复制 `.env.example` 为 `.env`；
2. 填入 `DEEPSEEK_API_KEY`（[platform.deepseek.com](https://platform.deepseek.com) 申请）；
3. 重启应用即可生成自然语言分析报告；未配置则自动降级为模板报告。

**数据源**：AkShare（免费开源），行情/财务/估值/新闻/宏观均有覆盖；接口偶有变动，已做容错处理。
""")
        st.warning(DISCLAIMER)


if __name__ == "__main__":
    main()
