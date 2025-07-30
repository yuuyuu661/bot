import os
import discord
from discord.ext import commands, tasks
import json
import io
import requests
from PIL import Image, ImageDraw, ImageFont
import random
import time
from keep_alive import keep_alive

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

keep_alive()

# ロールの設定（レベル: ロール名）
ROLE_REWARDS = {
    5: "C", 10: "Cプラス", 15: "CC", 25: "Bマイナス", 35: "B",
    45: "Bプラス", 55: "BB", 70: "Aマイナス", 85: "A", 90: "Aプラス",
    100: "AA", 125: "Sマイナス", 130: "S", 140: "Sプラス", 150: "SS", 200: "国家権力級"
}

# データ保存
def load_data():
    try:
        with open("data.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

user_data = load_data()
chat_cooldown = {}

# レベルに必要なXP計算式
def get_required_xp(level):
    return 100 + 50 * max(level - 1, 0)

def check_level_up(uid, member, channel=None):
    xp = user_data[uid]["xp"]
    level = user_data[uid]["level"]
    while xp >= get_required_xp(level):
        xp -= get_required_xp(level)
        level += 1
    changed = level != user_data[uid]["level"]
    user_data[uid]["xp"] = xp
    user_data[uid]["level"] = level
    if changed and channel:
        return True, level
    return changed, level

async def update_roles(member, new_level):
    guild_roles = {role.name: role for role in member.guild.roles}
    roles_to_add = [name for lvl, name in ROLE_REWARDS.items() if lvl == new_level]
    roles_to_remove = [guild_roles[name] for lvl, name in ROLE_REWARDS.items() if lvl != new_level and name in [r.name for r in member.roles]]

    # 古いロールを削除
    for role in roles_to_remove:
        await member.remove_roles(role)

    # 新しいロールを追加
    for role_name in roles_to_add:
        role = guild_roles.get(role_name)
        if role:
            await member.add_roles(role)

@bot.event
async def on_ready():
    print("✅ Bot起動完了！")
    voice_tracker.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    uid = str(message.author.id)
    now = time.time()
    last_time = chat_cooldown.get(uid, 0)
    if now - last_time < 60:  # クールタイム60秒
        await bot.process_commands(message)
        return

    chat_cooldown[uid] = now
    user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
    user_data[uid]["xp"] += 10

    changed, new_level = check_level_up(uid, message.author, message.channel)
    if changed:
        await message.channel.send(f"🎉 {message.author.mention} がレベル {new_level} に到達！")
        await update_roles(message.author, new_level)

    save_data(user_data)
    await bot.process_commands(message)

@tasks.loop(minutes=1)
async def voice_tracker():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue
                uid = str(member.id)
                user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
                user_data[uid]["xp"] += 1  # 毎分1XP（10分で10XP）
                user_data[uid]["voice_minutes"] += 1
                changed, new_level = check_level_up(uid, member)
                if changed and member.guild.system_channel:
                    await member.guild.system_channel.send(f"📞 {member.mention} が通話でレベル {new_level} に！")
                    await update_roles(member, new_level)
    save_data(user_data)
# !rank コマンド
@bot.command()
async def rank(ctx):
    uid = str(ctx.author.id)
    data = user_data.get(uid, {"xp": 0, "level": 0})
    xp = data["xp"]
    level = data["level"]

    # 背景画像読み込み
    bg = Image.open("background.png").convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # フォント読み込み
    try:
        font = ImageFont.truetype("fonts/NotoSansJP-VariableFont_wght.ttf", 32)
    except:
        font = ImageFont.load_default()

    # テキスト描画位置を右下寄りに変更
    name_x, name_y = bg.width - 700, bg.height - 230
    level_label_x, level_y = bg.width - 700, bg.height - 180
    level_value_x = level_label_x + 90
    xp_label_x, xp_y = bg.width - 700, bg.height - 130
    xp_value_x = xp_label_x + 90

    # ユーザー名（黒）
    draw.text((name_x, name_y), f"{ctx.author.name}", font=font, fill=(0, 0, 0))

    # Level（ラベル黒、数字赤）
    draw.text((level_label_x, level_y), "Level:", font=font, fill=(0, 0, 0))
    draw.text((level_value_x, level_y), f"{level}", font=font, fill=(139, 0, 0))

    # XP（ラベル黒、数字赤）
    draw.text((xp_label_x, xp_y), "XP:", font=font, fill=(0, 0, 0))
    draw.text((xp_value_x, xp_y), f"{xp:.1f}", font=font, fill=(139, 0, 0))


    # アイコン円形切り抜き
    avatar_asset = ctx.author.display_avatar.replace(size=128, static_format="png")
    avatar_bytes = await avatar_asset.read()
    pfp_size = 140  # サイズ変更（100→120）
    pfp = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((pfp_size, pfp_size))
    mask = Image.new("L", (pfp_size, pfp_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, pfp_size, pfp_size), fill=255)
    bg.paste(pfp, (600, 20), mask)  # 表示位置も少し上に & 左に調整

    # 画像送信
    with io.BytesIO() as buffer:
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        await ctx.send(file=discord.File(fp=buffer, filename="rankcard.png"))

# !rankall コマンド（ランキング表示）
@bot.command()
async def rankall(ctx):
    guild = ctx.guild
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["xp"], reverse=True)
    msg = "**📊 サーバー内ランキング：**\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        member = guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        msg += f"{i}. {name} - Lv{data['level']} ({data['xp']:.1f} XP)\n"

    await ctx.send(msg)
