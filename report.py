# -*- coding: utf-8 -*-
"""报告模块：生成加密货币时间线资讯报告（HTML + Markdown）。

HTML 报告为单文件、内嵌样式，浏览器直接打开即可查看/录屏演示。
"""
import html
import os
from datetime import datetime

from market import format_price

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

IMPACT_STYLE = {
    "利好": ("#e84545", "#fdecec"),   # 涨 = 红（中国股市配色习惯）
    "利空": ("#1a9e54", "#e6f6ec"),   # 跌 = 绿
    "中性": ("#8a8f98", "#f2f3f5"),
}

CATEGORY_ORDER = ["市场里程碑", "监管政策", "技术升级", "安全事件", "机构采用", "生态发展", "宏观经济"]


def _esc(s):
    return html.escape(str(s), quote=True)


def _sparkline_svg(klines, width=560, height=120):
    """根据 K 线收盘价生成内嵌 SVG 走势图。涨红跌绿。"""
    if len(klines) < 2:
        return ""
    closes = [c for _, c in klines]
    lo, hi = min(closes), max(closes)
    span = (hi - lo) or 1
    step = width / (len(closes) - 1)
    points = []
    for i, c in enumerate(closes):
        x = i * step
        y = height - 8 - (c - lo) / span * (height - 16)
        points.append("{:.1f},{:.1f}".format(x, y))
    rising = closes[-1] >= closes[0]
    color = "#e84545" if rising else "#1a9e54"
    fill = "rgba(232,69,69,0.10)" if rising else "rgba(26,158,84,0.10)"
    poly = "0,{h} ".format(h=height) + " ".join(points) + " {w},{h}".format(w=width, h=height)
    return (
        '<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<polygon points="{poly}" fill="{fill}"/>'
        '<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>'
    ).format(w=width, h=height, poly=poly, pts=" ".join(points), fill=fill, color=color)


def _impact_badge(impact):
    fg, bg = IMPACT_STYLE.get(impact, IMPACT_STYLE["中性"])
    return ('<span style="color:{fg};background:{bg};border-radius:4px;padding:1px 8px;'
            'font-size:12px;white-space:nowrap">{t}</span>').format(fg=fg, bg=bg, t=_esc(impact))


def _price_section(symbol, ticker, klines):
    if not ticker:
        return '<section><h2>实时行情</h2><p class="muted">行情获取失败（可检查网络后重试）。</p></section>'
    chg = ticker["change_pct"]
    chg_color = "#e84545" if chg >= 0 else "#1a9e54"
    sign = "+" if chg >= 0 else ""
    spark = _sparkline_svg(klines)
    kline_note = ""
    if klines:
        kline_note = '<p class="muted">近 {} 日收盘价走势：{} → {}</p>'.format(
            len(klines), klines[0][0], klines[-1][0])
    return """<section>
<h2>实时行情（{sym} · 数据来源：币安公开行情）</h2>
<div class="price-card">
  <div class="price-main">${price} <span style="color:{c};font-size:20px">{s}{chg:.2f}%</span></div>
  <div class="price-sub">24h 最高 ${hi} ｜ 24h 最低 ${lo} ｜ 24h 成交额 ${vol} 亿</div>
</div>
{spark}
{note}
</section>""".format(
        sym=_esc(symbol), price=format_price(ticker["last_price"]), c=chg_color,
        s=sign, chg=chg, hi=format_price(ticker["high"]), lo=format_price(ticker["low"]),
        vol="{:.1f}".format(ticker["quote_volume"] / 1e8), spark=spark, note=kline_note)


def _news_section(news_items):
    if not news_items:
        return '<section><h2>最新资讯</h2><p class="muted">暂无匹配的最新新闻（可能网络不可用或近期无相关报道）。</p></section>'
    rows = []
    for n in news_items:
        dt = n["published"].strftime("%Y-%m-%d %H:%M") if n["published"] else "时间未知"
        title = _esc(n["title"])
        if n["link"]:
            title = '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(_esc(n["link"]), title)
        rows.append(
            '<div class="news-item"><div class="news-title">{}</div>'
            '<div class="news-meta">{} ｜ {}</div>'
            '<div class="news-summary">{}</div></div>'.format(
                title, _esc(n["source"]), dt, _esc(n["summary"][:160])))
    return '<section><h2>最新资讯（{n} 条）</h2>{rows}</section>'.format(
        n=len(news_items), rows="\n".join(rows))


def _timeline_section(events):
    if not events:
        return '<section><h2>历史大事件时间线</h2><p class="muted">事件库中暂无该币种记录。</p></section>'
    items = []
    for e in events:
        items.append(
            '<div class="tl-item"><div class="tl-date">{d}</div>'
            '<div class="tl-body"><div class="tl-title">{t} {badge} '
            '<span class="tl-cat">{cat}</span></div>'
            '<div class="tl-desc">{desc}</div></div></div>'.format(
                d=_esc(e["date"]), t=_esc(e["title"]), badge=_impact_badge(e.get("impact", "中性")),
                cat=_esc(e.get("category", "")), desc=_esc(e["description"])))
    return ('<section><h2>历史大事件时间线（{} 条，按时间正序）</h2>'
            '<div class="timeline">{}</div></section>').format(len(events), "\n".join(items))


