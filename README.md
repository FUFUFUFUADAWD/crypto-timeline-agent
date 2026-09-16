> 🌐 **在线演示**：https://1ddeaab426ec41ef987123c55bcd373a.app.workbuddy.link/

# Crypto Timeline Agent 📈 · 加密编年史

> 加密货币时间线资讯 Agent —— 一键回答「什么时间段，BTC / ETH / BNB 等主流币种发生过什么金融事件」，
> 并给每条事件配上帝安官方历史行情与后续反应。
>
> 参赛方向：币安 Agent OS 迷你黑客松 · 赛道一（自建 AI Agent）· 数据分析主题

## 项目简介

Crypto Timeline Agent 是一个**零依赖**的 Python 命令行 AI Agent，面向加密货币资讯场景：

- 🕘 **加密编年史（命令行）**：`python agent.py chronicle BTC` 修一卷编年史 ——
  按年份分卷，每条事件附**币安官方历史行情**（事件当日收盘与涨跌、后 5 / 30 个交易日的累计涨跌、
  距区间高点的回撤），卷末给出**史评**（按事件性质与分类的统计）
- 🧭 **四通道取数**：默认多源容灾 / `--live` 强制重新选路 / `--skill` 官方 CLI 直取 /
  `--official` 纯档案模式（不需要上网工具）
- 🗂️ **历史事件时间线**：内置 10 个主流币种（BTC、ETH、BNB、SOL、XRP、DOGE、ADA、LTC、TRX、ZEC）
  从创世至今的 **93 条**重大金融事件，覆盖监管政策、技术升级、市场里程碑、安全事件、机构采用等 7 大分类，
  每条标注「利好 / 利空 / 中性」
- 🖥️ **Web 可视化控制台「链事纪」**：一行命令启动本地 Web 分析台，含市场总览、大事件时间线、
  最新资讯、研究报告四大面板
- 📰 **最新资讯聚合**：抓取主流媒体 RSS，按币种关键词过滤
- 💹 **实时行情**：多数据源自动容灾（币安官方公开行情 → Gate.io → OKX → CoinLore → …），
  任一源不可用自动切换，**中国大陆网络可直连使用**
- 📊 **一键生成报告**：输出 HTML（可视化时间线 + 走势图，红涨绿跌）与 Markdown 双格式
- 🗣️ **自然语言提问**：`ask` 模式支持「2021年比特币发生了什么」「给比特币修一卷编年史」这类口语化查询
- 🔌 **全程零依赖**：只用 Python 标准库，无需第三方包、无需 API Key

## 编年史长什么样（节选 · 实测）

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                         加 密 编 年 史
  比特币 · BTCUSDT ｜ 收录 34 条 ｜ 修于 2026-09-16 00:48 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【卷首】
   本卷以币安官方开源数据仓库（data.binance.vision）的现货日线归档为底本，
   为每条事件附「当日官方行情与后续反应」；归档未覆盖的年代一律留空，
   不以后世价格顶替。
   取数通道：币安官方公开行情优先 · 多源自动容灾
   当期行情：$75,797.68 -2.77% ｜ 来源 Binance

━ 卷 · 2020 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  二〇二〇年三月十二日 · “312”黑天鹅崩盘
     〔宏观经济〕〔利空〕
     新冠疫情引发全球流动性危机，比特币单日暴跌近 40%，最低触及约 3,800 美元。
     〔市场反应〕 2020-03-12 收 $4,800.00 ｜ 当日 -39.50% ｜ 后 5 个交易日 +10.68% ｜ 后 30 个交易日 +43.27% ｜ 距区间高点 -75.76%
  二〇二〇年十月二十一日 · PayPal 宣布支持加密货币
     〔机构采用〕〔利好〕
     支付巨头 PayPal 宣布允许用户买卖和持有比特币等加密货币，机构化叙事升温。
     〔市场反应〕 2020-10-21 收 $12,780.96 ｜ 当日 +7.31% ｜ 后 5 个交易日 +2.12% ｜ 后 30 个交易日 +83.52% ｜ 距区间高点 -35.45%

【史评】
   总体（24 条 / 有行情 24 条）
     平均当日 -3.65% ｜ 后 5 个交易日 -0.44% ｜ 后 30 个交易日 +6.36% ｜ 30 日上涨占比 58.3%
   利好（16 条 / 有行情 16 条）
     平均当日 +0.65% ｜ 后 30 个交易日 +4.66% ｜ 30 日上涨占比 50.0%
   利空（8 条 / 有行情 8 条）
     平均当日 -12.24% ｜ 后 30 个交易日 +9.76% ｜ 30 日上涨占比 75.0%
