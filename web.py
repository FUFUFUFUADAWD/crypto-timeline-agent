# -*- coding: utf-8 -*-
"""Web 控制台：零依赖本地 Web 界面「链事纪」。

启动方式: python agent.py web [--port 8000]
浏览器打开 http://127.0.0.1:8000 即可使用可视化分析台。

后端仅用 Python 标准库 http.server 提供 JSON API，前端为 static/index.html 单页应用。
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import events_db
import market
import news as news_mod
import report as report_mod

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")


# ---------------- API 逻辑 ----------------

def api_coins():
    coins = []
    for sym in events_db.supported_coins():
        c = events_db.get_coin(sym)
        coins.append({"symbol": sym, "name": c["name"], "name_en": c["name_en"],
                      "event_count": len(c["events"])})
    return {"coins": coins, "categories": events_db.categories()}


def api_timeline(q):
    sym = q.get("coin", "BTC").upper()
    coin = events_db.get_coin(sym)
    if not coin:
        return {"error": "不支持的币种: " + sym}
    events = events_db.get_events(sym, start=q.get("from") or None,
                                  end=q.get("to") or None,
                                  category=q.get("category") or None)
    return {"coin": sym, "name": coin["name"], "events": events, "count": len(events)}


def api_news(q):
    sym = q.get("coin", "BTC").upper()
    coin = events_db.get_coin(sym)
    if not coin:
        return {"error": "不支持的币种: " + sym}
    limit = int(q.get("limit", 10))
    items = news_mod.fetch_news(keywords=coin["keywords"], limit=limit)
    for n in items:  # datetime -> str 由 default=str 兜底，这里显式格式化
        if n.get("published"):
            n["published"] = n["published"].strftime("%Y-%m-%d %H:%M")
    return {"coin": sym, "name": coin["name"], "news": items, "count": len(items)}


def api_price(q):
    sym = q.get("coin", "BTC").upper()
    coin = events_db.get_coin(sym)
    if not coin:
        return {"error": "不支持的币种: " + sym}
    t = market.get_ticker(sym, coin["binance_symbol"], timeout=8)
    klines = market.get_klines(sym, limit=int(q.get("days", 30)),
                               binance_symbol=coin["binance_symbol"], timeout=8)
    return {"coin": sym, "name": coin["name"], "ticker": t,
            "klines": [{"date": d, "close": c} for d, c in klines]}


def api_overview():
    """全部币种行情总览：24h / 7日 / 30日 涨跌 + 30日相对低点。"""
    def one(sym):
        coin = events_db.get_coin(sym)
        row = {"symbol": sym, "name": coin["name"], "name_en": coin["name_en"]}
        t = market.get_ticker(sym, coin["binance_symbol"], timeout=5)
        if t:
            row.update(price=t["last_price"], change24=round(t["change_pct"], 2),
                       source=t["source"])
        k = market.get_klines(sym, limit=31, binance_symbol=coin["binance_symbol"], timeout=5)
        if k:
            closes = [c for _, c in k]
            last = closes[-1]
            if len(closes) >= 8 and closes[-8]:
                row["change7"] = round((last / closes[-8] - 1) * 100, 2)
            if closes[0]:
                row["change30"] = round((last / closes[0] - 1) * 100, 2)
            lo = min(closes)
            if lo:
                row["off_low"] = round((last - lo) / lo * 100, 2)
        return row
    with ThreadPoolExecutor(max_workers=10) as ex:
        rows = list(ex.map(one, events_db.supported_coins()))
    return {"rows": rows}


def api_report_md(q):
    """生成某币种 Markdown 报告文本（供前端复制/下载）。"""
    sym = q.get("coin", "BTC").upper()
    coin = events_db.get_coin(sym)
    if not coin:
        return {"error": "不支持的币种: " + sym}
    t = market.get_ticker(sym, coin["binance_symbol"], timeout=8)
    klines = market.get_klines(sym, limit=30, binance_symbol=coin["binance_symbol"], timeout=8)
    items = news_mod.fetch_news(keywords=coin["keywords"], limit=8)
    events = events_db.get_events(sym)
    md = report_mod.build_markdown(sym, coin["name"], t, klines, items, events)
    return {"coin": sym, "name": coin["name"], "markdown": md}


# ---------------- HTTP 服务 ----------------

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif u.path == "/api/coins":
                self._send(200, _json_bytes(api_coins()))
            elif u.path == "/api/timeline":
                self._send(200, _json_bytes(api_timeline(q)))
            elif u.path == "/api/news":
                self._send(200, _json_bytes(api_news(q)))
            elif u.path == "/api/price":
                self._send(200, _json_bytes(api_price(q)))
            elif u.path == "/api/overview":
                self._send(200, _json_bytes(api_overview()))
            elif u.path == "/api/report_md":
                self._send(200, _json_bytes(api_report_md(q)))
            else:
                self._send(404, _json_bytes({"error": "not found"}))
        except Exception as e:
            self._send(500, _json_bytes({"error": str(e)}))

    def log_message(self, fmt, *args):
        line = fmt % args
        if "/api/" in line:
            print("[Web] " + line)


def run(port=8000):
    # 部署环境：通过 PORT 环境变量指定端口并绑定 0.0.0.0；本地默认 127.0.0.1
    env_port = os.environ.get("PORT")
    if env_port:
        host, port = "0.0.0.0", int(env_port)
    else:
        host = "127.0.0.1"
    server = ThreadingHTTPServer((host, port), Handler)
    print("=" * 56)
    print("  链事纪 · Crypto Timeline Agent Web 控制台已启动")
    print("  请在浏览器打开:  http://{}:{}".format(
        "127.0.0.1" if host == "0.0.0.0" else host, port))
    print("  按 Ctrl+C 停止服务")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
