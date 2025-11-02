import os, discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
from dotenv import load_dotenv
from news_links import NEWS_SOURCES

load_dotenv()

def _env_int(*keys: str) -> int | None:
    """依序嘗試多個 env key，取第一個是純數字的值轉 int。"""
    for k in keys:
        v = os.getenv(k)
        if v and v.isdigit():
            return int(v)
    return None

# 同時支援小寫與大寫 .env key
NEWS_CHANNEL_ID  = _env_int("news_channel_id", "NEWS_CHANNEL_ID")
GAMING_CHANNEL_ID = _env_int("game_channel_id", "GAMING_CHANNEL_ID")
GUILD_ID = _env_int("GUILD_ID")

def now_tz():
    return datetime.now(timezone.utc)

async def resolve_channel(bot: commands.Bot, channel_id: int | None) -> discord.abc.Messageable | None:
    """先從快取取頻道；miss 時回退 HTTP 取得；最後確認型別可 send。"""
    if not channel_id:
        return None
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
    if isinstance(ch, (discord.TextChannel, discord.Thread)):
        return ch
    return None

class NewsManager(commands.Cog):
    """處理新聞功能的 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.latest_news = set()
        self.latest_gaming = set()
        self.news_channel_id = NEWS_CHANNEL_ID
        self.gaming_channel_id = GAMING_CHANNEL_ID

    # ---------- Auto：LTN ----------
    @tasks.loop(hours=1)
    async def check_news_task(self):
        print("check_news_task() 正在執行")
        if not self.news_channel_id:
            print("未設置新聞頻道 ID，跳過發送。")
            return

        channel = await resolve_channel(self.bot, self.news_channel_id)
        if not channel:
            print(f"找不到新聞頻道 ID：{self.news_channel_id}")
            return

        items = NEWS_SOURCES["ltn"]()
        # 由舊到新發送
        for item in reversed(items):
            key = f"{item['title']}-{item['url']}"
            if key in self.latest_news:
                continue

            title_text = f"{item['time']}\n{item['title']}" if item["time"] else item["title"]
            embed = discord.Embed(
                title=title_text,
                url=item["url"],
                color=discord.Color.random(),
                timestamp=now_tz()
            )
            if item.get("image"):
                embed.set_thumbnail(url=item["image"])

            await channel.send(embed=embed)
            self.latest_news.add(key)
        
        print(f"抓到 {len(items)} 則新聞")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item['time']} {item['title']}")
        

    # ---------- Auto：Reddit（Game） ----------
    @tasks.loop(hours=1)
    async def check_gaming_task(self):
        if not self.gaming_channel_id:
            print("未設置遊戲頻道 ID，跳過發送。")
            return

        ch = await resolve_channel(self.bot, self.gaming_channel_id)
        if not ch:
            print(f"找不到遊戲頻道 ID：{self.gaming_channel_id}")
            return

        items = NEWS_SOURCES["reddit"]()
        for item in reversed(items):
            key = f"{item['title']}-{item['url']}"
            if key in self.latest_gaming:   # 統一用 latest_gaming
                continue

            embed = discord.Embed(
                title=item["title"],
                url=item["url"],
                color=discord.Color.random(),
                timestamp=now_tz(),
            )
            if item.get("image"):
                embed.set_thumbnail(url=item["image"])

            await ch.send(embed=embed)
            self.latest_gaming.add(key)

    # ---------- 手動抓取 ----------
    @app_commands.command(name="fetch_latest_news", description="手動檢查新聞並發送到當前頻道")
    @app_commands.describe(source=f"選擇新聞來源（{', '.join(NEWS_SOURCES.keys())}）")  # ✅ 括號補齊
    @app_commands.choices(
        source=[
            app_commands.Choice(name="LTN 即時 (ltn)", value="ltn"),
            app_commands.Choice(name="TVBS (tvbs)", value="tvbs"),
            app_commands.Choice(name="ETtoday (ettoday)", value="ettoday"),
            app_commands.Choice(name="Reddit 遊戲 (reddit)", value="reddit"),
        ]
    )
    async def fetch_latest_news(self, interaction: discord.Interaction, source: app_commands.Choice[str] | None = None):
        await interaction.response.defer(ephemeral=True, thinking=True)

        src_key = source.value if source else "ltn"
        if src_key not in NEWS_SOURCES:
            await interaction.followup.send(
                f"無此來源：{src_key}\n可用：{', '.join(NEWS_SOURCES.keys())}",
                ephemeral=True
            )
            return

        items = NEWS_SOURCES[src_key]()
        for item in items:
            title_text = f"{item['time']}\n{item['title']}" if item["time"] else item["title"]
            embed = discord.Embed(
                title=title_text,
                url=item["url"],
                color=discord.Color.random(),
                timestamp=now_tz(),
            )
            if item.get("image"):
                embed.set_thumbnail(url=item["image"])
            await interaction.channel.send(embed=embed)

        await interaction.followup.send(f"已抓取 **{src_key.upper()}** 共 {len(items)} 則", ephemeral=True)

    # ---------- Help ----------
    @app_commands.command(name="news_help", description="顯示新聞機器人可用指令與教學")
    async def news_help(self, interaction: discord.Interaction):
        text_sources = "、".join(name.upper() for name in NEWS_SOURCES.keys())

        embed = discord.Embed(
            title="新聞機器人指令一覽",
            description="以下是可用的 Slash 指令與用途：",
            color=discord.Color.blue(),
            timestamp=now_tz(),
        )
        embed.add_field(
            name="/fetch_latest_news",
            value=(
                "手動抓新聞到**當前頻道**。\n"
                f"**來源**：{text_sources}\n"
                "範例：`/fetch_latest_news source: ltn`"
            ),
            inline=False
        )
        embed.add_field(
            name="/set_news_channel",
            value="設定**即時新聞 (LTN)** 自動推送的頻道。",
            inline=False
        )
        embed.add_field(
            name="/set_gaming_channel",
            value="設定**遊戲新聞 (Reddit)** 自動推送的頻道。",
            inline=False
        )
        embed.set_footer(text="提示：在輸入 /fetch_latest_news 時可直接從下拉選來源")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- 設定頻道 ----------
    @app_commands.command(name="set_news_channel", description="設置自動發送新聞的頻道（LTN）")
    async def set_news_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.news_channel_id = channel.id
        await interaction.response.send_message(f"新聞頻道已設置為：{channel.mention}", ephemeral=True)

    @app_commands.command(name="set_gaming_channel", description="設置自動發送遊戲的頻道（Reddit）")
    async def set_gaming_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.gaming_channel_id = channel.id
        await interaction.response.send_message(f"遊戲頻道已設置為：{channel.mention}", ephemeral=True)

    @app_commands.command(name="show_news_channels", description="顯示目前設定的新聞與遊戲頻道")
    async def show_news_channels(self, interaction: discord.Interaction):
        """顯示目前設定的頻道狀態"""
        news_ch = self.bot.get_channel(self.news_channel_id) if self.news_channel_id else None
        gaming_ch = self.bot.get_channel(self.gaming_channel_id) if self.gaming_channel_id else None

        msg_lines = []
        msg_lines.append(f"**新聞頻道**：{news_ch.mention if news_ch else '未設置'}")
        msg_lines.append(f"**遊戲頻道**：{gaming_ch.mention if gaming_ch else '未設置'}")

        embed = discord.Embed(
            title="當前頻道設定狀態",
            description="\n".join(msg_lines),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @check_news_task.before_loop
    async def before_news_task(self):
        print("等待 bot 準備完成...")
        await self.bot.wait_until_ready()
        print("bot 準備完成，開始自動新聞任務")

    async def cog_load(self):
        if GUILD_ID:
            for cmd in self.get_app_commands():
                cmd.guilds = [discord.Object(id=GUILD_ID)]  # Object 大寫
                
        print("cog_load() 已執行 — 啟動定時任務")
        if not self.check_news_task.is_running():
            self.check_news_task.start()
            print("check_news_task started")
        if not self.check_gaming_task.is_running():
            self.check_gaming_task.start()

    def get_app_commands(self):
        return [c for c in self.__cog_app_commands__]

async def setup(bot):
    await bot.add_cog(NewsManager(bot))
