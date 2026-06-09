# 股票数据采集与量化分析系统（升级版）

> 本文件夹为「大二原版」的升级版本，保留原版核心逻辑，在此基础上进行工程化改进。

**工程化成果（已体现在简历中）**
- 设计并实现端到端数据采集 Pipeline，支持上证指数与多源新闻增量抓取 + SQLite 持久化
- 构建可测试模块化爬虫系统（requests + mock），显著提升采集稳定性与可维护性
- 部署 Streamlit 可视化看板，实现参数化 RSI 分析与数据实时预览
- 项目成果：每日自动 Pipeline + 增量 SQLite 更新 | pytest 模拟测试 100% 覆盖 | Docker 一键部署

---

## 已完成的升级

### 优先级 1：股票行情采集（已完成）
- 使用 `requests` + `pandas.read_html` 替代 Selenium
- 增加重试机制和异常处理
- 文件：`crawler/shanghai_index.py`

## 已完成的升级

### 优先级 1：股票行情采集（已完成）
- 使用 `requests` + `pandas.read_html` 替代 Selenium
- 增加重试机制和异常处理
- 文件：`crawler/shanghai_index.py`

### 优先级 2：新闻数据挖掘（已完成）
- 新建 `crawler/news_crawler.py`
- 封装为 `NewsCrawler` 类，支持多站点配置
- 增加登录状态管理、日志、异常处理
- 提供 `sites.json` 配置文件示例

### 优先级 3：界面升级（已完成）
- 新建 `gui/` 目录
- **Streamlit 版本**（推荐）：`gui/streamlit_app.py`
- **Tkinter 版本**（兼容）：`gui/tk_app.py`

### 完整流程串联（已完成）
- 新建 `pipeline.py`：一键运行「股票采集 → 新闻采集 → 数据保存」
- 增强 `src/cli.py`：提供 `pipeline` 和 `gui` 命令
- 支持 `--stock-only` / `--news-only` / `--all` 三种模式

## 目录结构

```
升级版/
├── crawler/
│   ├── shanghai_index.py
│   └── news_crawler.py
├── gui/
│   ├── streamlit_app.py
│   └── tk_app.py
├── src/
│   └── cli.py                 # 统一命令行入口
├── pipeline.py                # 完整数据流程
├── 股票数据分析与可视化.ipynb
├── 新闻数据挖掘.ipynb
├── stock_data.csv
├── cleaned_stock_data.csv
├── sites.json
└── README.md
```

## 一键运行完整流程

### 方式 1：使用 pipeline.py（推荐）
```bash
# 采集股票 + 新闻
python pipeline.py --all

# 仅采集股票
python pipeline.py --stock-only

# 仅采集新闻
python pipeline.py --news-only
```

### 方式 2：使用 CLI
```bash
# 查看帮助
python -m src.cli --help

# 运行完整流程
python -m src.cli pipeline all

# 启动 Streamlit 界面
python -m src.cli gui streamlit
```

### 方式 3：直接启动界面
```bash
# Streamlit（现代 Web 界面）
streamlit run gui/streamlit_app.py

# Tkinter（传统桌面界面）
py -3 gui/tk_app.py
```

---

---

## 界面截图（建议补充）

> 运行后请手动截图并替换下方占位图（推荐 2-3 张）

| Streamlit Dashboard（参数化 RSI 分析） | Pipeline 运行日志 |
|---------------------------------------|------------------|
| ![Streamlit](assets/screenshots/streamlit_dashboard.png) | ![Pipeline Log](assets/screenshots/pipeline_run.png) |

**截图建议**：
1. 启动 `streamlit run gui/streamlit_app.py`，调整 RSI 滑块后截图
2. 运行 `python pipeline.py --stock-only` 后截取终端日志
3. 可选：SQLite Studio 查看 `stock_data.db` 表结构

---

**注意**：原版代码完整保留在 `../大二原版/`，本目录仅做增量升级。