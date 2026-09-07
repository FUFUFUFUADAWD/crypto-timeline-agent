# -*- coding: utf-8 -*-
"""行情模块：多数据源自动容灾的实时价格与 K 线获取。

数据源按优先级依次尝试（均为无需 API Key 的公共接口）：
  1. 币安  Binance  /api/v3
  2. 欧易  OKX      /api/v5
  3. CoinGecko      /api/v3/simple/price（仅价格，无 K 线）
  4. CoinPaprika    /v1/tickers（仅价格，无 K 线）
任一源超时/失败自动切换到下一个，保证在不同网络环境下都尽量可用。
"""
import json
import urllib.request
import urllib.error

UA = "crypto-timeline-agent/1.0"
TIMEOUT = 12


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ticker_binance(binance_symbol):
    d = _get_json("https://api.binance.com/api/v3/ticker/24hr?symbol=" + binance_symbol)
    return {
        "source": "Binance",
        "last_price": float(d["lastPrice"]),
        "change_pct": float(d["priceChangePercent"]),
        "high": float(d["highPrice"]),
        "low": float(d["lowPrice"]),
        "quote_volume": float(d["quoteVolume"]),
    }


def _ticker_okx(inst_id):
    d = _get_json("https://www.okx.com/api/v5/market/ticker?instId=" + inst_id)
    row = d["data"][0]
    last = float(row["last"])
    open24 = float(row["open24h"])
    return {
        "source": "OKX",
        "last_price": last,
        "change_pct": (last - open24) / open24 * 100 if open24 else 0.0,
        "high": float(row["high24h"]),
        "low": float(row["low24h"]),
        "quote_volume": float(row["volCcy24h"]) * last,
    }


def _ticker_coingecko(cg_id):
    d = _get_json("https://api.coingecko.com/api/v3/simple/price?ids={}"
                  "&vs_currencies=usd&include_24hr_change=true".format(cg_id))
    row = d[cg_id]
    return {
        "source": "CoinGecko",
        "last_price": float(row["usd"]),
        "change_pct": float(row.get("usd_24h_change") or 0.0),
        "high": None,
        "low": None,
        "quote_volume": None,
    }


def _ticker_coinpaprika(cp_id):
    d = _get_json("https://api.coinpaprika.com/v1/tickers/" + cp_id)
    q = d["quotes"]["USD"]
    return {
        "source": "CoinPaprika",
        "last_price": float(q["price"]),
        "change_pct": float(q.get("percent_change_24h") or 0.0),
        "high": None,
        "low": None,
        "quote_volume": float(q.get("volume_24h") or 0.0),
    }


# 各币种在不同数据源的标识
_IDS = {
    "BTC":  {"okx": "BTC-USDT",  "cg": "bitcoin",   "cp": "btc-bitcoin"},
    "ETH":  {"okx": "ETH-USDT",  "cg": "ethereum",  "cp": "eth-ethereum"},
    "BNB":  {"okx": "BNB-USDT",  "cg": "binancecoin", "cp": "bnb-binance-coin"},
    "SOL":  {"okx": "SOL-USDT",  "cg": "solana",    "cp": "sol-solana"},
    "XRP":  {"okx": "XRP-USDT",  "cg": "ripple",    "cp": "xrp-xrp"},
    "DOGE": {"okx": "DOGE-USDT", "cg": "dogecoin",  "cp": "doge-dogecoin"},
    "ADA":  {"okx": "ADA-USDT",  "cg": "cardano",   "cp": "ada-cardano"},
    "LTC":  {"okx": "LTC-USDT",  "cg": "litecoin",  "cp": "ltc-litecoin"},
    "TRX":  {"okx": "TRX-USDT",  "cg": "tron",      "cp": "trx-tron"},
    "ZEC":  {"okx": "ZEC-USDT",  "cg": "zcash",     "cp": "zec-zcash"},
}


def get_ticker(symbol, binance_symbol=None):
    """获取 24 小时行情快照，多源容灾。

    参数:
        symbol:         币种代码，如 'BTC'
        binance_symbol: 币安交易对（可选，默认 '<symbol>USDT'）
    返回: dict（含 source 字段标注数据来源），全部失败返回 None
    """
    symbol = symbol.upper()
    binance_symbol = binance_symbol or (symbol + "USDT")
    ids = _IDS.get(symbol, {"okx": symbol + "-USDT", "cg": symbol.lower(), "cp": symbol.lower()})

    providers = [
        ("Binance", lambda: _ticker_binance(binance_symbol)),
        ("OKX", lambda: _ticker_okx(ids["okx"])),
        ("CoinGecko", lambda: _ticker_coingecko(ids["cg"])),
        ("CoinPaprika", lambda: _ticker_coinpaprika(ids["cp"])),
    ]
    for name, fn in providers:
        try:
            t = fn()
            t["symbol"] = symbol
            return t
        except Exception as e:
            print("[行情] {} 源失败，尝试下一个: {}".format(name, e))
    print("[行情] 所有行情源均不可用。")
    return None


def get_klines(symbol, interval="1d", limit=30, binance_symbol=None):
    """获取 K 线收盘价序列 [(日期, 收盘价), ...]，多源容灾，失败返回空列表。"""
    symbol = symbol.upper()
    binance_symbol = binance_symbol or (symbol + "USDT")
    import datetime

    def _fmt(ts_ms):
        return datetime.datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")

    # 源 1：币安
    try:
        rows = _get_json("https://api.binance.com/api/v3/klines?symbol={}&interval={}&limit={}"
                         .format(binance_symbol, interval, limit))
        return [(_fmt(r[0]), float(r[4])) for r in rows]
    except Exception as e:
        print("[行情] Binance K线失败，尝试 OKX: {}".format(e))

    # 源 2：OKX（bar 参数：1d -> 1D）
    try:
        bar = {"1d": "1D", "4h": "4H", "1h": "1H"}.get(interval, "1D")
        inst = _IDS.get(symbol, {}).get("okx", symbol + "-USDT")
        d = _get_json("https://www.okx.com/api/v5/market/candles?instId={}&bar={}&limit={}"
                      .format(inst, bar, limit))
        rows = sorted(d["data"], key=lambda r: int(r[0]))
        return [(_fmt(int(r[0])), float(r[4])) for r in rows]
    except Exception as e:
        print("[行情] OKX K线也失败: {}".format(e))
    return []


def format_price(p):
    """价格格式化：大额加千分位，小额保留足够精度。"""
    if p is None:
        return "-"
    if p >= 100:
        return "{:,.2f}".format(p)
    if p >= 1:
        return "{:,.4f}".format(p).rstrip("0").rstrip(".")
    return "{:.6f}".format(p).rstrip("0").rstrip(".")


def format_volume(v):
    """成交额格式化，None 安全。"""
    if v is None:
        return "-"
    return "{:.1f} 亿".format(v / 1e8)
