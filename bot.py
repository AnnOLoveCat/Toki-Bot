import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

# 加載 .env 文件中的 TOKEN
load_dotenv()
TOKEN = os.getenv("TOKEN")  # 確保 .env 文件中設置了 TOKEN
GUILD_ID = os.getenv("GUILD_ID")  # 適用於特定伺服器指令

# Bot 設定
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents, help_command=None)

    async def setup_hook(self):
        try:
            print("正在初始化 CommandTree...")
            if not hasattr(self, "tree"):
                raise RuntimeError("CommandTree 尚未初始化")
            
            # 加載擴展
            print("正在加載 extension 擴展...")
            await self.load_extension("responses")
            await self.load_extension("news")
            print("已成功加載 extension 擴展！")

            # 確保指令同步
            print("正在同步指令...")
            guild_id = os.getenv("GUILD_ID")
            guild = discord.Object(id=int(guild_id)) if guild_id else None
            await self.tree.sync(guild=guild)
            print(f"指令已同步到 {'伺服器: ' + guild_id if guild else '全域範圍'}")

        except Exception as e:
            print(f"初始化時發生錯誤：{e}")


    async def close(self):
        await super().close()
        print("機器人已關閉")

if __name__ == "__main__":
    bot = MyBot()
    
    try:
        print("正在啟動機器人...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"啟動機器人時發生錯誤：{e}")