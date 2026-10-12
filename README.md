# A股智能股票分析器

一个基于 **三层分析框架** 的 A 股投资价值分析工具，提供**推荐选股**与**个股深度分析**两大功能，并整合权威信息源交叉验证。

> ⚠️ 本工具输出仅供研究学习与交流，**不构成任何投资建议**。股市有风险，投资需谨慎。

## 功能特性

- **推荐选股**：条件快筛（PE/PB/市值）、行业热榜、自选池深度评分三种模式
- **个股分析**：输入代码或名称，输出三层量化评分 + 综合评级 + AI 报告 + 相关新闻
- **三层分析框架**：
  - 第一层 · 公司基本面（40%）：行业地位与商业模式、财务健康度、管理层与实际控制人
  - 第二层 · 估值水平（35%）：绝对估值（PE/PB）+ 历史分位数 + 成长性价比（PEG）
  - 第三层 · 宏观与政策（25%）：宏观经济周期 + 政策信号
- **权威信息源**：证监会官网、上交所/深交所/北交所、巨潮资讯网、证券时报、上海证券报、中国证券网
- **AI 自然语言报告**：集成 DeepSeek（OpenAI 兼容接口），未配置 Key 时自动降级为模板报告
- **硬风险一票否决**：ST / 退市风险警示、负面舆情等

## 安装与运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. （可选）配置大模型 API Key，生成自然语言报告
cp .env.example .env   # 然后编辑 .env 填入 DEEPSEEK_API_KEY

# 3. 启动
streamlit run app.py
```

启动后浏览器自动打开 http://localhost:8501 。

## 项目结构

```
股票分析/
├── app.py                # Streamlit 主界面
├── requirements.txt
├── .env.example          # 大模型 API Key 配置模板
└── analyzer/
    ├── config.py         # 评分权重 / 评级阈值 / LLM 配置
    ├── utils.py          # 打分、取值、加权等工具
    ├── data.py           # AkShare 数据采集（容错 + 缓存）
    ├── fundamentals.py   # 第一层：基本面
    ├── valuation.py      # 第二层：估值
    ├── macro.py          # 第三层：宏观与政策
    ├── news.py           # 权威信息源
    ├── scoring.py        # 综合评分与评级
    ├── recommend.py      # 推荐选股模块
    ├── llm.py            # 大模型报告
    └── pipeline.py       # 个股分析流水线
```

## 评分模型

| 层级 | 权重 | 子维度 |
|---|---|---|
| 公司基本面 | 40% | 行业地位与商业模式 15% · 财务健康度 15% · 管理层 10% |
| 估值水平 | 35% | 绝对估值 12% · 历史分位 12% · 成长性价比(PEG) 11% |
| 宏观与政策 | 25% | 经济周期 15% · 政策信号 10% |

评级：**强烈推荐(≥85) / 推荐(≥70) / 中性(≥55) / 谨慎(≥40) / 回避(<40)**。

权重与阈值可在 `analyzer/config.py` 中调整。

## 数据源说明

- 行情/财务/估值/新闻/宏观：**AkShare**（免费开源，东方财富/新浪/百度股市通等聚合）
- 财务指标：新浪财务分析接口（ROE、毛利率、资产负债率、经营现金流等）
- 估值历史分位：百度股市通每日 PE(TTM)/PB 序列（近五年）
- 宏观：国家统计局口径（PMI/GDP/CPI/M2）

> 注：百度股市通暂不提供市销率(PS)与股息率，这两个进阶指标当前缺数据、会在估值层自动降级（仅以 PE/PB 加权），不影响整体运行。

> AkShare 接口偶有字段变动或反爬限制，本工具已做容错与降级处理；若某项数据缺失，对应维度会以中性分兜底，不影响整体运行。

## 线上部署（Streamlit Community Cloud）

将本工具部署到公网，任何设备通过网址即可访问（对方无需安装 Python）。

### 1. 准备 GitHub 仓库
- 在 GitHub 新建一个**公开**仓库（Streamlit Community Cloud 免费版要求公开）。
- 本地初始化并推送（`.gitignore` 已排除密钥、日志、缓存，密钥不会被上传）：
  ```bash
  cd "D:\claude-project\股票分析"
  git init
  git add .
  git commit -m "init: A股智能股票分析器"
  git branch -M main
  git remote add origin https://github.com/<你的用户名>/<仓库名>.git
  git push -u origin main
  ```

### 2. 在 Streamlit Cloud 部署
1. 打开 https://share.streamlit.io ，用 GitHub 账号登录；
2. 点 **New app**，选择刚推送的仓库、分支 `main`、入口文件 `app.py`；
3. 如需固定 Python 版本，在 **Advanced settings** 里设为 **3.12**；
4. 点 **Deploy**，等待构建完成，得到形如 `https://<用户名>-<仓库名>.streamlit.app` 的网址。

### 3. 配置大模型密钥（可选，用于 AI 自然语言报告）
在 Streamlit Cloud 的 **Settings → Secrets** 中填写（TOML 格式）：
```toml
DEEPSEEK_API_KEY = "sk-你的真实Key"
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
```
不配置也可正常使用，会自动降级为模板化报告。

### 数据源提示
线上服务器位于海外，akshare 访问东方财富偶发限流时，工具会自动回退到新浪（行情）、百度（估值）、巨潮（行业）等备用源，显示「数据暂不可用」而非崩溃。

## 免责声明

本工具输出仅供研究学习与交流，不构成任何投资建议。数据可能存在延迟或误差，请以交易所与公司公告为准。据此操作，风险自负。