```

完整样张（含凡例）见 `AGENT.md`。**早期事件（2008—2016）会显示「无官方行情 —— 事件日早于官方归档起点」，
这是刻意留空，不是数据缺失**。

## 用了币安官方的哪几项（逐项可核验）

**【在用】4 项**

| 官方资源 | 用在哪 |
|---|---|
| 官方开源数据仓库 `data.binance.vision`（现货月度日线归档） | **每条事件的市场反应**（编年史底本） |
| 官方公开行情入口 `data-api.binance.vision`（`/api/v3/ticker/24hr`） | 卷首「当期行情」、`price` 命令 |
| 官方公开行情入口（`/api/v3/klines`） | `report` 报告的走势图 |
| 官方 CLI `binance-cli request GET` | `--skill` 通道（官方取数小工具） |

**【未用】其余官方技能，逐项说明**

- Web3 组（`crypto-market-rank` / `meme-rush` / `trading-signal` 等）：主力接口域名在本机不可达，
  且属链上 + 社交口径，与本作品的历史行情口径无关；
- `academy-skill` / `fiat` / `p2p` / `square-post`：内容与支付类，主站域名本机不可达；
- `payment` / `onchain-pay`：需要 API 密钥 + 签名，本作品不接账户、不碰资金。

## 快速开始（分步骤指南）

> 零基础也能 5 分钟跑起来。

**第 1 步：安装 Python**

安装 Python 3.8 或更高版本（[python.org 官网下载](https://www.python.org/downloads/)），
安装时勾选 "Add Python to PATH"。安装完成后打开终端验证：

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
# 方式一（推荐）：修一卷编年史
python agent.py chronicle BTC

# 纯档案模式（不需要上网工具）
python agent.py chronicle ETH --official

# 方式二：启动 Web 可视化控制台「链事纪」
python agent.py web
# 然后用浏览器打开 http://127.0.0.1:8000

# 方式三：命令行单项查询
python agent.py list                                  # 查看支持的币种
python agent.py timeline BTC                          # BTC 历史大事件时间线
python agent.py timeline ETH --from 2021 --to 2022    # 指定时间段
python agent.py price BNB                             # BNB 实时行情
python agent.py news SOL --limit 5                    # SOL 最新资讯
python agent.py report BTC                            # 生成完整时间线报告
python agent.py ask "2021年比特币发生了什么"           # 自然语言提问
```

**第 4 步：查看报告**

`report` 命令生成的文件保存在 `output/` 目录，用浏览器打开 HTML 文件即可看到可视化时间线报告。

## 命令一览

| 命令 | 作用 | 示例 |
| --- | --- | --- |
| `chronicle` | **修一卷编年史（事件 + 官方行情 + 史评）** | `python agent.py chronicle BTC --official` |
| `web` | 启动 Web 可视化控制台 | `python agent.py web --port 8000` |
| `list` | 列出支持的币种 | `python agent.py list` |
| `timeline` | 查询历史大事件时间线 | `python agent.py timeline BTC --from 2020 --to 2021` |
| `news` | 抓取币种最新资讯 | `python agent.py news ETH --limit 10` |
| `price` | 查询实时行情 | `python agent.py price BNB` |
| `report` | 生成 HTML + Markdown 报告 | `python agent.py report BTC --days 30` |
| `ask` | 自然语言提问 | `python agent.py ask "狗狗币最近有什么新闻"` |

**四通道旗标**（所有命令通用）：`--live`（强制重新选路）/ `--skill`（官方 CLI 直取）/
`--official`（纯档案模式）/ `--json`（stdout 只输出 JSON）。

## 项目结构

```
crypto-timeline-agent/
├── agent.py          # CLI 主入口（编年史 + 原七条命令 + 四通道旗标）
├── chronicle.py      # 编年史引擎：官方归档取数 + 事件对齐 + 史评统计
├── web.py            # Web 控制台后端（标准库 http.server 提供 JSON API）
├── static/
│   └── index.html    # Web 控制台前端「链事纪」（单页应用，原生 JS）
├── events_db.py      # 事件数据库：加载 / 查询 / 过滤
├── market.py         # 行情模块：多数据源容灾获取实时价格与 K 线
├── news.py           # 新闻模块：RSS 抓取 + 币种关键词过滤
├── report.py         # 报告模块：渲染 HTML / Markdown 时间线报告
├── data/
│   └── events.json   # 多币种历史大事件数据库（可持续扩充）
├── skills/
│   └── biannian-shi/SKILL.md   # 官方格式技能定义（可 npx skills add）
├── output/           # 生成的报告（自动创建）
└── README.md
```

## 文档索引

**随本仓库发布**

| 文件 | 内容 |
|---|---|
| `README.md` | 本文件：编年史首页 |
| `AGENT.md` | 史官手记：两卷真实编年史样张、三条核查命令、官方资源逐项核对、20 技能取舍、校勘纪律 |
| `项目说明.md` | 纂修条例：作品定位、四通道、口径与边界、使用指南 |
| `skills/biannian-shi/SKILL.md` | 修史凡例（官方技能格式，可安装给任意 Agent 使用） |

**作者本地自用材料（不随仓库发布，所以在仓库里检索不到，属正常）**

| 文件 | 内容 |
|---|---|
| `参赛回复-评委两问.md` | 答问（参赛答辩稿） |

## 如何扩展事件库

事件库就是一个普通 JSON 文件 `data/events.json`，按如下格式追加即可，欢迎 PR：

```json
{"date": "2025-03-06", "title": "美国建立战略比特币储备",
 "description": "……", "category": "监管政策", "impact": "利好"}
```

- `category` 可选：市场里程碑 / 监管政策 / 技术升级 / 安全事件 / 机构采用 / 生态发展 / 宏观经济
- `impact` 可选：利好 / 利空 / 中性

> 事件为人工整理自公开资料；**行情一律取自币安官方数据**，两者来源在编年史里分列。

## 数据来源与免责声明

- 历史事件：人工整理自公开资料，如有疏漏欢迎指正
- **历史行情**：币安官方开源数据仓库（`data.binance.vision`）现货日线归档
- 当期行情：币安官方公开行情域名（`data-api.binance.vision`）/ Gate.io / OKX / CoinLore /
  CoinGecko / CoinPaprika 公共接口，按序容灾切换
- 新闻资讯：各媒体公开 RSS 源
- **本项目仅供学习研究，不构成任何投资建议。**

## License

MIT
