# news.py
import os, re
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests

# -------- Helpers --------
def shorten(text: str, max_len: int = 40) -> str:
    """裁切字串長度並加上省略號"""
    text = re.sub(r"\s+", " ", text.strip())
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

def split_time_and_title(raw: str) -> tuple[str | None, str]:
    """嘗試從標題中分離出『開頭的 HH:MM』與標題內容"""
    m = re.match(r"^\s*(\d{2}:\d{2})\s*(.+)", raw)
    if m:
        return m.group(1), m.group(2).strip()
    return None, raw.strip()

def clean_headline(text: str) -> str:
    """移除標題中的時間片段與多餘符號，只保留純標題"""
    t = text
    # 去掉所有獨立的 HH:MM（不只尾巴，整段都清）
    t = re.sub(r"\b\d{1,2}:\d{2}\b", "", t)
    # 清掉時間清除後留下的多餘標點與空白
    t = re.sub(r"[ \u3000\t]+", " ", t)                 # 折疊空白
    t = re.sub(r"\s*([，、,:;｜|\-–—/])\s*", r"\1", t)   # 標點左右空白
    t = t.strip(" .。、，:;|｜-–—/ ")
    return t.strip()

def clean_url(u: str | None, base: str) -> str | None:
    """轉為 http(s) 絕對網址；不合法則回 None。"""
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

def find_time_near(anchor_tag) -> str | None:
    """從 a.tit 周邊節點抓時間（處理 LTN 把時間獨立在 .time 或 <time> 的情況）"""
    if anchor_tag is None:
        return None

    # 在自身、父層、祖父層找常見時間節點
    candidates = []
    for node in (anchor_tag, getattr(anchor_tag, "parent", None), getattr(getattr(anchor_tag, "parent", None), "parent", None)):
        if not node:
            continue
        # 常見 class / tag
        for sel in (".time", "time", ".date", "em.time", "span.time"):
            el = node.select_one(sel) if hasattr(node, "select_one") else None
            if el:
                candidates.append(el.get_text(" ", strip=True))

        # 容器整體文字也掃一次
        txt = node.get_text(" ", strip=True)
        if txt:
            candidates.append(txt)

    # 正則找 HH:MM（允許 H:MM）
    for text in candidates:
        m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
        if m:
            h, mm = m.group(1).split(":")
            try:
                h = int(h)
                if 0 <= h <= 23:
                    return f"{h:02d}:{mm}"
            except Exception:
                pass
    return None

def fetch_h1_title(url: str) -> str | None:
    """到文章頁抓 <h1> 當最終標題；失敗回 None。"""
    try:
        r = requests.get(url, headers=req_header, timeout=10)
        r.raise_for_status()
    except Exception:
        return None

    s = BeautifulSoup(r.text, "lxml")
    # 依序嘗試幾個常見 H1/標題節點
    for sel in ("h1", "h1.article-title", "h1#articleTitle", "h1.title", ".whitecon.boxTitle h1"):
        el = s.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                return text
    # 後備：文件第一個 h1
    el = s.find("h1")
    return el.get_text(" ", strip=True) if el else None

# -------------------------

load_dotenv()
news_channel_id = os.getenv("channel_id")
news_channel_id = int(news_channel_id) if news_channel_id and news_channel_id.isdigit() else None

guild_id = os.getenv("GUILD_ID")
guild_obj = discord.Object(id=int(guild_id)) if guild_id and guild_id.isdigit() else None

ltn_url = "https://news.ltn.com.tw/list/breakingnews"
req_header = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    )
}

