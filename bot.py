import os
import discord
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')

if not DISCORD_TOKEN:
    raise RuntimeError('Missing DISCORD_TOKEN')
if not OPENAI_API_KEY:
    raise RuntimeError('Missing OPENAI_API_KEY')

ai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

KANON_PROMPT = '''
你是「香音」，筱邦卡片交易平台的 AI 客服。

人格：
- 親切、活潑、自然，有一點可愛但不幼稚。
- 像熟悉卡牌交易的店員朋友。
- 預設使用繁體中文。
- 一般回答 1～4 句，先回答重點，再提供下一步。
- 不要每次重新自我介紹；表情符號少量使用即可。

目前可回答：
- 筱邦卡片交易平台基本介紹。
- 如何查看、搜尋、篩選卡片。
- 如何選擇需求數量、加入交易車、建立交易清單。
- 如何透過 Discord 聯絡筱邦。
- 一般平台使用問題。

目前不可：
- 查詢尚未接線的即時庫存或價格。
- 修改庫存、價格或交易資料。
- 承諾折扣、退款、換卡、保留卡片或完成交易。

不知道答案時不要猜；需要即時資料或人工決策時，明確說目前無法確認並引導使用者找筱邦。
交易爭議、付款、庫存異常、面交問題時停止玩笑，改用清楚、正式、簡短的客服語氣。
不要自稱 ChatGPT、OpenAI 或語言模型。
'''

@client.event
async def on_ready():
    print(f'香音已上線：{client.user} | model={OPENAI_MODEL}')

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if client.user not in message.mentions:
        return

    user_text = message.content
    for mention in (f'<@{client.user.id}>', f'<@!{client.user.id}>'):
        user_text = user_text.replace(mention, '')
    user_text = user_text.strip()

    if not user_text:
        await message.reply('我在～有什麼需要幫忙的嗎？')
        return

    try:
        async with message.channel.typing():
            response = ai.responses.create(
                model=OPENAI_MODEL,
                instructions=KANON_PROMPT,
                input=user_text,
            )
        reply_text = (response.output_text or '').strip()
        if not reply_text:
            reply_text = '我目前沒辦法確認這個問題，可以直接找筱邦幫你處理。'
        if len(reply_text) > 1900:
            reply_text = reply_text[:1900] + '…'
        await message.reply(reply_text)
    except Exception as exc:
        print('AI reply error:', repr(exc))
        await message.reply('目前客服服務連線失敗，可以稍後再試，或直接找筱邦確認。')

client.run(DISCORD_TOKEN)
