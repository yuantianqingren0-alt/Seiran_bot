# Python 3.10+ | pip install discord.py requests flask gunicorn
import os
import threading
import asyncio
import time
import requests
from flask import Flask
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN")

# ── Flask (ポート開放用) ───────────────────────────────────────────
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


# ── 転送スパム本体 ──────────────────────────────────────────────────
def do_forward_spam(
    user_token: str,
    src_channel_id: str,
    src_message_id: str,
    dst_guild_id: str,
    count: int,
    delay: float,
    result_channel,
    loop,
):
    headers = {
        "Authorization": user_token,
        "Content-Type" : "application/json",
    }

    # 転送元メッセージ取得
    r = requests.get(
        f"https://discord.com/api/v10/channels/{src_channel_id}/messages/{src_message_id}",
        headers=headers, timeout=10,
    )
    if r.status_code != 200:
        asyncio.run_coroutine_threadsafe(
            result_channel.send(f"❌ メッセージ取得失敗: {r.status_code}"),
            loop,
        )
        return

    msg_content = r.json().get("content", "")

    # 転送先チャンネル取得
    r2 = requests.get(
        f"https://discord.com/api/v10/guilds/{dst_guild_id}/channels",
        headers=headers, timeout=10,
    )
    if r2.status_code != 200:
        asyncio.run_coroutine_threadsafe(
            result_channel.send(f"❌ サーバー取得失敗: {r2.status_code}"),
            loop,
        )
        return

    channels = [c for c in r2.json() if c["type"] == 0]
    success_total = 0

    def spam_channel(ch: dict):
        nonlocal success_total
        ch_id   = ch["id"]
        for i in range(count):
            try:
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
                if resp.status_code == 200:
                    success_total += 1
                elif resp.status_code == 429:
                    retry = resp.json().get("retry_after", 1.0)
                    time.sleep(float(retry))
                    continue
                elif resp.status_code in (401, 403):
                    return
            except Exception:
                pass
            time.sleep(delay)

    threads = []
    for ch in channels:
        t = threading.Thread(target=spam_channel, args=(ch,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    asyncio.run_coroutine_threadsafe(
        result_channel.send(
            f"✅ 完了 — {success_total}件転送成功\n"
            f"対象チャンネル数: {len(channels)}"
        ),
        loop,
    )


# ── Discord Bot ────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)


class SpamModal(discord.ui.Modal, title="転送スパム設定"):
    user_token = discord.ui.TextInput(
        label="ユーザートークン",
        placeholder="あなたのDiscordトークンを入力",
        style=discord.TextStyle.short,
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

        try:
            parts = self.settings.value.replace(" ", "").split("/")
            count = int(parts[0])
            delay = float(parts[1])
        except Exception:
            await interaction.followup.send(
                "❌ 設定の形式が違います。例: `10 / 0.5`", ephemeral=True
            )
            return

        r = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": self.user_token.value.strip()},
            timeout=10,
        )
        if r.status_code != 200:
            await interaction.followup.send("❌ トークンが無効です", ephemeral=True)
            return

        user = r.json()
        await interaction.followup.send(
            f"✅ トークン確認: `{user['username']}`\n⏳ スパム開始します...",
            ephemeral=True,
        )

        loop = asyncio.get_event_loop()
        t = threading.Thread(
            target=do_forward_spam,
            args=(
                self.user_token.value.strip(),
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
# Flaskを別スレッドで起動
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

bot.run(TOKEN)
