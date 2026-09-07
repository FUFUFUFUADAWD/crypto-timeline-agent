# -*- coding: utf-8 -*-
"""Crypto Timeline Agent —— 加密货币时间线资讯 Agent

一个零依赖的命令行 AI Agent：
  1. 内置主流币种历史大事件数据库，回答“什么时间段发生过什么金融事件”
  2. 通过币安公开行情 API 获取实时价格与走势
  3. 抓取主流加密媒体 RSS，按币种过滤最新资讯
  4. 一键生成 HTML + Markdown 时间线资讯报告

用法示例：
  python agent.py list                          # 查看支持的币种
  python agent.py timeline BTC                  # BTC 全部历史大事件
  python agent.py timeline ETH --from 2021 --to 2022   # 指定时间段
  python agent.py news SOL --limit 5            # SOL 最新资讯
  python agent.py price BNB                     # BNB 实时行情
  python agent.py report BTC                    # 生成完整时间线报告
  python agent.py ask "2021年比特币发生了什么"   # 自然语言提问
  python agent.py web                           # 启动 Web 控制台（浏览器可视化界面）
"""
import argparse
import re
import sys

import events_db
import market
import news as news_mod
import report as report_mod


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
    t = market.get_ticker(args.coin.upper(), coin["binance_symbol"])
    if not t:
        sys.exit("行情获取失败，请检查网络后重试。")
    sign = "+" if t["change_pct"] >= 0 else ""
    print("{}（{}）实时行情 ｜ 数据来源：币安公开行情".format(coin["name"], args.coin.upper()))
    print("  最新价：${}（{}{:.2f}% / 24h）".format(
        market.format_price(t["last_price"]), sign, t["change_pct"]))
    print("  24h 最高 / 最低：${} / ${}".format(
        market.format_price(t["high"]), market.format_price(t["low"])))
    print("  24h 成交额：${:.1f} 亿".format(t["quote_volume"] / 1e8))


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
    """极简自然语言理解：识别币种 + 意图（事件 / 新闻 / 价格）+ 年份区间。"""
    q = args.question
    sym = events_db.resolve_symbol(q)
    if not sym:
        sys.exit("没有识别出币种，试试带上币种名，例如：python agent.py ask \"2021年比特币发生了什么\"")
    coin = events_db.get_coin(sym)

    years = re.findall(r"20\d{2}", q)
    start = min(years) if years else None
    end = max(years) if years else None

    if re.search(r"价格|多少钱|行情|price", q, re.I):
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
        description="Crypto Timeline Agent：加密货币时间线资讯 Agent（零依赖）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="列出支持的币种")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("timeline", help="查询某币种的历史大事件时间线")
    sp.add_argument("coin", help="币种代码，如 BTC / ETH / BNB")
    sp.add_argument("--from", dest="start", help="起始时间，如 2020 或 2020-01-01")
    sp.add_argument("--to", dest="end", help="结束时间，如 2021 或 2021-12-31")
    sp.add_argument("--category", help="按分类过滤，如 监管政策 / 技术升级")
    sp.set_defaults(func=cmd_timeline)

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


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
