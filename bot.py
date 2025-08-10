import os
import discord
from discord import app_commands
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
    target_role_name = None
    for level_threshold in sorted(level_roles.keys(), reverse=True):
        if new_level >= level_threshold:
            target_role_name = level_roles[level_threshold]
            break
    roles_to_remove = [role for role in member.roles if role.name in level_roles.values()]
    for role in roles_to_remove:
        await member.remove_roles(role)
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
    await bot.tree.sync()

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

# =====================
# Slash Commands
# =====================

@bot.tree.command(name="rank", description="自分または指定ユーザーのランクカードを表示します")
@app_commands.describe(user="表示するユーザー（省略可）")
async def rank_slash(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    uid = str(target.id)
    data = user_data.get(uid, {"xp": 0, "level": 0})
    xp = data["xp"]
    level, cur, need = get_xp_progress(xp)

    bg = Image.open("background.png").convert("RGBA")
    draw = ImageDraw.Draw(bg)
    try:
        font = ImageFont.truetype("fonts/NotoSansJP-VariableFont_wght.ttf", 32)
    except:
        font = ImageFont.load_default()

    draw.text((50, 50), f"{target.name}", font=font, fill=(0, 0, 0))
    draw.text((50, 100), f"Level: {level}", font=font, fill=(139, 0, 0))
    draw.text((50, 150), f"XP: {xp:.1f}", font=font, fill=(139, 0, 0))
    draw.text((50, 200), f"{int(cur)} / {int(need)} XP", font=font, fill=(0, 0, 0))

    avatar_asset = target.display_avatar.replace(size=128, static_format="png")
    avatar_bytes = await avatar_asset.read()
    pfp = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((128, 128))
    mask = Image.new("L", (128, 128), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 128, 128), fill=255)
    bg.paste(pfp, (bg.width - 180, 30), mask)

    with io.BytesIO() as buffer:
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        await interaction.response.send_message(file=discord.File(fp=buffer, filename="rankcard.png"))

@bot.tree.command(name="rankall", description="サーバー内ランキング上位10人を表示します")
async def rankall_slash(interaction: discord.Interaction):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["xp"], reverse=True)
    msg = "**📊 サーバー内ランキング：**\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"User {uid}"
        msg += f"{i}. {name} - Lv{data['level']} ({data['xp']:.1f} XP)\n"
    await interaction.response.send_message(msg)

@bot.tree.command(name="addxp", description="指定ユーザーのXPを増加させます（権限者のみ）")
@app_commands.describe(user="対象ユーザー", amount="追加するXP量")
async def addxp_slash(interaction: discord.Interaction, user: discord.Member, amount: float):
    allowed_users = [440893662701027328, 716667546241335328]
    if interaction.user.id not in allowed_users:
        await interaction.response.send_message("❌ このコマンドを使う権限がありません。", ephemeral=True)
        return
    uid = str(user.id)
    user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
    before_level = user_data[uid]["level"]
    user_data[uid]["xp"] += amount
    new_level = calculate_level(user_data[uid]["xp"])
    user_data[uid]["level"] = new_level
    save_data(user_data)
    await update_roles(user, new_level)
    if new_level > before_level:
        msg = f"🎉 {user.mention} に {amount} XP を付与しました！レベルが {before_level} → {new_level} に上がりました。"
    else:
        msg = f"✅ {user.mention} に {amount} XP を付与しました（現在 Lv{new_level}）。"
    await interaction.response.send_message(msg)

@bot.tree.command(name="removexp", description="指定ユーザーのXPを減少させます（権限者のみ）")
@app_commands.describe(user="対象ユーザー", amount="減らすXP量")
async def removexp_slash(interaction: discord.Interaction, user: discord.Member, amount: float):
    allowed_users = [440893662701027328, 716667546241335328]
    if interaction.user.id not in allowed_users:
        await interaction.response.send_message("❌ このコマンドを使う権限がありません。", ephemeral=True)
        return
    uid = str(user.id)
    user_data.setdefault(uid, {"xp": 0, "level": 0, "voice_minutes": 0})
    before_level = user_data[uid]["level"]
    user_data[uid]["xp"] = max(0, user_data[uid]["xp"] - amount)
    new_level = calculate_level(user_data[uid]["xp"])
    user_data[uid]["level"] = new_level
    save_data(user_data)
    await update_roles(user, new_level)
    if new_level < before_level:
        msg = f"⚠️ {user.mention} のXPを {amount} 減らしました！レベルが {before_level} → {new_level} に下がりました。"
    else:
        msg = f"✅ {user.mention} のXPを {amount} 減らしました（現在 Lv{new_level}）。"
    await interaction.response.send_message(msg)

# 🔒 注意：最後
bot.run(os.getenv("DISCORD_TOKEN"))
