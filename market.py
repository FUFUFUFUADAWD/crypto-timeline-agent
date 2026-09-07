# -*- coding: utf-8 -*-
"""行情模块：多数据源自动容灾的实时价格与 K 线获取。

数据源按优先级依次尝试（均为无需 API Key 的公共接口）：
  1. 币安 Binance  官方公开行情域名 data-api.binance.vision，中国大陆可直连
  2. Gate.io      中国大陆可直连，含 24h 行情与 K 线
  3. 欧易 OKX      海外网络可用
  4. CoinLore     中国大陆可直连，仅价格
  5. CoinGecko    仅价格（国内不可直连，作为海外兜底）
  6. CoinPaprika  仅价格（海外兜底）
任一源超时/失败自动切换到下一个，保证在中国大陆及海外网络环境下都尽量可用。
"""
import json
import urllib.request
import urllib.error

UA = "crypto-timeline-agent/1.0"
TIMEOUT = 12


def _get_json(url, timeout=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ticker_gateio(pair, timeout=None):
    rows = _get_json("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=" + pair,
                     timeout=timeout)
    row = rows[0] if isinstance(rows, list) else rows
    return {
        "source": "Gate.io",
        "last_price": float(row["last"]),
        "change_pct": float(row.get("change_percentage") or 0.0),
        "high": float(row["high_24h"]),
        "low": float(row["low_24h"]),
        "quote_volume": float(row.get("quote_volume") or 0.0),
    }


def _ticker_binance(binance_symbol, timeout=None):
    # data-api.binance.vision 是币安官方公开行情域名，中国大陆可直连
    d = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr?symbol=" + binance_symbol,
                  timeout=timeout)
    return {
        "source": "Binance",
        "last_price": float(d["lastPrice"]),
        "change_pct": float(d["priceChangePercent"]),
        "high": float(d["highPrice"]),
        "low": float(d["lowPrice"]),
        "quote_volume": float(d["quoteVolume"]),
    }


def _ticker_okx(inst_id, timeout=None):
    d = _get_json("https://www.okx.com/api/v5/market/ticker?instId=" + inst_id, timeout=timeout)
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


def _ticker_coinlore(symbol, timeout=None):
    """CoinLore 免费行情（国内可直连）。从 top100 列表中按 symbol 匹配。"""
    d = _get_json("https://api.coinlore.net/api/tickers/?start=0&limit=100", timeout=timeout)
    rows = d["data"] if isinstance(d, dict) and "data" in d else d
    for row in rows:
        if row.get("symbol", "").upper() == symbol:
            return {
                "source": "CoinLore",
                "last_price": float(row["price_usd"]),
                "change_pct": float(row.get("percent_change_24h") or 0.0),
                "high": None,
                "low": None,
                "quote_volume": float(row.get("volume24") or 0.0),
            }
    raise ValueError("CoinLore 未收录 " + symbol)


def _ticker_coingecko(cg_id, timeout=None):
    d = _get_json("https://api.coingecko.com/api/v3/simple/price?ids={}"
                  "&vs_currencies=usd&include_24hr_change=true".format(cg_id), timeout=timeout)
    row = d[cg_id]
    return {
        "source": "CoinGecko",
        "last_price": float(row["usd"]),
        "change_pct": float(row.get("usd_24h_change") or 0.0),
        "high": None,
        "low": None,
        "quote_volume": None,
    }


def _ticker_coinpaprika(cp_id, timeout=None):
    d = _get_json("https://api.coinpaprika.com/v1/tickers/" + cp_id, timeout=timeout)
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
    "BTC":  {"gate": "BTC_USDT",  "okx": "BTC-USDT",  "cg": "bitcoin",     "cp": "btc-bitcoin"},
    "ETH":  {"gate": "ETH_USDT",  "okx": "ETH-USDT",  "cg": "ethereum",    "cp": "eth-ethereum"},
    "BNB":  {"gate": "BNB_USDT",  "okx": "BNB-USDT",  "cg": "binancecoin", "cp": "bnb-binance-coin"},
    "SOL":  {"gate": "SOL_USDT",  "okx": "SOL-USDT",  "cg": "solana",      "cp": "sol-solana"},
    "XRP":  {"gate": "XRP_USDT",  "okx": "XRP-USDT",  "cg": "ripple",      "cp": "xrp-xrp"},
    "DOGE": {"gate": "DOGE_USDT", "okx": "DOGE-USDT", "cg": "dogecoin",    "cp": "doge-dogecoin"},
    "ADA":  {"gate": "ADA_USDT",  "okx": "ADA-USDT",  "cg": "cardano",     "cp": "ada-cardano"},
    "LTC":  {"gate": "LTC_USDT",  "okx": "LTC-USDT",  "cg": "litecoin",    "cp": "ltc-litecoin"},
    "TRX":  {"gate": "TRX_USDT",  "okx": "TRX-USDT",  "cg": "tron",        "cp": "trx-tron"},
    "ZEC":  {"gate": "ZEC_USDT",  "okx": "ZEC-USDT",  "cg": "zcash",       "cp": "zec-zcash"},
}


