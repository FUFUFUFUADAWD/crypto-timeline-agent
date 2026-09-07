# -*- coding: utf-8 -*-
"""事件数据库模块：加载并查询多币种历史大事件时间线。

数据来源：data/events.json（人工整理 + 社区维护，可持续扩充）
"""
import json
import os

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "events.json")

_cache = None


def _load():
    """加载事件数据库（带缓存）。"""
    global _cache
    if _cache is None:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def supported_coins():
    """返回所有支持的币种代码列表，如 ['BTC', 'ETH', ...]。"""
    return list(_load().keys())


def get_coin(symbol):
    """按币种代码获取完整信息；支持大小写不敏感，找不到返回 None。"""
    if not symbol:
        return None
    return _load().get(symbol.strip().upper())


def resolve_symbol(text):
    """从任意文本中识别币种（支持代码 / 英文名 / 中文名），返回币种代码或 None。"""
    if not text:
        return None
    lowered = text.lower()
    for symbol, info in _load().items():
        if symbol.lower() in lowered.split():
            return symbol
        for kw in info.get("keywords", []):
            if kw.lower() in lowered:
                return symbol
    return None


def get_events(symbol, start=None, end=None, category=None):
    """查询某币种的历史事件时间线。

    参数:
        symbol:   币种代码，如 'BTC'
        start:    起始日期字符串 'YYYY-MM-DD' 或 'YYYY'（含）
        end:      结束日期字符串 'YYYY-MM-DD' 或 'YYYY'（含）
        category: 事件分类过滤，如 '监管政策'
    返回:
        按日期升序排列的事件列表
    """
    coin = get_coin(symbol)
    if not coin:
        return []
    events = sorted(coin.get("events", []), key=lambda e: e["date"])
    if start:
        start = start if len(start) > 4 else start + "-01-01"
        events = [e for e in events if e["date"] >= start]
    if end:
        end = end if len(end) > 4 else end + "-12-31"
        events = [e for e in events if e["date"] <= end]
    if category:
        events = [e for e in events if e.get("category") == category]
    return events


def categories(symbol=None):
    """返回事件分类列表（可指定币种，默认全部币种的去重分类）。"""
    db = _load()
    cats = set()
    coins = [db[symbol.upper()]] if symbol and symbol.upper() in db else db.values()
    for coin in coins:
        for e in coin.get("events", []):
            cats.add(e.get("category", "其他"))
    return sorted(cats)
