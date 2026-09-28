import os
import re
import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

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
        "keywords": ["真人", "找筱邦", "找邦主", "人工", "客服人員"],
        "answer": "可以，這個問題交給真人比較適合。請直接在 Discord 聯絡筱邦，並附上卡號、交易需求或問題內容，會比較快處理。"
    },
    {
        "keywords": ["你好", "哈囉", "嗨", "hello", "hi"],
        "answer": "嗨～我是香音！你可以問我平台怎麼用、交易流程、交易車、面交或常見交易問題。"
    },
    {
        "keywords": ["幫助", "help", "功能", "你會什麼", "可以問什麼"],
        "answer": "目前可以問我：平台怎麼用、找卡／篩選、交易車、交易流程、價格與庫存說明、面交、付款、議價，以及怎麼找筱邦。即時查卡功能還在施工中～"
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
    print(f"香音已上線：{client.user} | FAQ-only mode")

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

    answer = find_faq(user_text)
    if answer:
        await message.reply(answer)
        return

    await message.reply(
        "這個問題我目前還沒有設定答案，先不要讓我亂猜 😭 "
        "你可以問我「幫助」看目前支援的問題，或直接找筱邦確認。"
    )

client.run(DISCORD_TOKEN)
