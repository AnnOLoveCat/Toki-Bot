import discord
from datetime import datetime
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os, requests, re
from bs4 import BeautifulSoup


load_dotenv()
channel_id = int(os.getenv("channel_id"))

class NewsManager(commands.Cog):
    """處理新聞功能的 Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.latest_news = set()  # 使用集合來追蹤已發送的新聞 URL
        self.news_channel_id = channel_id  # 設置要自動發送新聞的頻道 ID

    
    @tasks.loop(hours=1)
    async def check_news_task(self):
        """自動檢查新聞並發送最新內容"""
        url = 'https://news.ltn.com.tw/list/breakingnews'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取最新 10 則新聞
        articles = soup.select('.content940 a.tit')[:10]
        images = soup.select('.content940 img.lazy_imgs_ltn')[:10]

        # 如果未設置新聞頻道，跳過執行
        if not self.news_channel_id:
            print("未設置新聞頻道 ID，跳過發送。")
            return

        channel = self.bot.get_channel(self.news_channel_id)
        if not channel:
            print(f"找不到頻道 ID：{self.news_channel_id}")
            return

        # create new dataset, save only lastest news this turn
        current_news = set()
        
        print(f"本次抓取標題: {[article.get_text(strip=True) for article in articles]}")

        for index, article in enumerate(articles[::-1], start=1):
            raw_title = article.get_text(strip=True)
            match = re.match(r"^(\d{2}:\d{2})(.+)", raw_title)

            if match:
                time_str = match.group(1).strip()
                news_title = match.group(2).strip() 
            else:
                time_str = "未知時間"
                news_title = raw_title.strip()


            news_url = article['href']
            image_url = images[index]['data-src'] if index < len(images) else None

            unique_key = f"{news_title}-{news_url}"

            print(f"本次抓取：  {news_title} | {news_url}")

            # 如果新聞已經發送過，跳過
            if unique_key in self.latest_news:
                continue

            embed = discord.Embed(
                title=f"{time_str}\n {news_title}",
                url=news_url,
                color=discord.Color.random(),
                timestamp=datetime.utcnow()
            )
            if image_url:
                embed.set_thumbnail(url=image_url)

            await channel.send(embed=embed)

            current_news.add(unique_key)

            print(f"目前已發送：{(index)} 條")

        #   Update already send news list
        self.latest_news = current_news

    @check_news_task.before_loop
    async def before_check_news_task(self):
        """等待機器人準備好後再啟動定時任務"""
        await self.bot.wait_until_ready()

    # 使用 @app_commands.guilds 限制到特定伺服器
    @app_commands.command(name="set_news_channel", description="設置自動發送新聞的頻道")
    @app_commands.guilds(discord.Object(id=channel_id))  # 替換為伺服器 ID
    async def set_news_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """設置新聞自動發送頻道"""
        self.news_channel_id = channel.id
        await interaction.response.send_message(f"新聞頻道已設置為：{channel.mention}", ephemeral=True)

    @app_commands.command(name="fetch_latest_news", description="手動檢查新聞並發送")
    @app_commands.guilds(discord.Object(id=channel_id))  # 替換為伺服器 ID
    async def fetch_latest_news(self, interaction: discord.Interaction):
        """手動檢查新聞並發送"""
        # 手動執行新聞檢查
        await self.check_news_task()
        await interaction.response.send_message("已檢查並發送最新新聞！", ephemeral=True)

    async def cog_load(self):
        """在 Cog 加載時啟動定時任務和同步指令"""
        if not self.check_news_task.is_running():
            self.check_news_task.start()

async def setup(bot):
    """加載 NewsManager"""
    await bot.add_cog(NewsManager(bot))
