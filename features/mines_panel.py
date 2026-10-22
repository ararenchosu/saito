import discord
from discord import app_commands
import aiohttp

WEB_BASE_URL = "https://app-6cfc7eb9.fadehost.app"

class MinesWebStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💎 マインスを始める", style=discord.ButtonStyle.green, custom_id="mines_web_v1")
    async def start(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{WEB_BASE_URL}/create-session",
                json={"user_id": str(inter.user.id)}
            ) as resp:
                data = await resp.json()
        if not data.get("success"):
            await inter.followup.send("❌ セッション作成失敗", ephemeral=True)
            return
        url = f"{WEB_BASE_URL}{data['session_url']}"
        await inter.followup.send(
            embed=discord.Embed(
                title="💎 ゲームページ",
                description=f"👇 ここからプレイ！\n{url}\n\n⚠️ このリンクはあなた専用です",
                color=0x2ECC71
            ),
            ephemeral=True
        )

async def setup(tree, bot):
    bot.add_view(MinesWebStartView())
    @tree.command(name="マインスパネル", description="マインス開始パネル")
    async def cmd(inter: discord.Interaction):
        await inter.response.send_message(
            embed=discord.Embed(title="💎 マインスゲーム", description="下のボタンを押して始めてください", color=0xFFD700),
            view=MinesWebStartView()
        )
    print("[MINES] ✅ セットアップ完了")
