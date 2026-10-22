import discord
from discord.ext import commands
import asyncio
import os
import threading
from core.database import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

from web.app import app as flask_app

def run_web():
    try:
        flask_app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ ウェブサーバー: {e}")

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        init_db()
        print("✅ DB初期化完了")
        # 必要なCogがあればここに追加
        synced = await self.tree.sync()
        print(f"✅ コマンド同期: {len(synced)}件")

bot = MyBot()

async def main():
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    print("✅ ウェブサーバー起動:8080")
    await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
