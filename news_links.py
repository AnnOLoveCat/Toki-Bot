import re, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

USER_AGENT = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/127.0.0.0 Safari/537.36")
}

MIN_DEFAULT = 1
MAX_DEFAULT = 5

def format(time, title, url, image):
    return {"time":time.strip() if time else None,
            "title": title.strip() if title else "",
            "url": url.strip() if url else "",
            "image": image.strip() if image else None,}

def shorten(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    return s if len(s) <= n else s[:n-1] + "…"

# ---------- ltn ----------
def get_ltn(limit: int = 3):
    base = "https://news.ltn.com.tw/list/breakingnews"
    r = requests.get(base, headers=USER_AGENT, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    titles = soup.select(".content940 a.tit") or []
    thumbs = soup.select(".content940 img.lazy_imgs_ltn") or []
    items = []

    for i, a in enumerate(titles[:limit]):
        raw = a.get_text(strip=True)
        # 時間在開頭或在鄰近 .time
        
        m = re.match(r"^(\d{1,2}:\d{2})", raw)
        time_str = m.group(1) if m else None
        if not time_str:
            parent = a.parent
            tnode = parent.select_one(".time") if parent else None
            if tnode:
                m2 = re.search(r"\b(\d{1,2}:\d{2})\b", tnode.get_text(" ", strip=True))
                time_str = m2.group(1) if m2 else None

        # 標題：清掉任何 HH:MM
        title = re.sub(r"^\s*\d{1,2}:\d{2}\s*", "", raw)
        title = re.sub(r"\b\d{1,2}:\d{2}\b", "", title).strip()

        url = urljoin(base, a.get("href", ""))
        img_raw = thumbs[i].get("data-src") or thumbs[i].get("src") if i < len(thumbs) else None
        image = urljoin(base, img_raw) if img_raw else None
        items.append(format(time_str, title, url, image))

    return items

# ---------- TVBS ----------
def get_tvbs(limit: int = 3):
    base = "https://news.tvbs.com.tw/realtime"
    r = requests.get(base, headers=USER_AGENT, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for li in soup.select("li.news_list")[:limit]:
        a = li.select_one("h2 a")
        if not a:
            continue
        title = a.get_text(strip=True)
        url = urljoin(base, a.get("href", ""))

        tnode = li.select_one(".time") or li.select_one("div.time")
        time_str = None
        if tnode:
            m = re.search(r"\b(\d{1,2}:\d{2})\b", tnode.get_text(" ", strip=True))
            time_str = m.group(1) if m else None

        img_el = li.select_one("img")
        image = urljoin(base, img_el.get("src", "")) if img_el and img_el.get("src") else None
        items.append(format(time_str, title, url, image))
    return items

# ---------- ETtoday ----------
def get_ettoday(limit: int = 3):
    base = "https://www.ettoday.net/news/realtime-hot.htm"
    r = requests.get(base, headers=USER_AGENT, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for h3 in soup.select("div.part_list_2 h3")[:limit]:
        a = h3.select_one("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        url = urljoin(base, a.get("href", ""))

        tnode = h3.select_one("span.date")
        time_str = None
        if tnode:
            m = re.search(r"\b(\d{1,2}:\d{2})\b", tnode.get_text(" ", strip=True))
            time_str = m.group(1) if m else None

        # 圖片：版面不一定有，盡量抓
        image = None
        sib_a = h3.find_previous_sibling("a")
        if sib_a:
            img = sib_a.select_one("img")
            if img and img.get("src"):
                image = urljoin(base, img.get("src"))
        items.append(format(time_str, title, url, image))
    return items

# ---------- Reddit（r/Games） ----------
def get_reddit_gaming(limit: int = 2):
    base = "https://www.reddit.com/r/Games/"
    r = requests.get(base, headers=USER_AGENT, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    posts = soup.select("shreddit-post")[:limit]
    items = []
    for p in posts:
        title = p.get("post-title") or p.get("data-adclicktitle")
        url = p.get("content-href") or p.get("permalink")
        if not title or not url:
            continue
        image = p.get("thumbnail-url")
        items.append(format(None, shorten(title, 120), url, image))
    return items

NEWS_SOURCES = {
    "ltn": get_ltn,
    "tvbs": get_tvbs,
    "ettoday": get_ettoday,
    "reddit": get_reddit_gaming,   # 遊戲新聞
}