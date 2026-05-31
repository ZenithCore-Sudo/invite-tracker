import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from flask import Flask, jsonify
import threading
import json

# Flask app for Render health checks
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Discord Invite Tracker",
        "commands": [
            "/testrun", "/invites", "/myinvites", "/inviteinfo",
            "/latestinvite", "/latestmember", "/membercount", "/topinvites",
            "/inviterank", "/serverinfo", "/inviteleaderboard", "/botstats",
            "/totalinvites", "/memberjoined", "/serveranalytics", "/health"
        ]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "uptime": str(timedelta(seconds=uptime_seconds))})

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

invite_cache = {}
member_join_log = {}
invite_leaderboard = {}
bot_start_time = datetime.now()
uptime_seconds = 0

CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
TOKEN = os.getenv("BOT_TOKEN")

@bot.event
async def on_ready():
    global uptime_seconds
    print(f"{bot.user} is online!")
    print(f"Bot ID: {bot.user.id}")
    print(f"Bot Name: {bot.user.name}")
    
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
        invite_leaderboard[guild.id] = {}
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | {sum(g.member_count for g in bot.guilds)} users"
    ))
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
        for cmd in synced:
            print(f"  /{cmd.name}")
    except Exception as e:
        print(e)

@bot.event
async def on_member_join(member):
    guild = member.guild
    invites_before = invite_cache.get(guild.id, {})
    invites_after = await guild.invites()
    
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites_after}
    
    # Log member join
    join_time = datetime.now()
    member_join_log[member.id] = {
        "name": str(member),
        "time": join_time,
        "guild": guild.name
    }
    
    for invite in invites_after:
        if invite.code in invites_before:
            if invites_before[invite.code] != invite.uses:
                inviter = invite.inviter
                # Update leaderboard
                if inviter.id not in invite_leaderboard[guild.id]:
                    invite_leaderboard[guild.id][inviter.id] = 0
                invite_leaderboard[guild.id][inviter.id] += 1
                await send_embed(member, inviter, invite, guild)
                return
        else:
            inviter = invite.inviter
            if inviter.id not in invite_leaderboard[guild.id]:
                invite_leaderboard[guild.id][inviter.id] = 0
            invite_leaderboard[guild.id][inviter.id] += 1
            await send_embed(member, inviter, invite, guild)
            return

async def send_embed(member, inviter, invite, guild):
    embed = discord.Embed(
        title="📥 Member Joined",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="member.id", value=str(member.id), inline=True)
    embed.add_field(name="member.name", value=member.name, inline=True)
    embed.add_field(name="member.display_name", value=member.display_name, inline=True)
    embed.add_field(name="member.discriminator", value=member.discriminator, inline=True)
    embed.add_field(name="member.mention", value=member.mention, inline=True)
    
    embed.add_field(name="inviter.id", value=str(inviter.id), inline=True)
    embed.add_field(name="inviter.name", value=inviter.name, inline=True)
    embed.add_field(name="inviter.display_name", value=inviter.display_name, inline=True)
    embed.add_field(name="inviter.discriminator", value=inviter.discriminator, inline=True)
    embed.add_field(name="inviter.mention", value=inviter.mention, inline=True)
    
    embed.add_field(name="invite.code", value=invite.code, inline=True)
    embed.add_field(name="invite.uses", value=str(invite.uses), inline=True)
    
    embed.add_field(name="server.id", value=str(guild.id), inline=True)
    embed.add_field(name="server.name", value=guild.name, inline=True)
    embed.add_field(name="server.members", value=str(guild.member_count), inline=True)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text=f"Inviter ID: {inviter.id} | Total invited: {invite_leaderboard[guild.id].get(inviter.id, 0)}")
    
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)
    
    # Console log for Render
    print(f"[JOIN] {member.name} joined {guild.name} invited by {inviter.name} (Code: {invite.code})")

@bot.tree.command(name="latestinvite", description="Get the latest invite created in the server")
async def latestinvite(interaction: discord.Interaction):
    await interaction.response.defer()
    invites_list = await interaction.guild.invites()
    
    if not invites_list:
        await interaction.followup.send("No invites found in this server.")
        return
    
    # Sort by created_at
    latest = max(invites_list, key=lambda x: x.created_at if x.created_at else datetime.min)
    
    embed = discord.Embed(
        title="🔗 Latest Invite",
        color=discord.Color.blue(),
        timestamp=latest.created_at
    )
    
    embed.add_field(name="Code", value=latest.code, inline=True)
    embed.add_field(name="Creator", value=latest.inviter.mention, inline=True)
    embed.add_field(name="Uses", value=str(latest.uses), inline=True)
    embed.add_field(name="Channel", value=latest.channel.mention, inline=True)
    embed.add_field(name="Max Uses", value=str(latest.max_uses) if latest.max_uses else "Unlimited", inline=True)
    embed.add_field(name="Expires", value="Never" if not latest.expires_at else latest.expires_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="latestmember", description="Get the latest member who joined the server")
