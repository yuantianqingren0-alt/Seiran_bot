# Python 3.10+ | pip install discord.py requests flask gunicorn audioop-lts
import os
import threading
import asyncio
import time
import random
import requests
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN")

# ── Bot定義 ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Flask ──────────────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "online", 200

@flask_app.route("/ping")
def ping():
    return "pong", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# ── ヘッダー生成 ───────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

def make_headers(token: str) -> dict:
    return {
        "Authorization"     : token,
        "Content-Type"      : "application/json",
        "User-Agent"        : random.choice(USER_AGENTS),
        "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImphIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMC4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIwLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjI3MDQwNiwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0=",
        "X-Discord-Locale"  : "ja",
        "Origin"            : "https://discord.com",
        "Referer"           : "https://discord.com/channels/@me",
    }

# ── トークン検証 ───────────────────────────────────────────────────
def validate_token(token: str) -> dict | None:
    r = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers=make_headers(token),
        timeout=10,
    )
    return r.json() if r.status_code == 200 else None

# ── メッセージ取得 ─────────────────────────────────────────────────
def get_message(token: str, channel_id: str, message_id: str) -> dict | None:
    headers = make_headers(token)
    for api_ver in ["v10", "v9"]:
        r = requests.get(
            f"https://discord.com/api/{api_ver}/channels/{channel_id}/messages/{message_id}",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    return None

# ── 転送スパム本体 ──────────────────────────────────────────────────
def do_forward_spam(
    tokens: list[str],
    src_channel_id: str,
    src_message_id: str,
    dst_guild_id: str,
    count: int,
    delay: float,
    result_channel,
    loop,
):
    # 有効なトークンだけ残す
    valid_tokens = []
    for t in tokens:
        u = validate_token(t)
        if u:
            valid_tokens.append(t)
            asyncio.run_coroutine_threadsafe(
                result_channel.send(f"✅ トークン有効: `{u['username']}`"),
                loop,
            )
        else:
            asyncio.run_coroutine_threadsafe(
                result_channel.send(f"❌ トークン無効: `{t[:20]}...`"),
                loop,
            )

    if not valid_tokens:
        asyncio.run_coroutine_threadsafe(
            result_channel.send("❌ 有効なトークンがありません"),
            loop,
        )
        return

    # メッセージ取得 (有効トークンの最初のもので取得)
    msg_data = get_message(valid_tokens[0], src_channel_id, src_message_id)
    if not msg_data:
        asyncio.run_coroutine_threadsafe(
            result_channel.send(
                "❌ メッセージ取得失敗\n"
                "・チャンネルIDとメッセージIDを確認\n"
                "・そのチャンネルにアクセス権があるか確認"
            ),
            loop,
        )
        return

    msg_content = msg_data.get("content", "") or "[添付ファイル/埋め込み]"
    asyncio.run_coroutine_threadsafe(
        result_channel.send(f"📨 メッセージ取得成功: `{msg_content[:80]}`"),
        loop,
    )

    # 転送先チャンネル取得
    r2 = requests.get(
        f"https://discord.com/api/v10/guilds/{dst_guild_id}/channels",
        headers=make_headers(valid_tokens[0]),
        timeout=10,
    )
    if r2.status_code != 200:
        asyncio.run_coroutine_threadsafe(
            result_channel.send(f"❌ サーバー取得失敗: {r2.status_code}"),
            loop,
        )
        return

    channels = [c for c in r2.json() if c["type"] == 0]
    if not channels:
        asyncio.run_coroutine_threadsafe(
            result_channel.send("❌ 転送先チャンネルが見つかりません"),
            loop,
        )
        return

    asyncio.run_coroutine_threadsafe(
        result_channel.send(
            f"🎯 転送先チャンネル数: {len(channels)}個\n"
            f"🔑 使用トークン数: {len(valid_tokens)}個\n"
            f"⏳ スパム開始..."
        ),
        loop,
    )

    success_total = 0
    lock = threading.Lock()
    token_index = 0
    token_lock  = threading.Lock()

    def next_token() -> str:
        nonlocal token_index
        with token_lock:
            t = valid_tokens[token_index % len(valid_tokens)]
            token_index += 1
            return t

    def spam_channel(ch: dict):
        nonlocal success_total
        ch_id = ch["id"]

        for i in range(count):
            token   = next_token()
            headers = make_headers(token)

            try:
                # 転送として送信
                payload = {
                    "content": msg_content,
                    "message_reference": {
                        "type"      : 1,
                        "channel_id": src_channel_id,
                        "message_id": src_message_id,
                    },
                    "flags": 16384,
                }
                resp = requests.post(
                    f"https://discord.com/api/v10/channels/{ch_id}/messages",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )

                # 転送失敗なら通常送信
                if resp.status_code not in (200, 201):
                    payload2 = {"content": msg_content}
                    resp = requests.post(
                        f"https://discord.com/api/v10/channels/{ch_id}/messages",
                        headers=headers,
                        json=payload2,
                        timeout=10,
                    )

                if resp.status_code in (200, 201):
                    with lock:
                        success_total += 1
                elif resp.status_code == 429:
                    retry = resp.json().get("retry_after", 1.0)
                    time.sleep(float(retry))
                    continue
                elif resp.status_code == 403:
                    # 権限なしはスキップ
                    return
                elif resp.status_code == 401:
                    # トークン無効は次のトークンへ
                    continue

            except Exception as e:
                print(f"エラー: {e}")

            # ランダムディレイでレート制限回避
            time.sleep(delay + random.uniform(0, 0.2))

    threads = []
    for ch in channels:
        t = threading.Thread(target=spam_channel, args=(ch,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    asyncio.run_coroutine_threadsafe(
        result_channel.send(
            f"✅ 完了\n"
            f"転送成功: {success_total}件\n"
            f"対象チャンネル: {len(channels)}個\n"
            f"使用トークン: {len(valid_tokens)}個"
        ),
        loop,
    )


# ── モーダル ───────────────────────────────────────────────────────
class SpamModal(discord.ui.Modal, title="転送スパム設定"):
    user_tokens = discord.ui.TextInput(
        label="ユーザートークン (改行で複数指定可)",
        placeholder="トークン1\nトークン2\nトークン3",
        style=discord.TextStyle.paragraph,
        required=True,
    )
    src_channel_id = discord.ui.TextInput(
        label="転送元 チャンネルID",
        placeholder="転送したいメッセージのチャンネルID",
        style=discord.TextStyle.short,
        required=True,
    )
    src_message_id = discord.ui.TextInput(
        label="転送元 メッセージID",
        placeholder="転送したいメッセージのID",
        style=discord.TextStyle.short,
        required=True,
    )
    dst_guild_id = discord.ui.TextInput(
        label="転送先 サーバーID",
        placeholder="スパム先のサーバーID",
        style=discord.TextStyle.short,
        required=True,
    )
    settings = discord.ui.TextInput(
        label="回数 / 間隔(秒) 例: 10 / 0.5",
        placeholder="10 / 0.5",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # トークンを改行で分割
        tokens = [
            t.strip()
            for t in self.user_tokens.value.strip().splitlines()
            if t.strip()
        ]

        if not tokens:
            await interaction.followup.send(
                "❌ トークンを入力してください",
                ephemeral=True,
            )
            return

        try:
            parts = self.settings.value.replace(" ", "").split("/")
            count = int(parts[0])
            delay = float(parts[1])
        except Exception:
            await interaction.followup.send(
                "❌ 設定の形式が違います。例: `10 / 0.5`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"🔍 {len(tokens)}個のトークンを検証中...",
            ephemeral=True,
        )

        loop = asyncio.get_event_loop()
        t = threading.Thread(
            target=do_forward_spam,
            args=(
                tokens,
                self.src_channel_id.value.strip(),
                self.src_message_id.value.strip(),
                self.dst_guild_id.value.strip(),
                count,
                delay,
                interaction.channel,
                loop,
            ),
            daemon=True,
        )
        t.start()


# ── スラッシュコマンド ─────────────────────────────────────────────
@bot.tree.command(name="spam", description="転送スパムを実行します")
@app_commands.checks.has_permissions(administrator=True)
async def spam_command(interaction: discord.Interaction):
    await interaction.response.send_modal(SpamModal())


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")
    await bot.tree.sync()
    print("コマンド同期完了")


# ── 起動 ───────────────────────────────────────────────────────────
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

bot.run(TOKEN)
