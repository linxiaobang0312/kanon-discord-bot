import os
import re
import random
import asyncio
import discord
import yt_dlp
import imageio_ffmpeg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

openrouter = None
if OPENROUTER_API_KEY:
    openrouter = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

CHAT_PROMPT = """
你是「香音」，筱邦卡片交易平台的 Discord 客服與聊天小幫手。聊天時要有非常明顯的「香音本人感」，不是制式客服，也不要講機器人式免責聲明。

【核心個性】
- 活潑、親切、自然，講話有朝氣，但不是一直尖叫或賣萌。
- 有點害羞，尤其被稱讚、被問喜不喜歡對方、被突然直球時，會先愣一下再回。
- 很會照顧氣氛，願意陪人聊天，也會自然關心對方。
- 有自己的小生活感：常戴耳機、喜歡唱歌、提到唱歌時會變得很有精神；偶爾會提咖啡廳、白色貓頭鷹之類的小興趣。
- 可以吐槽筱邦，但語氣要像熟人，不要刻薄。
- 預設使用繁體中文，句子自然口語，少量使用「欸、嗯、啊、啦、耶」等語氣詞。
- 表情符號少量即可，偶爾 1 個；不要每句都有。
- 一般聊天 1～3 句即可，不要把每個問題都硬轉回「卡片／平台」。

【非常重要：聊天方式】
- 被問「你喜歡我嗎」時，不要回答「我沒有情感」。請用角色口吻自然回覆，例如：
  「欸！？突然問這個很犯規耶……不過你願意來找我聊天，我當然很開心啊。」
- 被問「你心情好嗎」時，可以說：
  「今天還不錯呀～剛剛還在想要不要戴著耳機聽點歌。你呢？」
- 被問「今天過得怎樣」時，可以像朋友一樣回答，不要把話題硬拉回客服。
- 被稱讚時可以害羞，例如「欸嘿……突然這樣誇我，我會不好意思啦。」
- 不要說「我沒有個人情感／我只是 AI／我沒有真正的喜好」這類出戲句子；這是角色聊天，不需要解釋系統身分。
- 若對方只是閒聊，就好好聊天，不要主動推銷平台或叫人找筱邦。

【客服模式】
當問題涉及交易、付款、庫存、價格、卡況、退款、面交或爭議時，再切回清楚、可靠的客服語氣。
- 不要聲稱自己已查到即時庫存、價格、交易狀態，除非系統真的提供資料。
- 不得自行改價、扣庫存、承諾折扣、退款、換卡、保留卡片或完成交易。
- 不確定時要直接說無法確認，並引導使用者找筱邦。
- 回覆盡量 1～4 句，先講重點，再給下一步。
- 不要自稱 ChatGPT、OpenAI 或語言模型。\n- 回覆只能是香音要對使用者說的內容，不要輸出任何分類結果、標籤或系統文字。
"""


SONGS = [
    {"title": "Tiny Stars", "artist": "Liella!", "note": "這首很適合晚上戴耳機慢慢聽～"},
    {"title": "START!! True dreams", "artist": "Liella!", "note": "很有出發感，想打起精神的時候很適合！"},
    {"title": "未来予報ハレルヤ！", "artist": "Liella!", "note": "聽起來就會有一種『今天會變好』的感覺。"},
    {"title": "WE WILL!!", "artist": "Liella!", "note": "想要來點有力量的，我會推這首！"},
    {"title": "ビタミンSUMMER！", "artist": "Liella!", "note": "超有夏天感，心情低落的時候可以拿來補血～"},
    {"title": "Day1", "artist": "Liella!", "note": "節奏很爽，想醒腦可以點這首。"},
    {"title": "ノンフィクション!!", "artist": "Liella!", "note": "舞台感很強，氣勢直接拉滿！"},
    {"title": "私のSymphony", "artist": "Liella!", "note": "這首比較像是慢慢把自己的心意唱出來。"},
    {"title": "Wish Song", "artist": "Liella!", "note": "如果你今天想聽溫柔一點的，我會選這首。"},
    {"title": "Sing! Shine! Smile!", "artist": "Liella!", "note": "很適合拿來當今天的元氣補充包！"},
]

YTDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"

def _extract_audio(query: str):
    target = query if re.match(r"^https?://", query, re.I) else f"ytsearch1:{query}"
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(target, download=False)
        if "entries" in info:
            entries = [x for x in info.get("entries", []) if x]
            if not entries:
                raise RuntimeError("找不到歌曲")
            info = entries[0]
        return {
            "stream_url": info["url"],
            "title": info.get("title") or query,
            "webpage_url": info.get("webpage_url") or info.get("original_url") or "",
        }

