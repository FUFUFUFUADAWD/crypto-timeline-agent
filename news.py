# -*- coding: utf-8 -*-
"""新闻模块：抓取主流加密货币媒体 RSS，并按币种关键词过滤。

仅使用 Python 标准库（urllib + xml.etree），无需安装任何依赖。
"""
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = "crypto-timeline-agent/1.0"

# 主流加密货币媒体 RSS 源（中英文混合，失效源会被自动跳过）
FEEDS = [
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
    {"name": "Decrypt", "url": "https://decrypt.co/feed"},
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml"},
    {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
]


def _parse_date(entry, atom):
    """解析条目发布时间，统一返回 UTC datetime；失败返回 None。"""
    if atom:
        for tag in ("published", "updated"):
            el = entry.find(tag, _ATOM_NS)
            if el is not None and el.text:
                try:
                    return datetime.fromisoformat(el.text.replace("Z", "+00:00"))
                except ValueError:
                    pass
        return None
    el = entry.find("pubDate")
    if el is None:
        el = entry.find("date")
    if el is not None and el.text:
        try:
            dt = parsedate_to_datetime(el.text)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    return None


_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def _parse_feed(xml_bytes, source):
    """解析单个 RSS/Atom 源，返回新闻条目列表。"""
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    atom = root.tag.endswith("}feed")
    entries = root.findall("a:entry", _ATOM_NS) if atom else root.findall(".//item")
    for entry in entries:
        if atom:
            title_el = entry.find("a:title", _ATOM_NS)
            link_el = entry.find("a:link", _ATOM_NS)
            desc_el = entry.find("a:summary", _ATOM_NS)
            title = title_el.text if title_el is not None else ""
            link = link_el.get("href", "") if link_el is not None else ""
            desc = desc_el.text if desc_el is not None else ""
        else:
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            desc = (entry.findtext("description") or "")
        desc_text = re.sub(r"<[^>]+>", "", desc or "").strip()
        dt = _parse_date(entry, atom)
        if title:
            items.append({
                "title": title.strip(),
                "link": link,
                "summary": desc_text[:300],
                "published": dt,
                "source": source,
            })
    return items


def fetch_news(keywords=None, limit=20, per_feed=40):
    """抓取全部 RSS 源并按关键词过滤。

    参数:
        keywords: 关键词列表（如 ['bitcoin', 'btc', '比特币']）；None 表示不过滤
        limit:    返回的最大条数（按时间倒序）
        per_feed: 每个源最多解析的条目数
    """
    all_items = []
    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=12) as resp:
                xml_bytes = resp.read()
            all_items.extend(_parse_feed(xml_bytes, feed["name"])[:per_feed])
        except Exception as e:  # 单个源失败不影响整体
            print("[新闻] 源 {} 抓取失败，已跳过: {}".format(feed["name"], e))

    if keywords:
        kws = [k.lower() for k in keywords]
        def hit(item):
            text = (item["title"] + " " + item["summary"]).lower()
            return any(k in text for k in kws)
        all_items = [i for i in all_items if hit(i)]

    all_items.sort(key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc),
                   reverse=True)
    # 按标题去重
    seen, result = set(), []
    for item in all_items:
        key = item["title"].strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
        if len(result) >= limit:
            break
    return result
