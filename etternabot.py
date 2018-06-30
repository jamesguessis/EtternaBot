from discord.ext import commands
import matplotlib.pyplot as plt
from operator import itemgetter
from datetime import datetime, timedelta
from eoapi import *
import logging, logging.handlers
import asyncio#, uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import discord, sqlite3, random
import time, json, sys, os, re
from PIL import Image, ImageDraw, ImageFont

settings = json.loads(open('config.json').read())
prefix = settings['prefix']
client = commands.Bot(prefix)
client.uptime = datetime.utcnow()
database = sqlite3.connect('users.db')
c = database.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (discordid INTEGER, user TEXT, rival TEXT)")
minanym = json.loads(open('minanyms.json').read())

logger = logging.getLogger("etterna")
log_format = logging.Formatter(
    '%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: '
    '%(message)s',
    datefmt="[%d/%m/%Y %H:%M]")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(log_format)
logger.setLevel(logging.WARNING)
logger.addHandler(stdout_handler)

@client.event
async def on_ready():
    print('Logged in as {}\nI can see {} users in {} servers'.format(
        client.user,  len(list(client.get_all_members())), 
        len(client.guilds)))
    await client.change_presence(status=discord.Status.dnd, game=discord.Game(name='Etterna'))

@client.event
async def on_message(message):
    if not await checkmessages(message): return
    else: await client.process_commands(message)
    scores = re.findall('https://etternaonline.com/score/view/[A-Z]\w+', message.content)
    for score in scores:
        await message.channel.send(embed=await buildscore(score.replace('https://etternaonline.com/score/view/', '')))
    songs = re.findall('https://etternaonline.com/song/view/[0-9]\w+', message.content)
    for song in songs:
        await message.channel.send(embed=await buildsong(song.replace('https://etternaonline.com/song/view/', '')))
    #packs = re.findall('https://etternaonline.com/pack/[0-9]\w+', message.content)
    #for pack in packs:
    #    await message.channel.send(embed=await buildpack(pack.replace('https://etternaonline.com/pack/', '')))

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def profile(ctx, user=None):
    """Shows basic EtternaOnline stats of a given user"""
    await dotheprofile(ctx, user=user)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def advprof(ctx, user=None):
    """Shows not basic EtternaOnline stats of a given user"""
    await dotheprofile(ctx, user=user, adv=69)

