在线演示链接：https://1ddeaab426ec41ef987123c55bcd373a.app.workbuddy.link/
# Crypto Timeline Agent 🪙📈

> 加密货币时间线资讯 Agent —— 一键回答「什么时间段，BTC / ETH / BNB 等主流币种发生过什么金融事件」
>
> 参赛方向：币安 Agent OS 迷你黑客松 · 赛道一（自建 AI Agent）· 数据分析主题

## 项目简介

Crypto Timeline Agent 是一个**零依赖**的 Python 命令行 AI Agent，面向加密货币资讯场景：

- 🕘 **历史事件时间线**：内置 10 个主流币种（BTC、ETH、BNB、SOL、XRP、DOGE、ADA、LTC、TRX、ZEC）从创世至今的 90+ 条重大金融事件，覆盖监管政策、技术升级、市场里程碑、安全事件、机构采用等 7 大分类，每条事件标注「利好 / 利空 / 中性」影响方向
- 🖥️ **Web 可视化控制台「链事纪」**：一行命令启动本地 Web 分析台，含市场总览（全币种 24h/7日/30日 涨跌表）、大事件时间线、最新资讯、研究报告四大面板，支持一键复制 / 下载 Markdown 报告
- 📰 **最新资讯聚合**：自动抓取 CoinDesk、Cointelegraph、Decrypt、The Block、Bitcoin Magazine 等主流媒体 RSS，按币种关键词智能过滤
- 💹 **实时行情**：多数据源自动容灾（Binance 官方公开行情 → Gate.io → OKX → CoinLore → CoinGecko → CoinPaprika），任一源不可用自动切换，**中国大陆网络可直连使用**
- 📊 **一键生成报告**：输出 HTML（可视化时间线 + 走势图，红涨绿跌配色）与 Markdown 双格式资讯报告
- 🗣️ **自然语言提问**：`ask` 模式支持「2021年比特币发生了什么」这类口语化查询
- 🔌 **全程零依赖**：只用 Python 标准库，无需安装任何第三方包，无需 API Key

## 快速开始（分步骤指南）

> 零基础也能 5 分钟跑起来。

**第 1 步：安装 Python**

安装 Python 3.8 或更高版本（[python.org 官网下载](https://www.python.org/downloads/)），安装时勾选 “Add Python to PATH”。安装完成后打开终端验证：

```bash
python --version
```

**第 2 步：获取本项目**

```bash
git clone https://github.com/FUFUFUFUADAWD/crypto-timeline-agent.git
cd crypto-timeline-agent
```

没有安装 git 的话，也可以在 GitHub 页面点击 `Code → Download ZIP` 下载解压。

**第 3 步：直接运行（无需安装任何依赖！）**

```bash
# 方式一（推荐）：启动 Web 可视化控制台「链事纪」
python agent.py web
# 然后用浏览器打开 http://127.0.0.1:8000

# 方式二：命令行操作
# 查看支持的币种
python agent.py list

# 查询 BTC 历史大事件时间线
python agent.py timeline BTC

# 查询 2021~2022 年以太坊发生了什么
python agent.py timeline ETH --from 2021 --to 2022

# 只看监管类事件
python agent.py timeline BTC --category 监管政策

# 抓取 SOL 最新资讯（联网）
python agent.py news SOL --limit 5

# 查询 BNB 实时行情（联网）
python agent.py price BNB

# 生成完整时间线资讯报告（HTML + Markdown）
python agent.py report BTC

# 自然语言提问
python agent.py ask "2021年比特币发生了什么大事"
```

**第 4 步：查看报告**

`report` 命令生成的文件保存在 `output/` 目录，用浏览器打开 HTML 文件即可看到可视化时间线报告（可直接用于作品视频录屏）。

## 命令一览

| 命令 | 作用 | 示例 |
| --- | --- | --- |
| `web` | 启动 Web 可视化控制台 | `python agent.py web --port 8000` |
| `list` | 列出支持的币种 | `python agent.py list` |
| `timeline` | 查询历史大事件时间线 | `python agent.py timeline BTC --from 2020 --to 2021` |
| `news` | 抓取币种最新资讯 | `python agent.py news ETH --limit 10` |
| `price` | 查询实时行情 | `python agent.py price BNB` |
| `report` | 生成 HTML + Markdown 报告 | `python agent.py report BTC --days 30` |
| `ask` | 自然语言提问 | `python agent.py ask "狗狗币最近有什么新闻"` |

## 项目结构

```
crypto-timeline-agent/
├── agent.py          # CLI 主入口（含自然语言 ask 模式、web 启动命令）
├── web.py            # Web 控制台后端（标准库 http.server 提供 JSON API）
├── static/
│   └── index.html    # Web 控制台前端「链事纪」（单页应用，原生 JS）
├── events_db.py      # 事件数据库：加载 / 查询 / 过滤
├── market.py         # 行情模块：多数据源容灾获取实时价格与 K 线
├── news.py           # 新闻模块：RSS 抓取 + 币种关键词过滤
├── report.py         # 报告模块：渲染 HTML / Markdown 时间线报告
├── data/
│   └── events.json   # 多币种历史大事件数据库（可持续扩充）
├── output/           # 生成的报告（自动创建）
└── README.md
```

## 如何扩展事件库

事件库就是一个普通 JSON 文件 `data/events.json`，按如下格式追加即可，欢迎 PR：

```json
{"date": "2025-03-06", "title": "美国建立战略比特币储备",
 "description": "……", "category": "监管政策", "impact": "利好"}
```

- `category` 可选：市场里程碑 / 监管政策 / 技术升级 / 安全事件 / 机构采用 / 生态发展 / 宏观经济
- `impact` 可选：利好 / 利空 / 中性

## 数据来源与免责声明

- 历史事件：人工整理自公开资料，如有疏漏欢迎指正
- 实时行情：Binance（data-api.binance.vision 公开行情域名）/ Gate.io / OKX / CoinLore / CoinGecko / CoinPaprika 公共接口，按序容灾切换
- 新闻资讯：各媒体公开 RSS 源
- **本项目仅供学习研究，不构成任何投资建议。**

## License

MIT