async def latestmember(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild = interaction.guild
    members = sorted(guild.members, key=lambda x: x.joined_at, reverse=True)
    
    if not members:
        await interaction.followup.send("No members found.")
        return
    
    latest = members[0]
    
    embed = discord.Embed(
        title="👤 Latest Member",
        color=discord.Color.green(),
        timestamp=latest.joined_at
    )
    
    embed.add_field(name="Name", value=latest.mention, inline=True)
    embed.add_field(name="ID", value=latest.id, inline=True)
    embed.add_field(name="Joined", value=latest.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Account Created", value=latest.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Is Bot", value=str(latest.bot), inline=True)
    
    embed.set_thumbnail(url=latest.avatar.url if latest.avatar else latest.default_avatar.url)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="membercount", description="Get detailed member count of the server")
async def membercount(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild = interaction.guild
    total = guild.member_count
    humans = sum(1 for m in guild.members if not m.bot)
    bots = total - humans
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    
    embed = discord.Embed(
        title=f"📊 Member Count - {guild.name}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Total Members", value=str(total), inline=True)
    embed.add_field(name="Humans", value=str(humans), inline=True)
    embed.add_field(name="Bots", value=str(bots), inline=True)
    embed.add_field(name="Online", value=str(online), inline=True)
    embed.add_field(name="Offline", value=str(total - online), inline=True)
    embed.add_field(name="Boosts", value=str(guild.premium_subscription_count or 0), inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="topinvites", description="Show top inviters in the server")
async def topinvites(interaction: discord.Interaction):
    await interaction.response.defer()
    
    invites_list = await interaction.guild.invites()
    inviter_counts = {}
    
    for invite in invites_list:
        if invite.inviter:
            if invite.inviter.id not in inviter_counts:
                inviter_counts[invite.inviter.id] = {"name": invite.inviter.name, "count": 0}
            inviter_counts[invite.inviter.id]["count"] += invite.uses
    
    sorted_inviters = sorted(inviter_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    
    if not sorted_inviters:
        await interaction.followup.send("No invite data found.")
        return
    
    embed = discord.Embed(
        title="🏆 Top Inviters",
        color=discord.Color.gold()
    )
    
    for i, (uid, data) in enumerate(sorted_inviters, 1):
        embed.add_field(
            name=f"{i}. {data['name']}",
            value=f"Invites: {data['count']}",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="inviterank", description="Check your invite rank in the server")
async def inviterank(interaction: discord.Interaction):
    await interaction.response.defer()
    
    invites_list = await interaction.guild.invites()
    inviter_counts = {}
    
    for invite in invites_list:
        if invite.inviter:
            if invite.inviter.id not in inviter_counts:
                inviter_counts[invite.inviter.id] = {"name": invite.inviter.name, "count": 0}
            inviter_counts[invite.inviter.id]["count"] += invite.uses
    
    sorted_inviters = sorted(inviter_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    
    user_rank = None
    user_count = 0
    
    for i, (uid, data) in enumerate(sorted_inviters, 1):
        if uid == interaction.user.id:
            user_rank = i
            user_count = data["count"]
            break
    
    if not user_rank:
        await interaction.followup.send(f"{interaction.user.mention}, you haven't invited anyone yet.")
        return
    
    embed = discord.Embed(
        title=f"📈 {interaction.user.name}'s Invite Rank",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Rank", value=f"#{user_rank}", inline=True)
    embed.add_field(name="Total Invites", value=str(user_count), inline=True)
    embed.add_field(name="Total Inviters", value=str(len(sorted_inviters)), inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="serverinfo", description="Get detailed server information")
async def serverinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"ℹ️ Server Info - {guild.name}",
        color=discord.Color.purple(),
        timestamp=guild.created_at
    )
    
    embed.add_field(name="Server ID", value=str(guild.id), inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
    embed.add_field(name="Boosts", value=str(guild.premium_subscription_count or 0), inline=True)
    embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="inviteleaderboard", description="Full invite leaderboard with stats")
async def inviteleaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    invites_list = await interaction.guild.invites()
    inviter_counts = {}
    total_invites = 0
    
    for invite in invites_list:
        if invite.inviter:
            if invite.inviter.id not in inviter_counts:
                inviter_counts[invite.inviter.id] = {"name": invite.inviter.name, "count": 0, "mention": invite.inviter.mention}
            inviter_counts[invite.inviter.id]["count"] += invite.uses
            total_invites += invite.uses
    
    sorted_inviters = sorted(inviter_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:15]
    
    if not sorted_inviters:
        await interaction.followup.send("No invite data found.")
        return
    
    embed = discord.Embed(
        title="🏆 Invite Leaderboard",
        description=f"Total Invites: **{total_invites}**",
        color=discord.Color.gold()
    )
    
    leaderboard_text = ""
    for i, (uid, data) in enumerate(sorted_inviters, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        leaderboard_text += f"{medal} {data['mention']} - **{data['count']}** invites\n"
    
    embed.add_field(name="Top Inviters", value=leaderboard_text, inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="botstats", description="Get bot statistics and performance")
async def botstats(interaction: discord.Interaction):
    await interaction.response.defer()
    
    global uptime_seconds
    uptime_seconds = int((datetime.now() - bot_start_time).total_seconds())
    uptime = str(timedelta(seconds=uptime_seconds))
    
    embed = discord.Embed(
        title="🤖 Bot Statistics",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Bot Name", value=bot.user.name, inline=True)
    embed.add_field(name="Bot ID", value=str(bot.user.id), inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Total Users", value=str(sum(g.member_count for g in bot.guilds)), inline=True)
    embed.add_field(name="Uptime", value=uptime, inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Commands", value="16 slash commands", inline=True)
    embed.add_field(name="Python Version", value="3.11", inline=True)
    embed.add_field(name="discord.py Version", value="2.3.2", inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="totalinvites", description="Get total invites count for the server")
async def totalinvites(interaction: discord.Interaction):
    await interaction.response.defer()
    
    invites_list = await interaction.guild.invites()
    total = sum(invite.uses for invite in invites_list)
    unique_codes = len(invites_list)
    
    embed = discord.Embed(
        title="📊 Total Invites Statistics",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Total Invites Used", value=str(total), inline=True)
    embed.add_field(name="Unique Invite Codes", value=str(unique_codes), inline=True)
    embed.add_field(name="Average per Code", value=round(total/unique_codes, 1) if unique_codes > 0 else 0, inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="memberjoined", description="Check when a specific member joined")
async def memberjoined(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    
    embed = discord.Embed(
        title=f"📅 {member.name}'s Join Info",
        color=discord.Color.blue(),
        timestamp=member.joined_at
    )
    
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="Days in Server", value=str((datetime.now() - member.joined_at).days), inline=True)
    embed.add_field(name="Account Age", value=str((datetime.now() - member.created_at).days), inline=True)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="serveranalytics", description="Get detailed server analytics")
async def serveranalytics(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild = interaction.guild
    invites_list = await guild.invites()
    
    total_invites = sum(invite.uses for invite in invites_list)
    unique_inviters = len(set(invite.inviter.id for invite in invites_list if invite.inviter))
    
    embed = discord.Embed(
        title=f"📈 Server Analytics - {guild.name}",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Total Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Total Invites", value=str(total_invites), inline=True)
    embed.add_field(name="Unique Inviters", value=str(unique_inviters), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Emojis", value=str(len(guild.emojis)), inline=True)
    embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
    embed.add_field(name="Boosts", value=str(guild.premium_subscription_count or 0), inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="testrun", description="Test the invite tracker with a fake member join")
async def testrun(interaction: discord.Interaction):
    await interaction.response.defer()
    
    fake_member = interaction.guild.me
    fake_inviter = interaction.user
    
    invites_list = await interaction.guild.invites()
    if invites_list:
        fake_invite = invites_list[0]
    else:
        try:
            channel = interaction.channel
            fake_invite = await channel.create_invite(max_uses=1, reason="Test run")
        except:
            await interaction.followup.send("❌ Failed to create test invite. Please create an invite first.")
            return
    
    embed = discord.Embed(
        title="🧪 TEST RUN - Member Joined",
        description="This is a test of the invite tracker system",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="member.id", value=str(fake_member.id), inline=True)
    embed.add_field(name="member.name", value=fake_member.name, inline=True)
    embed.add_field(name="member.display_name", value=fake_member.display_name, inline=True)
    embed.add_field(name="member.discriminator", value=fake_member.discriminator, inline=True)
    embed.add_field(name="member.mention", value=fake_member.mention, inline=True)
    
    embed.add_field(name="inviter.id", value=str(fake_inviter.id), inline=True)
    embed.add_field(name="inviter.name", value=fake_inviter.name, inline=True)
    embed.add_field(name="inviter.display_name", value=fake_inviter.display_name, inline=True)
    embed.add_field(name="inviter.discriminator", value=fake_inviter.discriminator, inline=True)
    embed.add_field(name="inviter.mention", value=fake_inviter.mention, inline=True)
    
    embed.add_field(name="invite.code", value=fake_invite.code, inline=True)
    embed.add_field(name="invite.uses", value=str(fake_invite.uses), inline=True)
    
    embed.add_field(name="server.id", value=str(interaction.guild.id), inline=True)
    embed.add_field(name="server.name", value=interaction.guild.name, inline=True)
    embed.add_field(name="server.members", value=str(interaction.guild.member_count), inline=True)
    
    embed.set_footer(text="🔧 TEST MODE - No actual member joined")
    
    await interaction.followup.send(embed=embed)
    
    # Console log for Render
    print(f"[TEST] {interaction.user.name} ran testrun in {interaction.guild.name}")

@bot.tree.command(name="invites", description="View all invites in this server")
async def invites(interaction: discord.Interaction):
    await interaction.response.defer()
    invites_list = await interaction.guild.invites()
    
    if not invites_list:
        await interaction.followup.send("No invites found in this server.")
        return
    
    embed = discord.Embed(
        title="📨 Server Invites",
        color=discord.Color.blue()
    )
    
    for invite in invites_list[:10]:
        embed.add_field(
            name=f"Code: {invite.code}",
            value=f"Creator: {invite.inviter.mention}\nUses: {invite.uses}\nChannel: {invite.channel.mention}",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="myinvites", description="See how many people you've invited")
async def myinvites(interaction: discord.Interaction):
    await interaction.response.defer()
    invites_list = await interaction.guild.invites()
    user_invites = [invite for invite in invites_list if invite.inviter == interaction.user]
    
    if not user_invites:
        await interaction.followup.send(f"{interaction.user.mention}, you haven't invited anyone yet.")
        return
    
    total_uses = sum(invite.uses for invite in user_invites)
    
    embed = discord.Embed(
        title=f"{interaction.user.name}'s Invites",
        description=f"You have invited **{total_uses}** people!",
        color=discord.Color.gold()
    )
    
    for invite in user_invites[:5]:
        embed.add_field(
            name=f"Code: {invite.code}",
            value=f"Uses: {invite.uses}\nChannel: {invite.channel.mention}",
            inline=False
        )
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="inviteinfo", description="Get info about a specific invite code")
async def inviteinfo(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    invites_list = await interaction.guild.invites()
    
    target_invite = None
    for invite in invites_list:
        if invite.code == code:
            target_invite = invite
            break
    
    if not target_invite:
        await interaction.followup.send(f"Invite code `{code}` not found in this server.")
        return
    
    embed = discord.Embed(
        title=f"Invite Info: {target_invite.code}",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="invite.code", value=target_invite.code, inline=True)
    embed.add_field(name="invite.uses", value=str(target_invite.uses), inline=True)
    embed.add_field(name="inviter.id", value=str(target_invite.inviter.id), inline=True)
    embed.add_field(name="inviter.name", value=target_invite.inviter.name, inline=True)
    embed.add_field(name="inviter.mention", value=target_invite.inviter.mention, inline=True)
    embed.add_field(name="channel", value=target_invite.channel.mention, inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.event
async def on_guild_join(guild):
    invites = await guild.invites()
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
    invite_leaderboard[guild.id] = {}
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | {sum(g.member_count for g in bot.guilds)} users"
    ))
    
    print(f"[GUILD JOIN] {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")

@bot.event
async def on_guild_remove(guild):
    if guild.id in invite_cache:
        del invite_cache[guild.id]
    if guild.id in invite_leaderboard:
        del invite_leaderboard[guild.id]
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | {sum(g.member_count for g in bot.guilds)} users"
    ))
    
    print(f"[GUILD LEFT] {guild.name} (ID: {guild.id})")

def run_bot():
    if not TOKEN:
        print("Error: BOT_TOKEN environment variable not set")
        exit(1)
    if not CHANNEL_ID:
        print("Error: CHANNEL_ID environment variable not set")
        exit(1)
    bot.run(TOKEN)

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Run the bot
    run_bot()
