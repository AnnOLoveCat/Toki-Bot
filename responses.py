import discord
from discord.ext import commands
from discord import app_commands
import logging, json, os

# check JSON file existed
RESPONSES_FILE = "responses.json"

#setting logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if not os.path.exists(RESPONSES_FILE):
    with open(RESPONSES_FILE, "w", encoding="UTF-8") as file:
        json.dump({}, file)

class Response(commands.GroupCog, name = "response"):
    """管理關鍵字回應的 Slash Commands"""

    def __init__(self, bot):
        self.bot = bot
        self.responses = self.load_responses()  # 正確初始化 responses

    def load_responses(self):
        """載入 JSON 檔案中的回應資料"""
        if os.path.exists(RESPONSES_FILE):
            try:
                with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)  # 確保 responses 正確載入
            except json.JSONDecodeError:
                logging.warning("responses.json format error，reset to empty")
                return {}  # 防止 JSON 檔案損壞時發生錯誤

        return {}  # 如果檔案不存在，回傳空字典

    def save_responses(self):
        """儲存回應資料到 JSON 檔案"""
        try:
            #backup old responses.json
            if os.path.exists(RESPONSES_FILE):
                os.rename(RESPONSES_FILE, f"{RESPONSES_FILE}.backup")

            #save newwest responses.json
            with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.responses, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logging.error(f"儲存 responses.json 時發生錯誤: {e}")
            
            # 如果寫入失敗，恢復備份
            if os.path.exists(f"{RESPONSES_FILE}.backup"):
                os.rename(f"{RESPONSES_FILE}.backup", RESPONSES_FILE)
    
    @app_commands.command(name="add", description="add keyword's response")
    @app_commands.describe(keyword="type any keyword", response="response content")
    async def add_response(self, interaction: discord.Interaction, keyword: str, response: str):
        """新增關鍵字回應"""
        self.responses[keyword] = response
        self.save_responses()  # 正確存檔
        await interaction.response.send_message(f"add keyword: `{keyword}`，response：`{response}`")


    @app_commands.command(name="remove", description="remove keyword's response")
    @app_commands.describe(keyword="type any keyword existed")
    async def remove_response(self, interaction: discord.Interaction, keyword: str):
        """刪除關鍵字回應"""
        if keyword in self.responses:
            del self.responses[keyword]
            self.save_responses()
            await interaction.response.send_message(f"removed `{keyword}`")
        else:
            await interaction.response.send_message(f"`{keyword}` does NOT existed", ephemeral=True)


    @app_commands.command(name="show", description="show all keyword responses")
    async def show_responses(self, interaction: discord.Interaction):
        """顯示所有關鍵字回應"""
        if not self.responses:
            await interaction.response.send_message("these no saves keyword response", ephemeral=True)
            return

        response_list = "\n".join([f"🔹 `{key}` ➝ `{value}`" for key, value in self.responses.items()])
        response_str = "\n".join(response_list)

        # Discord 限制單次訊息最大 4096 字元，超過則拆分
        if len(response_str) > 4000:
            chunks = [response_str[i : i + 4000] for i in range(0, len(response_str), 4000)]
            await interaction.response.send_message("Keyword responses are too long, sending in multiple messages...")
            for chunk in chunks:
                await interaction.followup.send(chunk)
        else:
            embed = discord.Embed(title="keyword response list: ", description=response_list, color=0x00ff00)
            await interaction.response.send_message(embed=embed)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """當訊息包含關鍵字時，自動回應"""
        if message.author.bot:
            return  # 忽略機器人訊息

        user_message = message.content


        self.responses = self.load_responses()

        guild_name = message.guild.name if message.guild else "私訊 (DM)"
        channel_name = message.channel.name if message.guild else "私訊"
        username = str(message.author)
        user_message = str(message.content)
        has_attachment = len(message.attachments) > 0

        # 在終端機輸出聊天紀錄
        logging.info(f'[{guild_name} - {channel_name}] {username}: "{user_message}" {"📎(附加檔案)" if has_attachment else ""}')

        for keyword, response in self.responses.items():
            if keyword in message.content:
                await message.channel.send(response)
                break  # 只觸發第一個符合的關鍵字回應
        
        await self.bot.process_commands(message)  # 確保其他指令仍可運行

async def setup(bot):
    """加載 Response"""
    await bot.add_cog(Response(bot))