class NewsManager(commands.Cog):
    """處理新聞功能的 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.latest_news = set()      # 已發送的唯一鍵
        self.news_channel_id = news_channel_id

    async def run_once(self, target_channel: discord.abc.Messageable):
        """抓取 LTN 最新新聞並發送到指定頻道"""
        try:
            resp = requests.get(ltn_url, headers=req_header, timeout=10)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"[ERROR] 抓取失敗: {e}")
            return

        soup = BeautifulSoup(html, "lxml")

        # 主 selector
        articles = soup.select(".content940 a.tit")
        images = soup.select(".content940 img.lazy_imgs_ltn")

        # 備援 selector（DOM 變更時）
        if not articles:
            articles = (
                soup.select("a.tit")
                or soup.select("ul.list li a")
                or soup.select("div.list a")
                or []
            )
        if not images:
            images = (
                soup.select("img.lazy")
                or soup.select("ul.list li img")
                or soup.select("img")
                or []
            )

        # 取前 5 則
        articles = articles[:5]
        images = images[:5]

        if not articles:
            snippet = html[:400].replace("\n", " ")
            print("[DEBUG] 解析不到文章清單，可能 DOM 變更或反爬。HTTP:", resp.status_code)
            print("[DEBUG] HTML 前 400 字：", snippet)
            return

        print(f"本次抓取標題: {[a.get_text(strip=True) for a in articles]}")

        # 配對文章與圖片
        paired = []
        for idx, a in enumerate(articles):
            img_raw = images[idx].get("data-src") or images[idx].get("src") if idx < len(images) else None
            paired.append((a, img_raw))

        sent_this_round = set()

        for a, img_raw in reversed(paired):
            # === 1️⃣ 先解析清單頁的時間 ===
            raw_title = a.get_text(" ", strip=True)
            time_str, _tmp = split_time_and_title(raw_title)
            if not time_str:
                time_str = find_time_near(a)

            # === 2️⃣ 抓文章連結與縮圖 ===
            href = a.get("href") or ""
            news_url = clean_url(href, ltn_url)
            if not news_url:
                print(f"[SKIP] 無效文章網址: {href!r}")
                continue

            thumb_url = clean_url(img_raw, ltn_url)

            # === 3️⃣ 進入新聞頁抓 <h1> ===
            headline = fetch_h1_title(news_url)
            if not headline:
                # 備援：若新聞頁抓不到就用清單的標題
                headline = clean_headline(raw_title)

            # === 4️⃣ 縮短字數、防重檢查 ===
            short_title = shorten(headline, 60)
            unique_key = f"{headline}-{news_url}"
            if unique_key in self.latest_news:
                continue

            # === 5️⃣ 版面格式 ===
            # 這裡就是你要的：「時間在第一行，標題在第二行」
            title_text = f"{time_str}\n{short_title}" if time_str else short_title

            embed = discord.Embed(
                title=title_text,
                url=news_url,
                color=discord.Color.random(),
                timestamp=datetime.now(timezone.utc),
            )

            if thumb_url:
                embed.set_thumbnail(url=thumb_url)

            try:
                await target_channel.send(embed=embed)
            except discord.HTTPException as e:
                if "thumbnail" in str(e).lower():
                    embed.set_thumbnail(url=discord.Embed.Empty)
                    await target_channel.send(embed=embed)
                else:
                    raise

            self.latest_news.add(unique_key)



        # 更新本輪已發送（避免集合無限長大）
        if sent_this_round:
            self.latest_news = sent_this_round

    @tasks.loop(hours=1)
    async def check_news_task(self):
        """自動檢查新聞並發送最新內容"""
        if not self.news_channel_id:
            print("未設置新聞頻道 ID，跳過發送。")
            return

        channel = self.bot.get_channel(self.news_channel_id)
        if not channel:
            print(f"找不到頻道 ID：{self.news_channel_id}")
            return

        await self.run_once(channel)

    @check_news_task.before_loop
    async def before_check_news_task(self):
        """等待機器人準備好後再啟動定時任務"""
        await self.bot.wait_until_ready()

    @app_commands.command(name="set_news_channel", description="設置自動發送新聞的頻道")
    async def set_news_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """設置新聞自動發送頻道"""
        self.news_channel_id = channel.id
        await interaction.response.send_message(f"新聞頻道已設置為：{channel.mention}", ephemeral=True)

    @app_commands.command(name="fetch_latest_news", description="手動檢查新聞並發送")
    async def fetch_latest_news(self, interaction: discord.Interaction):
        """手動檢查新聞並發送（立即執行一次）"""
        target = interaction.channel
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.run_once(target)
        await interaction.followup.send("已檢查並發送最新新聞！", ephemeral=True)

    async def cog_load(self):
        if guild_obj:
            for cmd in self.get_app_commands():
                cmd.guilds = [guild_obj]
        if not self.check_news_task.is_running():
            self.check_news_task.start()

    def get_app_commands(self):
        """取出這個 Cog 內的 app commands（方便設定 guild）"""
        return [c for c in self.__cog_app_commands__]

async def setup(bot):
    """加載 NewsManager"""
    await bot.add_cog(NewsManager(bot))