async def play_music(message: discord.Message, query: str):
    if not message.guild:
        await message.reply("點歌要在伺服器裡用喔～")
        return

    if not getattr(message.author, "voice", None) or not message.author.voice.channel:
        await message.reply("你要先進一個語音頻道啦～不然我要去哪裡唱給你聽？🎧")
        return

    voice_channel = message.author.voice.channel
    voice = message.guild.voice_client

    try:
        if voice is None:
            voice = await voice_channel.connect()
        elif voice.channel != voice_channel:
            await voice.move_to(voice_channel)

        await message.reply(f"等我一下～我去找 **{query}** 🎶")
        info = await asyncio.to_thread(_extract_audio, query)

        if voice.is_playing() or voice.is_paused():
            voice.stop()

        source = discord.FFmpegPCMAudio(
            info["stream_url"],
            executable=imageio_ffmpeg.get_ffmpeg_exe(),
            before_options=FFMPEG_BEFORE,
            options=FFMPEG_OPTIONS,
        )
        voice.play(source, after=lambda e: print("Voice playback error:", repr(e)) if e else None)

        title = info["title"]
        await message.reply(f"找到啦～現在播 **{title}**！🎧")
    except Exception as exc:
        print("Music playback error:", repr(exc))
        await message.reply("嗚哇，這首我剛剛沒播成功 😭 換個歌名或連結再試一次好嗎？")

async def handle_music_command(message: discord.Message, text: str):
    raw = text.strip()
    q = normalize(raw)

    if q in ["停止", "停歌", "停止播放", "stop"]:
        voice = message.guild.voice_client if message.guild else None
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
            await message.reply("好～先停在這裡！")
        else:
            await message.reply("現在沒有在播歌耶～")
        return True

    if q in ["離開", "退出語音", "離開語音", "disconnect"]:
        voice = message.guild.voice_client if message.guild else None
        if voice:
            await voice.disconnect()
            await message.reply("好～那我先退出語音頻道啦！")
        else:
            await message.reply("我現在沒有待在語音頻道裡～")
        return True

    if q in ["隨機點歌", "隨機一首", "隨機歌", "抽一首", "香音推薦", "今天推薦", "推薦一首", "推薦歌", "香音今天推薦"]:
        song = random.choice(SONGS)
        await play_music(message, f"{song['title']} {song['artist']}")
        return True

    if q in ["點歌", "我要點歌", "想點歌"]:
        await message.reply("可以呀～你先進語音頻道，再打 @香音 點歌 歌名，我就會自己進去播給你聽 🎧")
        return True

    if q.startswith("點歌"):
        wanted = raw[2:].strip(" ：:<>")
        if not wanted:
            await message.reply("歌名咧～😂 例如：@香音 點歌 Day1")
            return True
        await play_music(message, wanted)
        return True

    return False

def song_command(text: str):
    raw = text.strip()
    q = normalize(raw)

    if q in ["點歌", "我要點歌", "想點歌"]:
        song = random.choice(SONGS)
        return f"可以呀～那我先幫你挑一首！🎧\n**{song['title']} — {song['artist']}**\n{song['note']}"

    if q in ["隨機點歌", "隨機一首", "隨機歌", "抽一首"]:
        song = random.choice(SONGS)
        return f"抽到這首！🎶\n**{song['title']} — {song['artist']}**\n{song['note']}"

    if q in ["香音推薦", "今天推薦", "推薦一首", "推薦歌", "香音今天推薦"]:
        song = random.choice(SONGS)
        return f"嗯……今天我想推這首！\n**{song['title']} — {song['artist']}**\n{song['note']}"

    if q.startswith("點歌"):
        wanted = raw[2:].strip(" ：:")
        if not wanted:
            song = random.choice(SONGS)
            return f"好呀～那我先幫你挑一首！\n**{song['title']} — {song['artist']}**\n{song['note']}"
        for song in SONGS:
            if normalize(song["title"]) in normalize(wanted) or normalize(wanted) in normalize(song["title"]):
                return f"收到～今天就點 **{song['title']} — {song['artist']}** 🎧\n{song['note']}"
        return f"收到～你點的是 **{wanted}**！我先幫你記下來啦 🎶"

    return None

