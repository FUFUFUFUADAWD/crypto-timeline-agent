# -*- coding: utf-8 -*-
"""Crypto Timeline Agent —— 加密货币时间线资讯 Agent（四通道 · 编年史）

一个零依赖的命令行 AI Agent：
  1. 内置主流币种历史大事件数据库，回答“什么时间段发生过什么金融事件”
  2. 用**币安官方开源数据仓库的历史日线**给每条事件配上「当日官方行情与后续反应」
  3. 通过币安官方公开行情 API 获取实时价格与走势
  4. 抓取主流加密媒体 RSS，按币种过滤最新资讯
  5. 一键生成 HTML + Markdown 时间线资讯报告

四通道（作用于行情取数；`chronicle` 与 `price` 都支持）
  （默认）     币安官方公开行情优先，多源自动容灾
  --live       同上，强制重新选路
  --skill      由官方 CLI（binance-cli request）直取币安官方公开行情
  --official   纯档案模式：不请求实时接口，改用官方开源数据仓库（T+1）

用法示例：
  python agent.py list                          # 查看支持的币种
  python agent.py timeline BTC                  # BTC 全部历史大事件
  python agent.py chronicle BTC                 # 编年史：事件 + 官方行情 + 史评
  python agent.py chronicle BTC --official      # 纯档案模式（不需要上网工具）
  python agent.py chronicle BTC --json          # stdout 只输出 JSON
  python agent.py price BNB                     # BNB 实时行情
  python agent.py price BNB --skill             # 由官方 CLI 取行情
  python agent.py news SOL --limit 5            # SOL 最新资讯
  python agent.py report BTC                    # 生成完整时间线报告
  python agent.py ask "2021年比特币发生了什么"   # 自然语言提问
  python agent.py web                           # 启动 Web 控制台
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import chronicle
import events_db
import market
import news as news_mod
import report as report_mod

VPN_PORTS = (7897, 7890, 10809, 2080, 1080, 8888)

CHANNEL_LABELS = {
    "default": "币安官方公开行情优先 · 多源自动容灾",
    "live": "币安官方公开行情优先 · 多源自动容灾（强制重新选路）",
    "skill": "官方 CLI（binance-cli request）直取币安官方公开行情",
    "official": "纯档案模式：币安官方开源数据仓库（T+1，不请求实时接口）",
}
SPOT_BASE = "https://data-api.binance.vision"

_CN = "〇一二三四五六七八九"


def _cn_num(n):
    """1~31 → 一 / 十 / 十一 / 二十一 / 三十一"""
    if n <= 0:
        return str(n)
    if n < 10:
        return _CN[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + _CN[n - 10]
    return _CN[n // 10] + "十" + (_CN[n % 10] if n % 10 else "")


def cn_date(iso):
    """2021-05-19 → 二〇二一年五月十九日"""
    try:
        y, m, d = iso.split("-")
        return "".join(_CN[int(c)] for c in y) + "年{}月{}日".format(
            _cn_num(int(m)), _cn_num(int(d)))
    except Exception:
        return iso


def say(msg=""):
    """进度与说明一律走 stderr，保证 --json 模式下 stdout 只有纯 JSON。"""
    sys.stderr.write(str(msg) + "\n")


# ---------------------------------------------------------------- 官方 CLI 通道
def cli_path():
    p = os.environ.get("BINANCE_CLI_PATH")
    if p and os.path.exists(p):
        return p
    return shutil.which("binance-cli")


def cli_get_json(url, timeout=60):
    """官方 CLI 直取（binance-cli request GET <url>）。

    ⚠️ 官方 CLI 不读系统上网工具设置；若本机需要走代理，用 HTTP_PROXY/HTTPS_PROXY 传给它。
    """
    exe = cli_path()
    if not exe:
        raise RuntimeError("未找到官方 CLI（binance-cli）：可用环境变量 BINANCE_CLI_PATH 指定，"
                           "或按官方文档安装该官方取数小工具")
    env = dict(os.environ)
    for port in VPN_PORTS:
        import socket
        s = socket.socket()
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:{}".format(port)
            break
        except Exception:
            continue
        finally:
            try:
                s.close()
            except Exception:
                pass
    p = subprocess.run([exe, "request", "GET", url], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError("官方 CLI 退出码 {}（{}…）".format(p.returncode, url[:60]))
    return json.loads(p.stdout)


# ---------------------------------------------------------------- 四通道取行情
def official_last_close(pair, say=None):
    """纯档案模式：用官方开源数据仓库取最近一个已发布交易日的收盘（T+1）。"""
    today = datetime.now(timezone.utc).date()
    for back in range(0, 3):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        ym = "{:04d}-{:02d}".format(y, m)
        try:
            bars = chronicle.fetch_month(pair, ym)
        except Exception:
            continue
        keys = sorted(bars)
        if not keys:
            continue
        last, prev = keys[-1], keys[-2] if len(keys) > 1 else None
        chg = None
        if prev and bars[prev]["close"]:
            chg = (bars[last]["close"] / bars[prev]["close"] - 1) * 100
        return {"source": "Binance(官方归档 T+1)", "symbol": pair,
                "last_price": bars[last]["close"], "change_pct": chg,
                "high": bars[last]["high"], "low": bars[last]["low"],
                "quote_volume": None, "bar_date": last}
    return None


def fetch_quote(symbol, binance_symbol, channel="default", force=False, say=say):
    """按通道取 24h 行情快照。

    默认 / --live：原多源容灾（币安官方公开行情 → Gate.io → OKX → CoinLore → …）
    --skill      ：官方 CLI 直取币安官方公开行情；不可用时**如实回退**并在结果里标注
    --official   ：不请求实时接口，改用官方开源数据仓库最近一日（T+1）
    """
    if channel == "official":
        q = official_last_close(binance_symbol, say=say)
        if q:
            return q
        say("官方归档暂无可用的最近交易日，改为多源容灾取实时行情")
        channel = "default"

    if channel == "skill":
        try:
            d = cli_get_json("{}/api/v3/ticker/24hr?symbol={}".format(SPOT_BASE, binance_symbol))
            return {"source": "Binance(官方CLI)", "symbol": symbol,
                    "last_price": float(d["lastPrice"]),
                    "change_pct": float(d["priceChangePercent"]),
                    "high": float(d["highPrice"]), "low": float(d["lowPrice"]),
                    "quote_volume": float(d["quoteVolume"])}
        except Exception as exc:
            say("官方 CLI 不可用（{}）→ 如实回退到多源容灾，并在输出里标注".format(exc))
            t = market.get_ticker(symbol, binance_symbol)
            if t:
                t["fallback_from"] = "skill"
                t["fallback_reason"] = str(exc)
            return t

    return market.get_ticker(symbol, binance_symbol)


# ---------------------------------------------------------------- 编年史输出
W = 64


def _pct(v, digits=2):
    if v is None:
        return "—"
    return "{:+.2f}%".format(v)


def print_chronicle(res, quote=None, channel="default"):
    coin = res["coin"]
    entries = res["entries"]
    line = "━" * W
    print(line)
    print("加 密 编 年 史".center(W - 4))
    print("{} · {} ｜ 收录 {} 条 ｜ 修于 {}".format(
        coin.get("name"), res["pair"], len(entries),
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")).center(W - 10))
    print(line)
    print()
    print("【卷首】")
    print("   本卷以币安官方开源数据仓库（data.binance.vision）的现货日线归档为底本，")
    print("   为每条事件附「当日官方行情与后续反应」；归档未覆盖的年代一律留空，")
    print("   不以后世价格顶替。")
    print("   取数通道：{}".format(CHANNEL_LABELS.get(channel, channel)))
    if quote:
        q = quote
        extra = "（{}）".format(q.get("bar_date")) if q.get("bar_date") else ""
        print("   当期行情：${} {} ｜ 来源 {}".format(
            market.format_price(q.get("last_price")), _pct(q.get("change_pct")),
            q.get("source")) + extra)
        if q.get("fallback_from"):
            print("   ⚠ 本期请求的是官方 CLI 通道，CLI 不可用已如实回退（原因：{}）".format(
                (q.get("fallback_reason") or "")[:60]))
    print()

    # 按年份分卷
    years = {}
    for e in entries:
        years.setdefault(e["date"][:4], []).append(e)
    for year in sorted(years):
        print("━ 卷 · {} ━".format(year) + "━" * max(0, W - len(year) - 6))
        for e in years[year]:
            print("  {} · {}".format(cn_date(e["date"]), e["title"]))
            print("     〔{}〕〔{}〕".format(e.get("category") or "未分类", e.get("impact") or "—"))
            if e.get("description"):
                print("     {}".format(str(e["description"])[:110]))
            m = e.get("market")
            if m:
                bits = ["{} 收 ${}".format(m["bar_date"], market.format_price(m["close"]))]
                if not m.get("same_day"):
                    bits.append("（事件日无交易，顺延 {} 天取下一交易日）".format(m.get("shift_days")))
                bits.append("当日 {}".format(_pct(m.get("change_1d"))))
                bits.append("后 5 个交易日 {}".format(_pct(m.get("change_5d"))))
                bits.append("后 30 个交易日 {}".format(_pct(m.get("change_30d"))))
                if m.get("drawdown_from_high") is not None:
                    bits.append("距区间高点 {}".format(_pct(m.get("drawdown_from_high"), 1)))
                print("     〔市场反应〕 " + " ｜ ".join(bits))
            else:
                print("     〔市场反应〕 无官方行情 —— {}".format(
                    e.get("market_note") or "归档未覆盖"))
        print()

    print(line)
    print("【史评】")
    s = res["summary"]

    def row(label, a):
        print("   {}（{} 条 / 有行情 {} 条）".format(label, a["样本数"], a["有官方行情样本"]))
        print("     平均当日 {} ｜ 后 5 个交易日 {} ｜ 后 30 个交易日 {} ｜ 30 日上涨占比 {}".format(
            _pct(a["平均当日涨跌"]), _pct(a["平均后5个交易日"]),
            _pct(a["平均后30个交易日"]),
            "—" if a["30日上涨占比"] is None else "{:.1f}%".format(a["30日上涨占比"])))

    row("总体", s["总体"])
    if s["按影响"]:
        print("   — 按事件性质 —")
        for k, a in s["按影响"].items():
            row(k, a)
    if s["按分类"]:
        print("   — 按事件分类 —")
        for k, a in s["按分类"].items():
            row(k, a)
    print()
    print(line)
    print("【凡例】")
    print("   一、事件日：事件发生当天；当天无交易数据时，取其后第一个交易日并注明顺延天数。")
    print("   二、当日涨跌：当日收盘 ÷ 前一交易日收盘 − 1。")
    print("   三、后续反应：以事件当日收盘为基准，第 5 / 30 个【交易日】的累计涨跌，")
    print("       非自然日；样本不足则不显示。")
    print("   四、距区间高点：当日收盘相对「至当日为止的归档区间最高价」的回撤。")
    print("   五、史评为历史统计（样本见括号），不代表未来，也不构成任何投资建议。")
    print(line)


def cmd_chronicle(args):
    coin = events_db.get_coin(args.coin)
    if not coin:
        sys.exit("暂不支持币种 {}，可用 list 命令查看支持列表。".format(args.coin))
    sym = args.coin.upper()
    channel = getattr(args, "channel", "default")
    say("修史中：取币安官方开源数据仓库的日线归档……")
    events = events_db.get_events(sym, start=args.start, end=args.end, category=args.category)
    if not events:
        print("该时间段内没有收录的事件。")
        return
    res = chronicle.build(coin, events, coin["binance_symbol"], say=say)
    res["channel"] = channel

    quote = None
    if not getattr(args, "no_quote", False):
        say("取当期行情（通道：{}）……".format(channel))
        quote = fetch_quote(sym, coin["binance_symbol"], channel=channel,
                            force=(channel == "live"), say=say)

    payload = {
        "coin": coin.get("name"), "symbol": sym, "pair": res["pair"],
        "channel": channel, "via_label": CHANNEL_LABELS.get(channel, channel),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "quote": quote, "summary": res["summary"], "notes": res["notes"],
        "missing": res["missing"], "bars": res["bars"],
        "entries": [{"date": e["date"], "title": e["title"],
                     "category": e.get("category"), "impact": e.get("impact"),
                     "market": e.get("market"), "market_note": e.get("market_note")}
                    for e in res["entries"]],
    }
    if getattr(args, "json", False):
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print_chronicle(res, quote=quote, channel=channel)


# ---------------------------------------------------------------- 原有命令（保留）
def cmd_list(_args):
    print("当前支持的币种（共 {} 个）：".format(len(events_db.supported_coins())))
    for sym in events_db.supported_coins():
        coin = events_db.get_coin(sym)
        print("  {:6s} {}（{}） ｜ 收录事件 {} 条".format(
            sym, coin["name"], coin["name_en"], len(coin["events"])))


def cmd_timeline(args):
    coin = events_db.get_coin(args.coin)
    if not coin:
        sys.exit("暂不支持币种 {}，可用 list 命令查看支持列表。".format(args.coin))
    events = events_db.get_events(args.coin, start=args.start, end=args.end,
                                  category=args.category)
    if not events:
        print("该时间段内没有收录的事件。")
        return
    span = "{} ~ {}".format(args.start or "最早", args.end or "至今")
    print("{}（{}）历史大事件时间线 ｜ {} ｜ 共 {} 条\n".format(
        coin["name"], args.coin.upper(), span, len(events)))
    for e in events:
        print("[{}] {}（{} / {}）".format(e["date"], e["title"], e["category"], e["impact"]))
        print("    {}".format(e["description"]))


def cmd_news(args):
    coin = events_db.get_coin(args.coin)
    if not coin:
        sys.exit("暂不支持币种 {}，可用 list 命令查看支持列表。".format(args.coin))
    print("正在抓取 {}（{}）相关最新资讯……".format(coin["name"], args.coin.upper()))
    items = news_mod.fetch_news(keywords=coin["keywords"], limit=args.limit)
    if not items:
        print("未抓取到匹配新闻（请检查网络，或稍后重试）。")
        return
    for i, n in enumerate(items, 1):
        dt = n["published"].strftime("%Y-%m-%d %H:%M") if n["published"] else "时间未知"
        print("\n{}. {}".format(i, n["title"]))
        print("   {} ｜ {}".format(n["source"], dt))
        if n["summary"]:
            print("   {}".format(n["summary"][:120]))
        if n["link"]:
            print("   {}".format(n["link"]))


def cmd_price(args):
    coin = events_db.get_coin(args.coin)
    if not coin:
        sys.exit("暂不支持币种 {}，可用 list 命令查看支持列表。".format(args.coin))
    channel = getattr(args, "channel", "default")
    t = fetch_quote(args.coin.upper(), coin["binance_symbol"],
                    channel=channel, force=(channel == "live"))
    if not t:
        sys.exit("行情获取失败，请检查网络后重试。")
    sign = "+" if (t["change_pct"] or 0) >= 0 else ""
    print("{}（{}）实时行情 ｜ 数据来源：{}".format(
        coin["name"], args.coin.upper(), t.get("source")))
    print("  最新价：${}（{}{:.2f}% / 24h）".format(
        market.format_price(t["last_price"]), sign, t["change_pct"] or 0))
    if t.get("high") is not None:
        print("  24h 最高 / 最低：${} / ${}".format(
            market.format_price(t["high"]), market.format_price(t["low"])))
    if t.get("quote_volume") is not None:
        print("  24h 成交额：${:.1f} 亿".format(t["quote_volume"] / 1e8))
    if t.get("bar_date"):
        print("  （纯档案模式：这是官方归档 {} 的收盘，不是此刻价格）".format(t["bar_date"]))
    if t.get("fallback_from"):
        print("  ⚠ 请求的是官方 CLI 通道，CLI 不可用已如实回退（未静默换数据）")


def cmd_report(args):
    coin = events_db.get_coin(args.coin)
    if not coin:
        sys.exit("暂不支持币种 {}，可用 list 命令查看支持列表。".format(args.coin))
    sym = args.coin.upper()
    print("正在为 {}（{}）生成时间线资讯报告……".format(coin["name"], sym))

    ticker = klines = None
    if not args.no_price:
        print("  [1/3] 获取实时行情……")
        ticker = market.get_ticker(sym, coin["binance_symbol"])
        klines = market.get_klines(sym, limit=args.days, binance_symbol=coin["binance_symbol"])
    news_items = []
    if not args.no_news:
        print("  [2/3] 抓取最新资讯……")
        news_items = news_mod.fetch_news(keywords=coin["keywords"], limit=args.limit)
    print("  [3/3] 渲染报告……")
    events = events_db.get_events(sym, start=args.start, end=args.end)

    html_path = report_mod.render_html(sym, coin["name"], ticker, klines, news_items, events)
    md_path = report_mod.render_markdown(sym, coin["name"], ticker, klines, news_items, events)
    print("\n报告生成完成：")
    print("  HTML     -> {}".format(html_path))
    print("  Markdown -> {}".format(md_path))
    print("用浏览器打开 HTML 文件即可查看可视化时间线报告。")


def cmd_ask(args):
    """极简自然语言理解：识别币种 + 意图（事件 / 新闻 / 价格 / 编年史）+ 年份区间。"""
    q = args.question
    sym = events_db.resolve_symbol(q)
    if not sym:
        sys.exit("没有识别出币种，试试带上币种名，例如：python agent.py ask \"2021年比特币发生了什么\"")
    coin = events_db.get_coin(sym)

    years = re.findall(r"20\d{2}", q)
    start = min(years) if years else None
    end = max(years) if years else None

    if re.search(r"编年|修史|行情|价格|多少钱|price", q, re.I):
        if re.search(r"编年|修史", q):
            print("识别意图：为 {} 修一卷编年史\n".format(coin["name"]))
            args.coin = sym
            args.start, args.end = start, end
            args.category = None
            args.no_quote = False
            return cmd_chronicle(args)
        print("识别意图：查询 {} 实时行情\n".format(coin["name"]))
        args.coin = sym
        return cmd_price(args)
    if re.search(r"新闻|资讯|最近|最新|news", q, re.I):
        print("识别意图：查询 {} 最新资讯\n".format(coin["name"]))
        args.coin = sym
        args.limit = 10
        return cmd_news(args)

    print("识别意图：查询 {} {} 期间的历史大事件\n".format(
        coin["name"], "{}~{}".format(start, end) if years else "全部"))
    events = events_db.get_events(sym, start=start, end=end)
    if not events:
        print("该时间段内没有收录的事件。")
        return
    for e in events:
        print("[{}] {}（{} / {}）".format(e["date"], e["title"], e["category"], e["impact"]))
        print("    {}".format(e["description"]))


def cmd_web(args):
    import web
    web.run(port=args.port)


def build_parser():
    p = argparse.ArgumentParser(
        prog="agent.py",
        description="Crypto Timeline Agent：加密货币时间线资讯 Agent（零依赖 · 四通道）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="列出支持的币种")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("timeline", help="查询某币种的历史大事件时间线")
    sp.add_argument("coin", help="币种代码，如 BTC / ETH / BNB")
    sp.add_argument("--from", dest="start", help="起始时间，如 2020 或 2020-01-01")
    sp.add_argument("--to", dest="end", help="结束时间，如 2021 或 2021-12-31")
    sp.add_argument("--category", help="按分类过滤，如 监管政策 / 技术升级")
    sp.set_defaults(func=cmd_timeline)

    sp = sub.add_parser("chronicle", help="修一卷编年史：事件 + 官方行情 + 史评")
    sp.add_argument("coin", help="币种代码，如 BTC / ETH / BNB")
    sp.add_argument("--from", dest="start", help="事件起始时间")
    sp.add_argument("--to", dest="end", help="事件结束时间")
    sp.add_argument("--category", help="按分类过滤")
    sp.add_argument("--no-quote", action="store_true", help="不取当期行情（纯历史）")
    sp.set_defaults(func=cmd_chronicle)

    sp = sub.add_parser("news", help="抓取某币种的最新资讯")
    sp.add_argument("coin", help="币种代码")
    sp.add_argument("--limit", type=int, default=10, help="返回条数（默认 10）")
    sp.set_defaults(func=cmd_news)

    sp = sub.add_parser("price", help="查询某币种的实时行情")
    sp.add_argument("coin", help="币种代码")
    sp.set_defaults(func=cmd_price)

    sp = sub.add_parser("report", help="生成时间线资讯报告（HTML + Markdown）")
    sp.add_argument("coin", help="币种代码")
    sp.add_argument("--from", dest="start", help="事件起始时间")
    sp.add_argument("--to", dest="end", help="事件结束时间")
    sp.add_argument("--days", type=int, default=30, help="走势图天数（默认 30）")
    sp.add_argument("--limit", type=int, default=10, help="新闻条数（默认 10）")
    sp.add_argument("--no-news", action="store_true", help="不抓取新闻（离线模式）")
    sp.add_argument("--no-price", action="store_true", help="不获取行情（离线模式）")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("ask", help="自然语言提问，如：2021年比特币发生了什么")
    sp.add_argument("question", help="你的问题")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("web", help="启动 Web 控制台（浏览器可视化分析台）")
    sp.add_argument("--port", type=int, default=8000, help="端口号（默认 8000）")
    sp.set_defaults(func=cmd_web)
    return p


GLOBAL_FLAGS = {"--live": "live", "--skill": "skill", "--official": "official", "--json": "json"}


def split_globals(argv):
    """把全局旗标从命令行里摘出来（这样所有子命令都支持，且原命令用法不变）。"""
    picked, rest = [], []
    for a in argv:
        if a in GLOBAL_FLAGS:
            picked.append(GLOBAL_FLAGS[a])
        else:
            rest.append(a)
    return picked, rest


def main():
    # Windows 管道下 stdout 默认按 GBK 编码，编年史里的框线字符会直接崩，统一强制 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    picked, rest = split_globals(sys.argv[1:])
    channels = [c for c in picked if c in ("live", "skill", "official")]
    if len(channels) > 1:
        sys.stderr.write("✗ 通道旗标冲突：{} 一次只能选一条\n".format(
            "、".join("--" + c for c in channels)))
        sys.exit(2)

    args = build_parser().parse_args(rest)
    args.channel = channels[0] if channels else "default"
    args.json = "json" in picked
    args.func(args)


if __name__ == "__main__":
    main()