async def dotheprofile(ctx, user=None, adv=None):
    if not user:
        c = database.cursor()
        record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
        if len(record) < 1:
            await ctx.message.channel.send("You either need to specify a username or run `{}userset [username]`".format(prefix))
            return
        else: user = record[0][0]
    data = await user_data(settings['key'], user)
    if 'error' in data:
        await ctx.message.channel.send("{} not found!".format(user))
        return
    rank = await user_rank(settings['key'], user)
    if not data['Overall'] or data['Overall'] == '0':
        message = "Looks like stats, this user has not!"
    elif adv: message = await buildprofileranks(data, rank)
    else: message = await buildprofile(data)
    ismod = '(Mod)' if int(data['moderator']) else ''
    ispatron = '(Patron)' if data['Patreon'] else ''
    flagurl = 'https://etternaonline.com/img/gif/{}.gif'.format(data['countrycode']) if (data['countrycode'] and data['countrycode'] != 'undef') else ''
    em = discord.Embed(description='```Prolog\n' + message + '\n```', colour=0x4E0092)
    if data['default_modifiers']:
        em.add_field(name="Default Modifiers:", value='```\n' + data['default_modifiers'] + '\n```')
    elif data['username'] == 'Jamu':
        em.add_field(name="Default Modifiers:", value='```\nC1050, 20% Mini, NoMines, Overhead, Krystal+\n```')
    if data['username'] == 'Jamu': 
        ismod = '(Best Mod)'
        em.set_footer(text="If the bot says I'm mod it must be true.")
    if adv: em.set_author(name='{} {} {}\n'.format(data['username'], ismod, ispatron), url='https://etternaonline.com/user/profile/{}'.format(user), icon_url=flagurl)
    else: em.set_author(name='{} #{} {}\n'.format(data['username'], rank['Overall'], ismod), url='https://etternaonline.com/user/profile/{}'.format(user), icon_url=flagurl)
    em.set_thumbnail(url='https://etternaonline.com/avatars/{}'.format(data['avatar']))
    if adv:
        if data['aboutme']:
            em.add_field(name='About {}:'.format(data['username']), value='```\n' + data['aboutme'][:500] + '\n```')
        em.set_image(url='http://198.199.121.145/graphs/{}-{}-{}-{}-{}-{}-{}'.format(data['Stream'],
                                                                                     data['Jumpstream'],
                                                                                     data['Handstream'],
                                                                                     data['Stamina'],
                                                                                     data['JackSpeed'],
                                                                                     data['Chordjack'],
                                                                                     data['Technical']))
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def top10(ctx, user=None, ss=None):
    """Shows the top scores of a user"""
    if user and not check_skillset(user):
        skillset = check_skillset(ss) if ss else check_skillset(user)
    elif check_skillset(user) and ss: 
        skillset = check_skillset(user)
        user = ss
    else:
        skillset = check_skillset(user)
        c = database.cursor()
        record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
        if len(record) < 1:
            await ctx.message.channel.send("You either need to specify a username or run `{}userset [username]`".format(prefix))
            return
        else: user = record[0][0]
    data = await user_data(settings['key'], user)
    if 'error' in data:
        await ctx.message.channel.send("{} not found!".format(user))
        return
    if not data['Overall'] or data['Overall'] == '0':
        message = "Looks like stats, this user has not!"
    else:
        scores = await user_scores(settings['key'], user, 10, skillset)
        message = await buildscores(scores, skillset if skillset else 'Overall')
    flagurl = 'https://etternaonline.com/img/gif/{}.gif'.format(data['countrycode']) if (data['countrycode'] and data['countrycode'] != 'undef') else ''
    em = discord.Embed(description='```\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name="{}'s Top 10{}".format(user, skillset_author(skillset)), url='https://etternaonline.com/user/profile/{}'.format(user), icon_url=flagurl)
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 60, commands.BucketType.user)
@client.command()
async def top25(ctx, user=None, ss=None):
    """Shows the top scores of a user"""
    if ctx.message.author.id != 103139260340633600:
        if ctx.message.channel.id == 339597420239519755:
            return
    if user and not check_skillset(user):
        skillset = check_skillset(ss) if ss else check_skillset(user)
    elif check_skillset(user) and ss: 
        skillset = check_skillset(user)
        user = ss
    else:
        skillset = check_skillset(user)
        c = database.cursor()
        record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
        if len(record) < 1:
            await ctx.message.channel.send("You either need to specify a username or run `{}userset [username]`".format(prefix))
            return
        else: user = record[0][0]
    data = await user_data(settings['key'], user)
    if 'error' in data:
        await ctx.message.channel.send("{} not found!".format(user))
        return
    if not data['Overall'] or data['Overall'] == '0':
        message = "Looks like stats, this user has not!"
    else:
        scores = await user_scores(settings['key'], user, 25, skillset)
        message = await buildscores(scores, skillset if skillset else 'Overall')
    flagurl = 'https://etternaonline.com/img/gif/{}.gif'.format(data['countrycode']) if (data['countrycode'] and data['countrycode'] != 'undef') else ''
    em = discord.Embed(description='```\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name="{}'s Top 25{}".format(user, skillset_author(skillset)), url='https://etternaonline.com/user/profile/{}'.format(user), icon_url=flagurl)
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def lastsession(ctx, user=None):
    """Shows the top scores of a user"""
    if not user:
        skillset = check_skillset(user)
        c = database.cursor()
        record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
        if len(record) < 1:
            await ctx.message.channel.send("You either need to specify a username or run `{}userset [username]`".format(prefix))
            return
        else: user = record[0][0]
    data = await user_data(settings['key'], user)
    if 'error' in data:
        await ctx.message.channel.send("{} not found!".format(user))
        return
    if not data['Overall'] or data['Overall'] == '0':
        message = "Looks like stats, this user has not!"
    else:
        scores = await last_session(settings['key'], user)
        message = await buildscores(scores, 'Overall')
    flagurl = 'https://etternaonline.com/img/gif/{}.gif'.format(data['countrycode']) if (data['countrycode'] and data['countrycode'] != 'undef') else ''
    em = discord.Embed(description='```\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name="{}'s Last 10 Scores".format(user), url='https://etternaonline.com/user/profile/{}'.format(user), icon_url=flagurl)
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def scorecompare(ctx, user1=None, user2=None, skillset=None):
    """Basic comparison of given users."""
    skillset = check_skillset(skillset)
    if not user1:
        await ctx.message.channel.send("You need to provide two users to compare!")
        return
    if not user2:
        await ctx.message.channel.send("You need to provide two users to compare!")
        return
    elif user1.lower() == user2.lower():
        await ctx.message.channel.send("They're so similar that I can't even be bothered to compare them. :^)")
        return
    data1 = await user_data(settings['key'], user1)
    data2 = await user_data(settings['key'], user2)
    if 'error' in data1:
        await ctx.message.channel.send("{} not found!".format(user1))
        return
    elif 'error' in data2:
        await ctx.message.channel.send("{} not found!".format(user2))
        return
    if not data1['Overall'] or not data2['Overall']:
        message = "Looks like one of the users given have no stats!"
    elif data1['Overall'] == '0' or data2['Overall'] == '0':
        message = "Looks like one of the users given have no stats!"
    else:
        scores1 = await user_scores(settings['key'], user1, 25, skillset)
        scores2 = await user_scores(settings['key'], user2, 25, skillset)
        message = await minacompare(scores1, scores2)
    em = discord.Embed(description='```\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name='{} vs. {}{}'.format(data1['username'], data2['username'], skillset_author(skillset)))
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def leaderboard(ctx, country=None):
    """Leaderboards with the optional country code"""
    leaderboard = await get_leaderboard(settings['key'], country)
    if 'error' in leaderboard:
        await ctx.message.channel.send("No users found for that country!")
        return
    longestusername = max([x['username'] for x in leaderboard])
    message = ""
    for i, user in enumerate(leaderboard):
        rating = '({:>4})'.format(round(float(user['Overall']), 2))
        message += "{}. [{}](https://etternaonline.com/user/profile/{}) {}\n".format(i + 1, user['username'], user['username'], rating)
    em = discord.Embed(description=message, colour=0x4E0092)
    em.set_author(name='Leaderboards' + ' of {}'.format(country) if country else '')
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def compare(ctx, user1=None, user2=None):
    """Basic comparison of given users."""
    if not user1:
        await ctx.message.channel.send("You need to provide two users to compare!")
        return
    elif not user2:
        c = database.cursor()
        record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
        if len(record) < 1:
            await ctx.message.channel.send("You either need to specify a second user or run `{}userset [username]`".format(prefix))
            return
        else:
            user2 = user1
            user1 = record[0][0]
    elif user1.lower() == user2.lower():
        await ctx.message.channel.send("They're so similar that I can't even be bothered to compare them. :^)")
        return
    data1 = await user_data(settings['key'], user1)
    data2 = await user_data(settings['key'], user2)
    if 'error' in data1:
        await ctx.message.channel.send("{} not found!".format(user1))
        return
    elif 'error' in data2:
        await ctx.message.channel.send("{} not found!".format(user2))
        return
    if not data1['Overall'] or not data2['Overall']:
        message = "Looks like one of the users given have no stats!"
    elif data1['Overall'] == '0' or data2['Overall'] == '0':
        message = "Looks like one of the users given have no stats!"
    else: message = await compareusers(data1, data2)
    em = discord.Embed(description='```Prolog\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name='{} vs. {}\n'.format(data1['username'], data2['username']))
    await ctx.message.channel.send(embed=em)

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def rival(ctx):
    """Basic comparison of given users."""
    c = database.cursor()
    record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
    if len(record) < 1:
        await ctx.message.channel.send("You need to run `{}userset [username]` first!".format(prefix))
        return
    else: user = record[0][0]
    c = database.cursor()
    record = c.execute('SELECT rival FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
    if not record[0][0]:
        await ctx.message.channel.send("You need to run `{}rivalset [username]` first!".format(prefix))
        return
    else: rival = record[0][0]
    if user.lower() == rival.lower():
        await ctx.message.channel.send("They're so similar that I can't even be bothered to compare them. :^)")
        return
    data1 = await user_data(settings['key'], user)
    data2 = await user_data(settings['key'], rival)
    if 'error' in data1:
        await ctx.message.channel.send("{} not found!".format(user1))
        return
    elif 'error' in data2:
        await ctx.message.channel.send("{} not found!".format(user2))
        return
    if not data1['Overall'] or not data2['Overall']:
        message = "Looks like your rival has no stats!"
    elif data1['Overall'] == '0' or data2['Overall'] == '0':
        message = "Looks like your rival has no stats!"
    else: message = await compareusers(data1, data2)
    em = discord.Embed(description='```Prolog\n' + message + '\n```', colour=0x4E0092)
    em.set_author(name='{} vs. {}\n'.format(data1['username'], data2['username']))
    await ctx.message.channel.send(embed=em)

async def buildprofile(user):
    return await buildmsg(await buildstats(user))

async def buildprofileranks(user, ranks):
    return await buildmsg(await buildranks(user, ranks))

async def buildscores(scores, skill):
    message = ""
    for i, score in enumerate(scores):
        message += "{}. {}: {}x\n".format(i + 1, score['songname'], score['user_chart_rate_rate'])
        if not score[skill]: message += "  ▸ Invalid Score\n"
        else: message += "  ▸ Score: {:.2f} Wife: {:.2f}%\n".format(float(score[skill]), float(score['wifescore']) * 100)
    return message

async def compareusers(user1, user2):
    user1 = await buildstats(user1)
    user2 = await buildstats(user2)
    comparelines = []
    for i in range(8):
        comparelines += [await comparevalue(float(user1[i]), float(user2[i]))]
    return await buildmsg(comparelines)

async def comparevalue(value1, value2):
    diff = value1 - value2
    diff = "{:.2f}".format(diff)
    value1 = round(value1, 2)
    value2 = round(value2, 2)
    if value1 > value2:
        return "{:>4}{}>  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (6 - len(diff))), diff)
    elif value1 < value2:
        return "{:>4}{}<  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (6 - len(diff))), diff)
    elif value1 == value2:
        return "{:>4}{}=  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (6 - len(diff))), diff)
    else:
        return "{:>4}{}?  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (6 - len(diff))), diff)

async def minavalue(value1, value2):
    diff = value1 - value2
    diff = "{:.2f}".format(diff)
    value1 = round(value1, 2)
    value2 = round(value2, 2)
    if value1 > value2:
        return "{:>4}{}>  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (7 - len(diff))), diff)
    elif value1 < value2:
        return "{:>4}{}<  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (7 - len(diff))), diff)
    elif value1 == value2:
        return "{:>4}{}=  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (7 - len(diff))), diff)
    else:
        return "{:>4}{}?  {:>4}{}{}".format(value1, ' ' * (7 - len(str(value1))), value2, ' ' * ((6 - len(str(value2))) + (7 - len(diff))), diff)

async def minacompare(scores1, scores2):
    lines = ""
    for i in range(min(len(scores1), len(scores2))):
        lines += "{:>15} {} {}\n".format(scores1[i]['songname'][:15], await minavalue(float(scores1[i]['Overall']), float(scores2[i]['Overall'])), scores2[i]['songname'][:15])
    return lines

async def buildstats(user):
    stats = ["{:.2f}".format(float(user['Overall']))]
    stats += ["{:.2f}".format(float(user['Stream']))]
    stats += ["{:.2f}".format(float(user['Stamina']))]
    stats += ["{:.2f}".format(float(user['Jumpstream']))]
    stats += ["{:.2f}".format(float(user['Handstream']))]
    stats += ["{:.2f}".format(float(user['JackSpeed']))]
    stats += ["{:.2f}".format(float(user['Technical']))]
    stats += ["{:.2f}".format(float(user['Chordjack']))] if user['Chordjack'] else [0.0]
    return stats

async def buildranks(user, ranks):
    stats = ["{:.2f} (#{})".format(float(user['Overall']), ranks['Overall'])]
    stats += ["{:.2f} (#{})".format(float(user['Stream']), ranks['Stream'])]
    stats += ["{:.2f} (#{})".format(float(user['Stamina']), ranks['Stamina'])]
    stats += ["{:.2f} (#{})".format(float(user['Jumpstream']), ranks['Jumpstream'])]
    stats += ["{:.2f} (#{})".format(float(user['Handstream']), ranks['Handstream'])]
    stats += ["{:.2f} (#{})".format(float(user['JackSpeed']), ranks['JackSpeed'])]
    stats += ["{:.2f} (#{})".format(float(user['Technical']), ranks['Technical'])]
    stats += ["{:.2f} (#{})".format(float(user['Chordjack']), ranks['Chordjack'])] if user['Chordjack'] else [0.0]
    return stats

async def buildmsg(lines):
    message =  "   Overall:   {}\n".format(lines[0])
    message += "    Stream:   {}\n".format(lines[1])
    message += "Jumpstream:   {}\n".format(lines[3])
    message += "Handstream:   {}\n".format(lines[4])
    message += "   Stamina:   {}\n".format(lines[2])
    message += "     Jacks:   {}\n".format(lines[5])
    message += " Chordjack:   {}\n".format(lines[7])
    message += " Technical:   {}\n".format(lines[6])
    return message

async def buildscore(key):
    score = await get_score(settings['key'], key[:41])
    score = score[0]
    wife = round(float(score['wifescore']) * 100, 4) if float(score['wifescore']) * 100 >= 99 else round(float(score['wifescore']) * 100, 2)
    ssrs =  "   Overall: {:>4}{}".format(float(score['Overall']), ' ' * (7 - len(str(round(float(score['Overall']), 2)))))
    ssrs += "      Wife: {}%\n".format(wife)
    ssrs += "    Stream: {:>4}{}".format(float(score['Stream']), ' ' * (7 - len(score['Stream'])))
    ssrs += "   Stamina: {:>4}\n".format(float(score['Stamina']))
    ssrs += "Jumpstream: {:>4}{}".format(float(score['Jumpstream']), ' ' * (7 - len(score['Jumpstream'])))
    ssrs += "Handstream: {:>4}\n".format(float(score['Handstream']))
    ssrs += "     Jacks: {:>4}{}".format(float(score['JackSpeed']), ' ' * (7 - len(score['JackSpeed'])))
    ssrs += " Chordjack: {:>4}\n".format(float(score['Chordjack']))
    ssrs += " Technical: {:>4}\n".format(float(score['Technical']))
    # alljudge = float(score['marv']) + float(score['perfect']) + float(score['great']) + float(score['good']) + float(score['bad']) + float(score['miss'])
    judgements =  "Marvelous:  {:<4}  ".format(score['marv'])
    judgements += "  Perfect:  {:<4}\n".format(score['perfect'])
    judgements += "    Great:  {:<4}  ".format(score['great'])
    judgements += "     Good:  {:<4}\n".format(score['good'])
    judgements += "      Bad:  {:<4}  ".format(score['bad'])
    judgements += "     Miss:  {:<4}\n".format(score['miss'])
    flagurl = 'https://etternaonline.com/img/gif/{}.gif'.format(score['countrycode']) if (score['countrycode'] and score['countrycode'] != 'undef') else ''
    em = discord.Embed(description='```\n' + score['modifiers'] + '\n```', colour=0x4E0092)
    em.set_author(name='{}'.format(score['songname']), url='https://etternaonline.com/song/view/{}'.format(score['id']), icon_url=flagurl)
    em.add_field(name='SSRS', value='```Prolog\n' + ssrs + '\n```')
    em.add_field(name='Judgements', value='```Prolog\n' + judgements + '\n```')
    em.set_footer(text='Played by {}'.format(score['username']))
    em.timestamp = datetime.strptime(score['datetime'], '%Y-%m-%d %H:%M:%S')
    em.set_thumbnail(url='https://etternaonline.com/avatars/{}'.format(score['avatar']))
    if score['replay']:
        await replaygraph(json.loads(score['replay']), key)
        em.set_image(url='http://198.199.121.145/replays/{}.png'.format(key))
    return em

async def replaygraph(replay, key):
    if not os.path.exists('/var/www/html/replays/{}.png'.format(key)):
        img = Image.new('RGBA', (840, 360), (52, 52, 52))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("/root/bots/arial.ttf", 12)
        coords = [(10, '180'), (55, '135'), (100, '90'), (145, '45'), 
            (167.5, '22.5'), (190, '0'), (212.5, '-22.5'), (235, '-45'),
            (280, '-90'), (325, '-135'), (370, '-180')]
        for coord, value in coords:
            wi, _ = draw.textsize(value, font=font)
            draw.text((30 - wi, coord - 5), value, (230, 230, 230), font=font)
            draw.line((40, coord, 840, coord), (230, 230, 230))
        scale = 790 / replay[-1][0]
        for timing in replay:
            draw.ellipse((timing[0] * scale + 39, 380 - (timing[1] + 190) - 1, timing[0] * scale + 41, 380 - (timing[1] + 190) + 1), fill=getcolor(timing[1]))
        img.save('/var/www/html/replays/{}.png'.format(key))

def getcolor(deviance):
    if   deviance <= 22.5 and deviance >= -22.5: return (153,204,255) # Marvelous
    elif deviance <= 45   and deviance > 22.5:   return (242,203,48)  # Perfect
    elif deviance < -22.5 and deviance >= -45:   return (242,203,48)  # Perfect
    elif deviance <= 90   and deviance > 45:     return (20,204,143)  # Great
    elif deviance < -45   and deviance >= -90:   return (20,204,143)  # Great
    elif deviance <= 135  and deviance > 90:     return (26,178,255)  # Good
    elif deviance < -90   and deviance >= -135:  return (26,178,255)  # Good
    elif deviance < 180   and deviance > 135:    return (255,26,179)  # Bad
    elif deviance < -135  and deviance >= -180:  return (255,26,179)  # Bad
    else: return (204,41,41)                                          # Should be a miss

async def buildsong(id):
    song = await get_song(settings['key'], id)
    song = song[0]
    em = discord.Embed(title='Packs:', description='```\n' + '\n'.join(song['packs']) + '\n```', colour=0x4E0092)
    charts = []
    for chart in song['charts']:
        chart['msd'] = float(chart['msd'])
        charts.append(chart)
    for chart in sorted(charts, key=itemgetter('msd'), reverse=True)[:2]:
        message = ""
        for i, score in enumerate(chart['leaderboard']):
            message += "{}. {}: {}x".format(i + 1, score['username'], score['user_chart_rate_rate'])
            message += "  ▸ {:.2f} | {:.2f}%\n".format(float(score['Overall']), float(score['wifescore']) * 100)
        if message == "": message = "No scores on this difficulty."
        status = 'Unranked' if chart['blacklisted'] == '0' else ''
        em.add_field(name="{} - {}: {}".format(chart['difficulty'], chart['msd'], status), value='```\n' + message + '\n```')
    em.set_author(name='{} by {}'.format(song['songname'], song['artist']), url='https://etternaonline.com/song/view/{}'.format(song['id']))
    return em

async def buildpack(id):
    em = discord.Embed(description="Todo")
    #todo if rop even adds this
    return em

def check_skillset(input):
    if   input == '-stream':        return 'Stream'
    elif input == '-stamina':       return 'Stamina'
    elif input == '-jumpstream':    return 'Jumpstream'
    elif input == '-handstream':    return 'Handstream'
    elif input == '-jacks':         return 'JackSpeed'
    elif input == '-chordjack':     return 'Chordjack'
    elif input == '-technical':     return 'Technical'
    else:                           return None

def skillset_author(input):
    if   input == 'Stream':     return ' | Stream'
    elif input == 'Stamina':    return ' | Stamina'
    elif input == 'Jumpstream': return ' | Jumpstream'
    elif input == 'Handstream': return ' | Handstream'
    elif input == 'jackspeed':  return ' | Jacks'
    elif input == 'chordjack':  return ' | Chordjack'
    elif input == 'tech':       return ' | Technical'
    else:                       return ''

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def userset(ctx, user):
    """Allows users to link their account for convenience"""
    data = await user_data(settings['key'], user)
    if 'error' in data:
        await ctx.message.channel.send("Can't set your username because {} not found!".format(user))
        return
    record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
    if len(record) < 1:
        c.execute('INSERT INTO users (discordid, user) VALUES (?, ?)', (ctx.message.author.id, user))
    else:
        c.execute('UPDATE users SET user = (?) WHERE discordid = (?)', (user, ctx.message.author.id))
    await ctx.message.channel.send("Successfully set your username to {}".format(user))
    database.commit()

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command()
async def rivalset(ctx, user):
    """Allows users to link their account for convenience"""
    record = c.execute('SELECT user FROM users WHERE discordid = {}'.format(ctx.message.author.id)).fetchall()
    if len(record) < 1:
        await ctx.message.channel.send("You need to run `{}userset [username]` first!".format(prefix))
        return
    else:
        data = await user_data(settings['key'], user)
        if 'error' in data:
            await ctx.message.channel.send("Can't set your rival because {} not found!".format(user))
            return
        c.execute('UPDATE users SET rival = (?) WHERE discordid = (?)', (user, ctx.message.author.id))
    await ctx.message.channel.send("Successfully set your rival to {}".format(user))
    database.commit()

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command(hidden=True)
async def ping(ctx):
    """Shows the bots ping in ms"""
    t1 = time.perf_counter()
    await ctx.message.channel.trigger_typing()
    t2 = time.perf_counter()
    await ctx.message.channel.send("**Pong.**\nTook {}ms.".format(round((t2-t1)*1000)))

@commands.cooldown(1, 5, commands.BucketType.user)
@client.command(hidden=True)
async def uptime(ctx):
    """Shows bot uptime"""
    now = datetime.utcnow()
    delta = now - client.uptime
    hours, remaining = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remaining, 60)
    days, hours = divmod(hours, 24)
    passed = ''
    passed += '{} Days, '.format(days) if days != 0 else ''
    passed += '{} Hours, '.format(hours) if hours != 0 else ''
    passed += '{} Minutes, '.format(minutes) if minutes != 0 else ''
    passed += '{} Seconds'.format(seconds)
    await ctx.message.channel.send("Been up for: **{}**".format(passed))

client.remove_command('help')
@commands.cooldown(1, 5, commands.BucketType.user)
@client.command(name='help', hidden=True)
async def _help(ctx, command=None):
    helpmsg = 'Here are my commands: (Descriptions by Fission)\n'
    helpmsg += "**{}profile [username]**\n        *Show your fabulously superberful profile*\n".format(prefix)
    helpmsg += "**{}advprof [username]**\n        *Now with delta graphs!*\n".format(prefix)
    helpmsg += "**{}top10 [username] [skillset]**\n        *For when top9 isn't enough*\n".format(prefix)
    helpmsg += "**{}top25 [username] [skillset]**\n        *Sometimes we take things too far*\n".format(prefix)
    helpmsg += "**{}compare [user1] [user2]**\n        *One person is an objectively better person than the other, find out which one!*\n".format(prefix)
    helpmsg += "**{}rival**\n        *But are you an objectively better person than gary oak?*\n".format(prefix)
    helpmsg += "**{}rivalset [username]**\n        *Replace gary oak with a more suitable rival*\n".format(prefix)
    helpmsg += "**{}userset [username]**\n        *Don't you dare set your user to {} you imposter*\n\n".format(prefix, random.choice(minanym))
    helpmsg += "**Skillsets are specified as following:**\n"
    helpmsg += "    *-stream -stamina -jumpstream -handstream -jacks -chordjack -technical*\n"
    helpmsg += "You can also post links to scores and songs and the I will show info about them"
    em = discord.Embed(description=helpmsg, color=0x4E0092)
    em.set_footer(text='I have existed since')
    em.timestamp = client.user.created_at
    await ctx.message.channel.send(embed=em)

async def checkmessages(message):
    if message.channel.id == 374774075865956355 and message.author.id != 361169097418866688 and not message.content.startswith('_ _'):
        links = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
        if len(links) == 0 and len(message.attachments) == 0:
            await message.delete()
            message = await message.channel.send('Links and attachments only in this channel please. <:meguw:372962655327092739>')
            await asyncio.sleep(5)
            await message.delete()
            return False
    # If it's Jamu, allow it :^)
    if message.author.id == 103139260340633600: return True
    # If the message is in etternaonline server, and not in an allowed channel, don't process the command
    allowedchans = [384829579308564480, 352646080346849281, 367466722405515264, 427509181457629184, 424545864351219712]
    if message.channel.guild.id == 339597420239519755 and message.channel.id not in allowedchans:
        # However if the person has the permission to manage the guild, then allow it anyways
        if not message.author.guild_permissions.manage_guild:
            return False
    return True

@client.event
async def on_member_update(old, new):
    if old.guild.id == 339597420239519755:
        channel = client.get_channel(389194939881488385)
        if not 'MAX 300' in [str(x) for x in old.roles]:
            if 'MAX 300' in [str(x) for x in new.roles]:
                await channel.send('Congrats on the promotion, <@{}>!'.format(old.id))

@client.command(hidden=True)
async def servers(ctx):
    if ctx.message.author.id == 103139260340633600:
        message = ''
        for i, server in enumerate(client.guilds):
            message += '**{}.** {}\n'.format(i + 1, server.name)
        await ctx.message.channel.send(message)

@client.command(hidden=True)
async def debug(ctx, *, code):
    """Evaluates code"""
    if ctx.message.author.id == 103139260340633600:
        author = ctx.message.author
        channel = ctx.message.channel
        code = code.strip('` ')
        result = None
        global_vars = globals().copy()
        global_vars['bot'] = client
        global_vars['ctx'] = ctx
        global_vars['message'] = ctx.message
        global_vars['author'] = ctx.message.author
        global_vars['channel'] = ctx.message.channel
        global_vars['server'] = ctx.message.guild
        try:
            result = eval(code, global_vars, locals())
        except Exception as e:
            await channel.send("```py\n{}: {}```".format(type(e).__name__, str(e)))
            return
        if asyncio.iscoroutine(result):
            result = await result
        await channel.send("```py\n{}```".format(str(result)))

@client.command(hidden=True)
async def roles(ctx):
    message = ""
    for role in ctx.message.channel.guild.roles[1:]:
        message += "@{} ".format(role.name)
    await ctx.message.channel.send(message)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        message = await ctx.message.channel.send("This command is on cooldown. Try again in {:.2f}s".format(error.retry_after))
        await asyncio.sleep(error.retry_after)
        await message.delete()
    else:
        message = ("Error in command '{}'.\n```{}```".format(ctx.command.qualified_name, error))
        await ctx.message.channel.send(message)

try:
    client.run(settings['token'])
except:
    database.close()
database.close()