def get_ticker(symbol, binance_symbol=None, timeout=None):
    """获取 24 小时行情快照，多源容灾（国内网络优先 Gate.io）。

    参数:
        symbol:         币种代码，如 'BTC'
        binance_symbol: 币安交易对（可选，默认 '<symbol>USDT'）
    返回: dict（含 source 字段标注数据来源），全部失败返回 None
    """
    symbol = symbol.upper()
    binance_symbol = binance_symbol or (symbol + "USDT")
    ids = _IDS.get(symbol, {"gate": symbol + "_USDT", "okx": symbol + "-USDT",
                            "cg": symbol.lower(), "cp": symbol.lower()})

    providers = [
        ("Binance", lambda: _ticker_binance(binance_symbol, timeout)),
        ("Gate.io", lambda: _ticker_gateio(ids["gate"], timeout)),
        ("OKX", lambda: _ticker_okx(ids["okx"], timeout)),
        ("CoinLore", lambda: _ticker_coinlore(symbol, timeout)),
        ("CoinGecko", lambda: _ticker_coingecko(ids["cg"], timeout)),
        ("CoinPaprika", lambda: _ticker_coinpaprika(ids["cp"], timeout)),
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


def get_klines(symbol, interval="1d", limit=30, binance_symbol=None, timeout=None):
    """获取 K 线收盘价序列 [(日期, 收盘价), ...]，多源容灾，失败返回空列表。"""
    symbol = symbol.upper()
    binance_symbol = binance_symbol or (symbol + "USDT")
    import datetime

    def _fmt_ms(ts_ms):
        return datetime.datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")

    # 源 1：币安公开行情域名（国内可直连）
    try:
        rows = _get_json("https://data-api.binance.vision/api/v3/klines?symbol={}&interval={}&limit={}"
                         .format(binance_symbol, interval, limit), timeout=timeout)
        return [(_fmt_ms(r[0]), float(r[4])) for r in rows]
    except Exception as e:
        print("[行情] Binance K线失败，尝试 Gate.io: {}".format(e))

    # 源 2：Gate.io（国内可直连；返回 [时间(秒), 成交额, 收盘, 最高, 最低, 开盘, ...]）
    try:
        pair = _IDS.get(symbol, {}).get("gate", symbol + "_USDT")
        bar = {"1d": "1d", "4h": "4h", "1h": "1h"}.get(interval, "1d")
        rows = _get_json("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={}"
                         "&interval={}&limit={}".format(pair, bar, limit), timeout=timeout)
        rows = sorted(rows, key=lambda r: int(r[0]))
        return [(datetime.datetime.utcfromtimestamp(int(r[0])).strftime("%Y-%m-%d"),
                 float(r[2])) for r in rows]
    except Exception as e:
        print("[行情] Gate.io K线失败，尝试 OKX: {}".format(e))

    # 源 3：OKX
    try:
        bar = {"1d": "1D", "4h": "4H", "1h": "1H"}.get(interval, "1D")
        inst = _IDS.get(symbol, {}).get("okx", symbol + "-USDT")
        d = _get_json("https://www.okx.com/api/v5/market/candles?instId={}&bar={}&limit={}"
                      .format(inst, bar, limit), timeout=timeout)
        rows = sorted(d["data"], key=lambda r: int(r[0]))
        return [(_fmt_ms(int(r[0])), float(r[4])) for r in rows]
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
