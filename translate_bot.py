from aiohttp import web
from discord import app_commands
import os, re, discord, aiohttp
import asyncio

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
CF_ID           = os.getenv("CF_ACCOUNT_ID")
CF_TOKEN        = os.getenv("CF_API_TOKEN")
KOYEB_URL       = os.getenv("KOYEB_URL")

# 한·일 문자 체크용 정규식
JA = re.compile(r'[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9faf]')
KO = re.compile(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check) # Health Check API 추가
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()

async def ping_self():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with aiohttp.ClientSession() as s:
                await s.get(KOYEB_URL)
        except:
            pass
        await asyncio.sleep(180)

async def translate(text: str, src: str, tgt: str) -> str:
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/ai/run/@cf/meta/m2m100-1.2b"
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type":  "application/json"
    }
    json_body = {"text": text, "source_lang": src, "target_lang": tgt}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url, json=json_body, headers=headers) as r:
            data = await r.json()
    return data["result"]["translated_text"]

# 메시지에서 멘션(<@…>)이나 "이름: " 형태의 접두사를 제거
def strip_prefix(text: str) -> str:
    # <@123…> 또는 <@!123…> 형태 멘션 제거
    text = re.sub(r'^<@!?\d+>\s*', '', text)
    # "username: 내용" 형태 제거
    text = re.sub(r'^[^:\s]+:\s*', '', text)
    return text

@tree.context_menu(name="KR-JP translate")
async def translate_menu(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    original = message.content
    to_translate = strip_prefix(original)

    if JA.search(to_translate):
        src, tgt = "ja", "ko"
    elif KO.search(to_translate):
        src, tgt = "ko", "ja"
    else:
        return await interaction.followup.send("한·일 텍스트가 아닙니다. 日本語・韓国語ではありません。", ephemeral=True)

    translated = await translate(to_translate, src, tgt)

    # 원문 삭제
    await message.delete()

    # 서버 닉네임 우선, 없으면 글로벌 유저네임
    author         = message.author
    webhook_name   = author.display_name
    webhook_avatar = author.display_avatar

    # 웹훅으로 재전송
    wh = await message.channel.create_webhook(
        name=webhook_name,
        avatar=await webhook_avatar.read()
    )
    await wh.send(
        f"{original}\n\n{translated}",
        username=webhook_name,
        avatar_url=webhook_avatar.url
    )
    await wh.delete()

    await interaction.followup.send("번역 완료! 翻訳完了！", ephemeral=True)


@bot.event
async def on_ready():
    await tree.sync()
    bot.loop.create_task(ping_self())
    print(f"Bot ready: {bot.user}")

bot.run(DISCORD_TOKEN)
