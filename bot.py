import os
import discord
from discord.ext import commands, tasks
import json
import io
from PIL import Image, ImageDraw, ImageFont
import random
from discord import ui
from keep_alive import keep_alive

keep_alive()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

user_data_file = "data.json"

def load_data():
    try:
        with open(user_data_file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(user_data_file, "w") as f:
        json.dump(data, f, indent=2)

user_data = load_data()
chat_cooldown = {}

def xp_for_next_level(level):
    return 100 + 50 * level

def calculate_level(xp):
    level = 0
    while xp >= xp_for_next_level(level):
        xp -= xp_for_next_level(level)
        level += 1
    return level

def get_total_xp_required(level):
    return sum(xp_for_next_level(i) for i in range(level))

def get_xp_progress(xp):
    level = calculate_level(xp)
    current_level_xp = xp - get_total_xp_required(level)
    next_level_xp = xp_for_next_level(level)
    return level, current_level_xp, next_level_xp

level_roles = {
    5: "C",
    10: "C-",
    15: "CC",
    25: "B-",
    35: "B",
    45: "B+",
    55: "BB",
    70: "A-",
    85: "A",
    90: "A+",
    100: "AA",
    125: "S-",
    130: "S",
    140: "S+",
    150: "SS",
    200: "国家権力級"
}

async def update_roles(member, new_level):
    guild = member.guild

    # 現在のレベルに該当するロール名を取得（最も近いが超えてない最大のキー）
    target_role_name = None
    for level_threshold in sorted(level_roles.keys(), reverse=True):
        if new_level >= level_threshold:
            target_role_name = level_roles[level_threshold]
            break

    # 削除対象：level_roles に定義されてるすべてのロール（今後の上位も含めて）
    roles_to_remove = [role for role in member.roles if role.name in level_roles.values()]

    for role in roles_to_remove:
        await member.remove_roles(role)

    # 新しいロールを付与（存在すれば）
    if target_role_name:
        role_to_add = discord.utils.get(guild.roles, name=target_role_name)
        if role_to_add:
            await member.add_roles(role_to_add)
@bot.event
async def on_ready():
    print("✅ Bot起動完了！")
    try:
        voice_tracker.start()
    except:
        pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    uid = str(message.author.id)
    now = discord.utils.utcnow().timestamp()
    last = chat_cooldown.get(uid, 0)
    if now - last >= 60:
        chat_cooldown[uid] = now
        user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
        user_data[uid]["xp"] += 10 / 30 
        new_level = calculate_level(user_data[uid]["xp"])
        if new_level > user_data[uid]["level"]:
            user_data[uid]["level"] = new_level
            await update_roles(message.author, new_level)
            await message.channel.send(f"🎉 {message.author.mention} がレベル {new_level} に到達！")
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
                user_data[uid]["xp"] += 1
                user_data[uid]["voice_minutes"] += 1
                new_level = calculate_level(user_data[uid]["xp"])
                if new_level > user_data[uid]["level"]:
                    user_data[uid]["level"] = new_level
                    await update_roles(member, new_level)
                    if member.guild.system_channel:
                        await member.guild.system_channel.send(f"📞 {member.mention} が通話でレベル {new_level} に！")
    save_data(user_data)

@bot.command()
async def rank(ctx):
    uid = str(ctx.author.id)
    data = user_data.get(uid, {"xp": 0, "level": 0})
    xp = data["xp"]
    level, cur, need = get_xp_progress(xp)

    bg = Image.open("background.png").convert("RGBA")
    draw = ImageDraw.Draw(bg)

    try:
        font = ImageFont.truetype("fonts/NotoSansJP-VariableFont_wght.ttf", 32)
    except:
        font = ImageFont.load_default()

    draw.text((50, 50), f"{ctx.author.name}", font=font, fill=(0, 0, 0))
    draw.text((50, 100), f"Level: {level}", font=font, fill=(139, 0, 0))
    draw.text((50, 150), f"XP: {xp:.1f}", font=font, fill=(139, 0, 0))
    draw.text((50, 200), f"{int(cur)} / {int(need)} XP", font=font, fill=(0, 0, 0))

    avatar_asset = ctx.author.display_avatar.replace(size=128, static_format="png")
    avatar_bytes = await avatar_asset.read()
    pfp = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((128, 128))
    mask = Image.new("L", (128, 128), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 128, 128), fill=255)
    bg.paste(pfp, (bg.width - 180, 30), mask)

    with io.BytesIO() as buffer:
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        await ctx.send(file=discord.File(fp=buffer, filename="rankcard.png"))

@bot.command()
async def rankall(ctx):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["xp"], reverse=True)
    msg = "**📊 サーバー内ランキング：**\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        msg += f"{i}. {name} - Lv{data['level']} ({data['xp']:.1f} XP)\n"
    await ctx.send(msg)
@bot.command()
async def addxp(ctx, member: discord.Member, amount: float):
    allowed_users = [440893662701027328, 716667546241335328]
    if ctx.author.id not in allowed_users:
        await ctx.send("❌ このコマンドを使う権限がありません。")
        return

    uid = str(member.id)
    user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
    before_level = user_data[uid]["level"]

    # 経験値加算
    user_data[uid]["xp"] += amount
    new_level = calculate_level(user_data[uid]["xp"])
    user_data[uid]["level"] = new_level
    save_data(user_data)

    await update_roles(member, new_level)

    if new_level > before_level:
        await ctx.send(f"🎉 {member.mention} に {amount} XP を付与しました！レベルが {before_level} → {new_level} に上がりました。")
    else:
        await ctx.send(f"✅ {member.mention} に {amount} XP を付与しました（現在 Lv{new_level}）。")

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


