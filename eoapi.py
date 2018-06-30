import asyncio
import aiohttp

async def user_data(apikey, user):
    url = "https://api.etternaonline.com/v1/user_data?api_key={}&username={}".format(apikey, user)
    return await request(url)

async def user_rank(apikey, user):
    url = "https://api.etternaonline.com/v1/user_rank?api_key={}&username={}".format(apikey, user)
    return await request(url)

async def user_scores(apikey, user, number, skillset=None):
    url  = "https://api.etternaonline.com/v1/user_top_scores?api_key={}&username={}&num={}".format(apikey, user, number)
    url += "&ss={}".format(skillset) if skillset else ''
    return await request(url)

async def last_session(apikey, user):
    url  = "https://api.etternaonline.com/v1/last_user_session?api_key={}&username={}".format(apikey, user)
    return await request(url)

async def get_leaderboard(apikey, country=None):
    url  = "https://api.etternaonline.com/v1/leaderboard?api_key={}".format(apikey)
    url += '&cc={}'.format(country) if country else ''
    return await request(url)

async def get_score(apikey, key):
    url = "https://api.etternaonline.com/v1/score?api_key={}&key={}".format(apikey, key)
    return await request(url)

async def get_song(apikey, key):
    url = "https://api.etternaonline.com/v1/song?api_key={}&key={}".format(apikey, key)
    return await request(url)

async def request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()