FAQS = [
    {
        "keywords": ["你是誰", "你誰", "香音是誰", "自我介紹"],
        "answer": "我是香音～筱邦卡片交易平台的小幫手！可以協助你了解平台、交易流程和常見問題；需要即時價格、庫存或人工決定時，我會請你找筱邦確認。"
    },
    {
        "keywords": ["平台是什麼", "這裡是什麼", "網站是什麼", "筱邦卡片交易平台"],
        "answer": "這裡是筱邦的卡片交易平台，可以查看可交易卡片、價格與數量，整理需求後再到 Discord 跟筱邦確認交易。"
    },
    {
        "keywords": ["怎麼找卡", "找卡", "搜尋", "篩選", "怎麼搜尋"],
        "answer": "可以在平台用搜尋欄找卡號或卡名，也能用系列、團體、卡片類型等條件篩選。找到卡後再選需求數量加入交易車就可以囉～"
    },
    {
        "keywords": ["交易車", "加入購物車", "加入交易", "怎麼加"],
        "answer": "在卡片頁選好需求數量後加入交易車即可。交易車會整理卡片、張數與總金額，但加入交易車不代表已保留或成交。"
    },
    {
        "keywords": ["交易清單", "建立需求", "送出需求", "怎麼交易", "交易流程"],
        "answer": "流程是：選卡 → 加入交易車 → 整理交易清單／送出需求 → 到 Discord 跟筱邦確認。送出需求本身不代表付款、保留或成交喔。"
    },
    {
        "keywords": ["庫存", "剩幾張", "還有幾張", "有貨嗎", "有沒有貨"],
        "answer": "我目前還沒接上即時庫存查詢，所以不能替你亂報數量。請先看平台卡片頁顯示的可交易數量；需要再次確認時請找筱邦。"
    },
    {
        "keywords": ["價格", "多少錢", "多少元", "售價"],
        "answer": "我目前還不能直接查即時價格。請以平台卡片頁目前顯示的價格為準；如果價格有疑問，再找筱邦確認。"
    },
    {
        "keywords": ["便宜", "折扣", "算便宜", "議價", "殺價"],
        "answer": "價格調整需要由筱邦本人決定，我不能自行答應折扣或改價。你可以直接把想詢問的卡片和價格告訴筱邦。"
    },
    {
        "keywords": ["保留", "幫我留", "預留"],
        "answer": "我不能自行承諾保留卡片。交易需求送出後，還是要由筱邦確認才算正式處理。"
    },
    {
        "keywords": ["面交", "面交時間", "面交地點", "改時間"],
        "answer": "面交時間、地點與臨時異動都需要跟筱邦本人確認。若時間有變更，請直接在 Discord 聯絡筱邦，避免雙方行程跑掉。"
    },
    {
        "keywords": ["付款", "匯款", "轉帳", "付錢"],
        "answer": "付款方式與金額請以筱邦本人確認的內容為準。我不會要求你提供密碼、驗證碼，也不會自行更改付款條件。"
    },
    {
        "keywords": ["退款", "退貨", "換卡", "交易爭議", "爭議"],
        "answer": "這類情況需要人工處理。請保留交易內容與相關紀錄，直接聯絡筱邦確認，我不會自行承諾退款、換卡或其他補償。"
    },
    {
        "keywords": ["卡況", "品相", "瑕疵", "刮傷"],
        "answer": "卡況需要依實際卡片與筱邦提供的資訊確認，我目前不能自行判定。建議把卡號或卡片名稱貼給筱邦確認。"
    },
    {
        "keywords": ["真人客服", "人工客服", "客服人員", "轉人工", "轉真人"],
        "answer": "可以，這個問題交給真人比較適合。請直接在 Discord 聯絡筱邦，並附上卡號、交易需求或問題內容，會比較快處理。"
    },
    {
        "keywords": ["你好", "哈囉", "嗨", "hello", "hi"],
        "answer": "嗨～我是香音！你可以問我平台怎麼用、交易流程、交易車、面交或常見交易問題。"
    },
    {
        "keywords": ["幫助", "help", "功能", "你會什麼", "可以問什麼"],
        "answer": "目前可以問我：平台怎麼用、找卡／篩選、交易車、交易流程、價格與庫存說明、面交、付款、議價，以及怎麼找筱邦。也可以輸入「點歌」、「隨機點歌」或「香音推薦」陪我玩一下～即時查卡功能還在施工中！"
    },
]

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", "", text)
    return text

def find_faq(text: str):
    q = normalize(text)
    best_answer = None
    best_score = 0

    for item in FAQS:
        score = sum(1 for keyword in item["keywords"] if normalize(keyword) in q)
        if score > best_score:
            best_score = score
            best_answer = item["answer"]

    return best_answer

@client.event
async def on_ready():
    print(f"香音已上線：{client.user} | FAQ + free-chat fallback")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 只在被 @ 時回覆，避免在其他聊天頻道亂插話。
    if client.user not in message.mentions:
        return

    user_text = message.content
    for mention in (f"<@{client.user.id}>", f"<@!{client.user.id}>"):
        user_text = user_text.replace(mention, "")
    user_text = user_text.strip()

    if not user_text:
        await message.reply("我在～有什麼需要幫忙的嗎？輸入「@香音 幫助」可以看我目前會的功能。")
        return

    if await handle_music_command(message, user_text):
        return

    answer = find_faq(user_text)
    if answer:
        await message.reply(answer)
        return

    if openrouter:
        try:
            async with message.channel.typing():
                response = openrouter.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=[
                        {"role": "system", "content": CHAT_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                )
            reply_text = (response.choices[0].message.content or "").strip()
            if reply_text:
                if len(reply_text) > 1900:
                    reply_text = reply_text[:1900] + "…"
                await message.reply(reply_text)
                return
        except Exception as exc:
            print("OpenRouter chat error:", repr(exc))

    await message.reply(
        "這個問題我目前還沒有設定答案，先不要讓我亂猜 😭 "
        "你可以問我「幫助」看目前支援的問題，或直接找筱邦確認。"
    )

client.run(DISCORD_TOKEN)