def render_html(symbol, coin_name, ticker, klines, news_items, events):
    """渲染完整 HTML 报告并写入 output/ 目录，返回文件路径。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}（{sym}）时间线资讯报告</title>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background:#f6f7f9;
         color:#222; margin:0; padding:24px; }}
  .container {{ max-width:860px; margin:0 auto; }}
  header {{ background:linear-gradient(135deg,#f0b90b,#f8d33a); border-radius:12px;
            padding:28px 32px; color:#1e2329; }}
  header h1 {{ margin:0 0 6px; font-size:28px; }}
  header .sub {{ font-size:14px; opacity:.75; }}
  section {{ background:#fff; border-radius:12px; padding:24px 28px; margin-top:20px;
             box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  h2 {{ font-size:19px; margin:0 0 16px; border-left:4px solid #f0b90b; padding-left:10px; }}
  .price-card {{ display:flex; flex-direction:column; gap:6px; margin-bottom:12px; }}
  .price-main {{ font-size:34px; font-weight:700; }}
  .price-sub {{ color:#707a8a; font-size:14px; }}
  .muted {{ color:#8a8f98; font-size:13px; }}
  .news-item {{ padding:12px 0; border-bottom:1px dashed #e6e8eb; }}
  .news-item:last-child {{ border-bottom:none; }}
  .news-title a {{ color:#1e2329; font-weight:600; text-decoration:none; }}
  .news-title a:hover {{ color:#c99400; }}
  .news-meta {{ color:#8a8f98; font-size:12px; margin:4px 0; }}
  .news-summary {{ color:#555; font-size:13px; line-height:1.6; }}
  .timeline {{ position:relative; padding-left:20px; border-left:2px solid #f0b90b; }}
  .tl-item {{ position:relative; padding:0 0 20px 18px; }}
  .tl-item::before {{ content:""; position:absolute; left:-27px; top:5px; width:10px; height:10px;
                      border-radius:50%; background:#f0b90b; border:2px solid #fff;
                      box-shadow:0 0 0 2px #f0b90b; }}
  .tl-date {{ color:#c99400; font-weight:700; font-size:14px; }}
  .tl-title {{ font-weight:600; margin:4px 0; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .tl-cat {{ color:#8a8f98; background:#f2f3f5; border-radius:4px; padding:1px 8px; font-size:12px; }}
  .tl-desc {{ color:#555; font-size:13px; line-height:1.7; }}
  footer {{ text-align:center; color:#8a8f98; font-size:12px; padding:24px 0; }}
</style></head>
<body><div class="container">
<header>
  <h1>{name}（{sym}）时间线资讯报告</h1>
  <div class="sub">由 Crypto Timeline Agent 自动生成 ｜ 生成时间：{now}</div>
</header>
{price}
{news}
{timeline}
<footer>本报告仅供学习研究，不构成任何投资建议。历史事件由人工整理，如有疏漏欢迎提交 PR 补充。</footer>
</div></body></html>""".format(
        name=_esc(coin_name), sym=_esc(symbol), now=now,
        price=_price_section(symbol, ticker, klines),
        news=_news_section(news_items),
        timeline=_timeline_section(events))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "report_{}_{}.html".format(
        symbol.upper(), datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path


def build_markdown(symbol, coin_name, ticker, klines, news_items, events):
    """构建 Markdown 报告文本并返回字符串。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# {}（{}）时间线资讯报告".format(coin_name, symbol.upper()),
        "",
        "> 由 Crypto Timeline Agent 自动生成 ｜ 生成时间：{}".format(now),
        "",
        "## 实时行情（数据来源：{}）".format(ticker["source"] if ticker else "公开行情"),
        "",
    ]
    if ticker:
        sign = "+" if ticker["change_pct"] >= 0 else ""
        lines += [
            "- 最新价：**${}**（{}{:.2f}% / 24h）".format(
                format_price(ticker["last_price"]), sign, ticker["change_pct"]),
            "- 24h 最高 / 最低：${} / ${}".format(
                format_price(ticker["high"]), format_price(ticker["low"])),
            "- 24h 成交额：${}".format(format_volume(ticker.get("quote_volume"))),
        ]
        if klines:
            lines.append("- 近 {} 日收盘：{} → {}".format(len(klines), klines[0][0], klines[-1][0]))
    else:
        lines.append("行情获取失败。")
    lines += ["", "## 最新资讯", ""]
    if news_items:
        for n in news_items:
            dt = n["published"].strftime("%Y-%m-%d %H:%M") if n["published"] else "时间未知"
            link = n["link"] or ""
            lines.append("- **[{}]({})** ｜ {} ｜ {}".format(n["title"], link, n["source"], dt))
            if n["summary"]:
                lines.append("  - {}".format(n["summary"][:160]))
    else:
        lines.append("暂无匹配的最新新闻。")
    lines += ["", "## 历史大事件时间线", ""]
    if events:
        lines.append("| 日期 | 事件 | 分类 | 影响 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for e in events:
            lines.append("| {} | {} | {} | {} | {} |".format(
                e["date"], e["title"], e.get("category", ""), e.get("impact", ""),
                e["description"].replace("|", "｜")))
    else:
        lines.append("事件库中暂无该币种记录。")
    lines += ["", "---", "本报告仅供学习研究，不构成任何投资建议。", ""]
    return "\n".join(lines)


def render_markdown(symbol, coin_name, ticker, klines, news_items, events):
    """渲染 Markdown 报告并写入 output/ 目录，返回文件路径。"""
    text = build_markdown(symbol, coin_name, ticker, klines, news_items, events)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "report_{}_{}.md".format(
        symbol.upper(), datetime.now().strftime("%Y%m%d_%H%M%S")))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
