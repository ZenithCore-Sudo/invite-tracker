import discord
from discord.ext import commands
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

invite_cache = {}

CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
TOKEN = os.getenv("BOT_TOKEN")

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | Tracking invites"
    ))
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)

@bot.event
async def on_member_join(member):
    guild = member.guild
    invites_before = invite_cache.get(guild.id, {})
    invites_after = await guild.invites()
    
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites_after}
    
    for invite in invites_after:
        if invite.code in invites_before:
            if invites_before[invite.code] != invite.uses:
                inviter = invite.inviter
                await send_embed(member, inviter, invite, guild)
                return
        else:
            inviter = invite.inviter
            await send_embed(member, inviter, invite, guild)
            return

@bot.event
async def on_member_remove(member):
    guild = member.guild
    invites = await guild.invites()
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

async def send_embed(member, inviter, invite, guild):
    embed = discord.Embed(
        title="📥 Member Joined",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="member.id", value=str(member.id), inline=True)
    embed.add_field(name="member.tag", value=member.tag, inline=True)
    embed.add_field(name="member.username", value=member.username, inline=True)
    embed.add_field(name="member.discriminator", value=member.discriminator, inline=True)
    embed.add_field(name="member.mention", value=member.mention, inline=True)
    
    embed.add_field(name="inviter.id", value=str(inviter.id), inline=True)
    embed.add_field(name="inviter.tag", value=inviter.tag, inline=True)
    embed.add_field(name="inviter.username", value=inviter.username, inline=True)
    embed.add_field(name="inviter.discriminator", value=inviter.discriminator, inline=True)
    embed.add_field(name="inviter.mention", value=inviter.mention, inline=True)
    
    embed.add_field(name="invite.code", value=invite.code, inline=True)
    embed.add_field(name="invite.uses", value=str(invite.uses), inline=True)
    
    embed.add_field(name="server.id", value=str(guild.id), inline=True)
    embed.add_field(name="server.name", value=guild.name, inline=True)
    embed.add_field(name="server.members", value=str(guild.member_count), inline=True)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text=f"Inviter ID: {inviter.id}", icon_url=inviter.avatar.url if inviter.avatar else None)
    
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

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
    embed.add_field(name="inviter.tag", value=target_invite.inviter.tag, inline=True)
    embed.add_field(name="inviter.mention", value=target_invite.inviter.mention, inline=True)
    embed.add_field(name="channel", value=target_invite.channel.mention, inline=True)
    
    await interaction.followup.send(embed=embed)

@bot.event
async def on_guild_join(guild):
    invites = await guild.invites()
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | Tracking invites"
    ))

@bot.event
async def on_guild_remove(guild):
    if guild.id in invite_cache:
        del invite_cache[guild.id]
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers | Tracking invites"
    ))

if __name__ == "__main__":
    if not TOKEN:
        print("Error: BOT_TOKEN environment variable not set")
        exit(1)
    if not CHANNEL_ID:
        print("Error: CHANNEL_ID environment variable not set")
        exit(1)
    bot.run(TOKEN)
