# -*- coding: utf-8 -*-
"""编年史引擎：把历史事件与币安官方历史行情对齐，产出「事件 × 市场反应」。

数据来源（全部来自币安官方、任何人可复现，不需要上网工具）
  官方开源数据仓库 data.binance.vision 的**现货月度日线归档**：
    /data/spot/monthly/klines/<PAIR>/1d/<PAIR>-1d-<YYYY-MM>.zip
  —— 一个月一个文件，下载一次就覆盖该月全部事件；
  —— 币安上市之前的月份返回 404，如实标注「当时币安尚无该交易对」，不编造价格。

口径（全部印在输出里）
  · 事件当日：事件日期当天；当天没有交易数据时，取其后第一个交易日；
  · 当日涨跌：(当日收盘 ÷ 前一交易日收盘 − 1) × 100%；
  · 后续反应：以事件当日收盘为基准，第 5 / 30 个**交易日**收盘的累计涨跌；
  · 距历史高点：事件当日收盘相对「至当日为止的历史最高价」的回撤；
  · 全部为官方收盘价，不复权、不含手续费、不预测后市。
"""
import io
import json
import os
import zipfile
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

UA = "crypto-timeline-agent/1.0 (chronicle)"
ARCHIVE = "https://data.binance.vision"
TIMEOUT = 60
BASE_PREFIXES = ("", "1000", "10000", "100000")   # 官方面值币代码前缀


class NoArchive(Exception):
    """该月份在官方归档里不存在（通常是当时还没上市）。"""


def _opener():
    # 空 dict = 显式忽略系统代理：官方数据域直连本就可达，避免被本机代理假死拖死
    return build_opener(ProxyHandler({}))


def month_url(pair, ym):
    return (f"{ARCHIVE}/data/spot/monthly/klines/{pair}/1d/{pair}-1d-{ym}.zip")


