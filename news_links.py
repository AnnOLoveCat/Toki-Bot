import re, requests, feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

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

def clean_url(u: str | None, base: str) -> str | None:
    if not u:
        return None
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("http"):
        u = urljoin(base, u)
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        return None
    return u

def shorten(text: str, max_len: int = 40) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

# ---------- ltn ----------
def get_ltn(limit: int = MAX_DEFAULT):
    rss_url = "https://news.ltn.com.tw/rss/all.xml"
    feed = feedparser.parse(rss_url)
    results = []

    for entry in feed.entries[:limit]:
        url = entry.link
        title = entry.title

        # 進入文章頁抓 og:image + 時間
        try:
            r2 = requests.get(url, headers=USER_AGENT, timeout=10)
            r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, "lxml")

            # 標題
            h1 = soup2.select_one("h1")
            title = h1.get_text(strip=True) if h1 else entry.title

            # 時間
            time_str = None
            meta_time = soup2.find("meta", property="article:published_time")
            if meta_time and meta_time.get("content"):
                m = re.search(r"T(\d{2}:\d{2})", meta_time["content"])
                if m:
                    time_str = m.group(1)

            # 圖片
            og_img = soup2.find("meta", property="og:image")
            img_url = og_img["content"].strip() if og_img and og_img.get("content") else None
            img_url = clean_url(img_url, url)
        except Exception as e:
            print(f"{rss_url}抓取內頁失敗：{e}")
            continue

        if not img_url:
            print(f"{rss_url} 無圖片，跳過：{url}")
            continue

        title_text = f"{shorten(title, 60)}"

        results.append({
            "time": time_str,
            "title": title_text,     # 這是 embed title
            "url": url,
            "image": img_url,
        })

    print(f"成功抓到 {len(results)} 則 LTN 新聞")
    return results

    

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