# --- ブラックジャック ---
active_games = {}

class BlackjackButton(discord.ui.View):
    def __init__(self, player_id):
        super().__init__(timeout=30)
        self.player_id = player_id

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("これはあなたのターンではありません。", ephemeral=True)
            return
        game = active_games.get(self.player_id)
        if not game:
            await interaction.response.send_message("ゲームが見つかりません。", ephemeral=True)
            return
        game["player_hand"].append(random.randint(1, 11))
        total = sum(game["player_hand"])
        if total > 21:
            await interaction.response.edit_message(content=f"あなたの手札: {game['player_hand']}（合計: {total}）\nバーストしました！", view=None)
            del active_games[self.player_id]
        else:
            await interaction.response.edit_message(content=f"あなたの手札: {game['player_hand']}（合計: {total}）", view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("これはあなたのターンではありません。", ephemeral=True)
            return
        game = active_games.pop(self.player_id, None)
        if not game:
            return
        dealer_total = sum(game["dealer_hand"])
        while dealer_total < 17:
            game["dealer_hand"].append(random.randint(1, 11))
            dealer_total = sum(game["dealer_hand"])

        player_total = sum(game["player_hand"])
        result = ""
        if dealer_total > 21 or player_total > dealer_total:
            result = "🎉 勝ち！"
        elif dealer_total == player_total:
            result = "🤝 引き分け"
        else:
            result = "😢 負け..."

        await interaction.response.edit_message(
            content=f"あなたの手札: {game['player_hand']}（合計: {player_total}）\n"
                    f"ディーラーの手札: {game['dealer_hand']}（合計: {dealer_total}）\n{result}",
            view=None
        )

@bot.command()
async def blackjack(ctx):
    dealer_hand = [random.randint(1, 11), random.randint(1, 11)]
    player_hand = [random.randint(1, 11), random.randint(1, 11)]
    active_games[ctx.author.id] = {
        "dealer_hand": dealer_hand,
        "player_hand": player_hand
    }

    await ctx.send(f"🃏 ディーラーの手札: [{dealer_hand[0]}, ?]")
    total = sum(player_hand)
    view = BlackjackButton(ctx.author.id)
    await ctx.author.send(f"あなたの手札: {player_hand}（合計: {total}）", view=view)

# 🔒 注意：ここは絶対に関数の中に書かないでください
bot.run(os.getenv("DISCORD_TOKEN"))