def _http_bytes(url, timeout=TIMEOUT):
    req = Request(url, headers={"User-Agent": UA})
    try:
        with _opener().open(req, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as exc:
        if exc.code == 404:
            raise NoArchive(url)
        raise


def read_zip_csv(raw):
    """读官方归档 ZIP 里的 CSV。现货日线文件**没有表头**，但仍按首列是否数字兜底判断。"""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace").read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines and not lines[0].split(",")[0].strip().replace(".", "").isdigit():
        lines = lines[1:]
    return [ln.split(",") for ln in lines]


def _to_ms(v):
    """官方归档里的时间戳可能是毫秒（13 位）或微秒（16 位），按量级自适应。"""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    while n > 10 ** 14:
        n //= 1000
    return n


def fetch_month(pair, ym, timeout=TIMEOUT):
    """取某个月的官方日线，返回 {日期: bar}。找不到该月归档抛 NoArchive。"""
    raw = _http_bytes(month_url(pair, ym), timeout=timeout)
    bars = {}
    for cells in read_zip_csv(raw):
        if len(cells) < 6:
            continue
        ms = _to_ms(cells[0])
        if ms is None:
            continue
        d = datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        try:
            bars[d] = {"open": float(cells[1]), "high": float(cells[2]),
                       "low": float(cells[3]), "close": float(cells[4]),
                       "volume": float(cells[5])}
        except (TypeError, ValueError):
            continue
    if not bars:
        raise NoArchive(month_url(pair, ym))
    return bars


def _months_needed(events, lookahead_days=45):
    """事件日所在月 + 其后 45 天覆盖的月（用来算 5/30 个交易日后的反应）。"""
    months = set()
    for e in events:
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        for delta in (0, lookahead_days):
            months.add((d + timedelta(days=delta)).strftime("%Y-%m"))
    return sorted(months)


def load_bars(pair, events, say=None, timeout=TIMEOUT):
    """把需要的月份全部拉下来（按月缓存一次），返回 (bars, 命中月份, 缺档月份)。"""
    bars, hit, miss = {}, [], []
    for ym in _months_needed(events):
        try:
            month_bars = fetch_month(pair, ym, timeout=timeout)
            bars.update(month_bars)
            hit.append(ym)
        except NoArchive:
            miss.append(ym)
        except Exception as exc:
            miss.append(f"{ym}（{type(exc).__name__}）")
        if say:
            say(f"  取官方归档 {pair} {ym} → {len(bars)} 个交易日累计")
    return bars, hit, miss


def align_events(events, bars, max_shift_days=5):
    """把每条事件与官方日线对齐。

    ⚠️ 关键纪律：**只给归档覆盖范围内的事件配行情**。
    事件日与取到的交易日相差超过 `max_shift_days` 天，就判为「早于归档起点 / 当月归档缺失」，
    如实留空并写明原因 —— 绝不把 2010 年的事件配上 2017 年的价格（那是最严重的数据误导）。
    """
    dates = sorted(bars)
    first = dates[0] if dates else None
    first_d = datetime.strptime(first, "%Y-%m-%d").date() if first else None
    entries = []
    for e in events:
        row = dict(e)
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            row["market"], row["market_note"] = None, "事件日期无法解析"
            entries.append(row)
            continue

        i = bisect_left(dates, d.isoformat())
        if i >= len(dates):
            row["market"], row["market_note"] = None, "晚于官方归档最后一天，暂无后续行情"
            entries.append(row)
            continue

        day_key = dates[i]
        gap = (datetime.strptime(day_key, "%Y-%m-%d").date() - d).days
        if gap > max_shift_days:
            if first_d and d < first_d:
                row["market_note"] = (f"事件日早于官方归档起点（{first}），"
                                      "当时币安尚无该交易对，市场反应如实留空")
            else:
                row["market_note"] = f"事件日 {d.isoformat()} 所在时段官方归档缺失，如实留空"
            row["market"] = None
            entries.append(row)
            continue

        day = bars[day_key]
        prev = bars[dates[i - 1]]["close"] if i > 0 else None
        base = day["close"]

        def after(n):
            j = i + n
            if j < len(dates) and base:
                return (bars[dates[j]]["close"] / base - 1) * 100
            return None

        high_so_far = max(bars[k]["high"] for k in dates[:i + 1])
        row["market"] = {
            "bar_date": day_key,
            "same_day": gap == 0,
            "shift_days": gap,
            "close": base,
            "change_1d": ((base / prev - 1) * 100) if prev else None,
            "change_5d": after(5),
            "change_30d": after(30),
            "drawdown_from_high": ((base / high_so_far - 1) * 100) if high_so_far else None,
        }
        entries.append(row)
    return entries


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def summarize(entries):
    """史评：按影响方向与事件分类，统计事件后市场的平均反应（透明、可复算）。"""

    def agg(rows):
        r30 = [r.get("change_30d") for r in rows]
        r30v = [v for v in r30 if v is not None]
        return {
            "样本数": len(rows),
            "有官方行情样本": len(r30v),
            "平均当日涨跌": _avg([r.get("change_1d") for r in rows]),
            "平均后5个交易日": _avg([r.get("change_5d") for r in rows]),
            "平均后30个交易日": _avg(r30),
            "30日上涨占比": (sum(1 for v in r30v if v > 0) / len(r30v) * 100) if r30v else None,
        }

    with_market = [e.get("market") for e in entries if e.get("market")]
    summary = {"总体": agg(with_market), "按影响": {}, "按分类": {}}
    for key in ("利好", "利空", "中性"):
        rows = [e["market"] for e in entries if e.get("market") and e.get("impact") == key]
        if rows:
            summary["按影响"][key] = agg(rows)
    cats = {}
    for e in entries:
        if e.get("market"):
            cats.setdefault(e.get("category") or "未分类", []).append(e["market"])
    for cat, rows in sorted(cats.items(), key=lambda kv: -len(kv[1])):
        summary["按分类"][cat] = agg(rows)
    return summary


def build(coin, events, pair, say=None, timeout=TIMEOUT):
    """编年史主流程：取官方档案 → 逐条对齐 → 统计史评。"""
    bars, hit, miss = load_bars(pair, events, say=say, timeout=timeout)
    entries = align_events(events, bars)
    notes, missing = [], []
    if bars:
        span = f"{min(bars)} ~ {max(bars)}"
        notes.append(f"官方归档覆盖 {span}，共 {len(bars)} 个交易日、{len(hit)} 个月度文件")
    else:
        missing.append("该币种在官方归档中没有任何日线（可能尚未上市）")
    if miss:
        missing.append("以下月份官方归档不存在：" + "、".join(miss[:8])
                       + (" 等" if len(miss) > 8 else ""))
    no_market = [e for e in entries if not e.get("market")]
    if no_market:
        notes.append(f"{len(no_market)} 条事件早于官方归档起点（当时币安尚无该交易对），"
                     "市场反应如实留空，不虚构价格")
    return {"pair": pair, "coin": coin, "entries": entries,
            "summary": summarize(entries), "notes": notes, "missing": missing,
            "bars": len(bars), "months_hit": hit, "months_missing": miss}
