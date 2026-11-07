# Python 3.10+ | pip install discord.py requests flask gunicorn audioop-lts
import os
import threading
import asyncio
import time
import random
import base64
import json
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

# ── フィンガープリント ─────────────────────────────────────────────
SUPER_PROPERTIES_LIST = [
    {
        "os": "Windows", "browser": "Chrome", "device": "",
        "system_locale": "ja",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "browser_version": "120.0.0.0", "os_version": "10",
        "referrer": "", "referring_domain": "",
        "referrer_current": "", "referring_domain_current": "",
        "release_channel": "stable", "client_build_number": 270406,
        "client_event_source": None,
    },
    {
        "os": "Mac OS X", "browser": "Chrome", "device": "",
        "system_locale": "ja",
        "browser_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "browser_version": "120.0.0.0", "os_version": "10.15.7",
        "referrer": "", "referring_domain": "",
        "referrer_current": "", "referring_domain_current": "",
        "release_channel": "stable", "client_build_number": 270406,
        "client_event_source": None,
    },
    {
        "os": "Windows", "browser": "Firefox", "device": "",
        "system_locale": "ja",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "browser_version": "121.0", "os_version": "10",
        "referrer": "", "referring_domain": "",
        "referrer_current": "", "referring_domain_current": "",
        "release_channel": "stable", "client_build_number": 270406,
        "client_event_source": None,
    },
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

def make_super_properties() -> str:
    props = random.choice(SUPER_PROPERTIES_LIST)
    return base64.b64encode(json.dumps(props).encode()).decode()

def make_headers(token: str, channel_id: str = None) -> dict:
    referer = (
        f"https://discord.com/channels/@me/{channel_id}"
        if channel_id else "https://discord.com/channels/@me"
    )
    return {
        "Authorization"        : token,
        "Content-Type"         : "application/json",
        "User-Agent"           : random.choice(USER_AGENTS),
        "X-Super-Properties"   : make_super_properties(),
        "X-Discord-Locale"     : "ja",
        "X-Discord-Timezone"   : "Asia/Tokyo",
        "X-Context-Properties" : "e30=",
        "Origin"               : "https://discord.com",
        "Referer"              : referer,
        "Accept"               : "*/*",
        "Accept-Language"      : "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding"      : "gzip, deflate, br",
        "Sec-Ch-Ua"            : '"Not_A Brand";v="8", "Chromium";v="120"',
        "Sec-Ch-Ua-Mobile"     : "?0",
        "Sec-Ch-Ua-Platform"   : '"Windows"',
        "Sec-Fetch-Dest"       : "empty",
        "Sec-Fetch-Mode"       : "cors",
        "Sec-Fetch-Site"       : "same-origin",
    }

# ── 無料プロキシ取得 ───────────────────────────────────────────────
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

proxy_pool: list[str] = []
proxy_lock = threading.Lock()

def fetch_proxies() -> list[str]:
    """複数ソースからプロキシを取得してプールに追加"""
    fetched = set()
    for url in PROXY_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    line = line.strip()
                    if line and ":" in line:
                        fetched.add(f"http://{line}")
        except Exception:
            pass
    return list(fetched)

def validate_proxy(proxy: str) -> bool:
    """プロキシがDiscordに繋がるか確認"""
    try:
        r = requests.get(
            "https://discord.com/api/v10/gateway",
            proxies={"http": proxy, "https": proxy},
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False

def refresh_proxy_pool(send_func=None):
    """プロキシプールを更新"""
    global proxy_pool
    if send_func:
        send_func("🔄 プロキシリスト取得中...")

    raw = fetch_proxies()
    if send_func:
        send_func(f"📋 {len(raw)}個取得 → 検証中...")

    # 並列で検証 (速度優先で最大50個チェック)
    sample    = random.sample(raw, min(50, len(raw)))
    valid     = []
    val_lock  = threading.Lock()

    def check(p):
        if validate_proxy(p):
            with val_lock:
                valid.append(p)

    threads = [threading.Thread(target=check, args=(p,), daemon=True) for p in sample]
    for t in threads: t.start()
    for t in threads: t.join()

    with proxy_lock:
        proxy_pool = valid

    if send_func:
        send_func(f"✅ 有効プロキシ: {len(valid)}個")

    return valid

def get_proxy() -> str | None:
    """プールからランダムにプロキシを取得"""
    with proxy_lock:
        if proxy_pool:
            return random.choice(proxy_pool)
    return None

def remove_proxy(proxy: str):
    """死んだプロキシをプールから削除"""
    with proxy_lock:
        if proxy in proxy_pool:
            proxy_pool.remove(proxy)


# ── セッション管理 ─────────────────────────────────────────────────
class TokenSession:
    def __init__(self, token: str):
        self.token    = token
        self.banned   = False
        self.username = ""
        self.session  = requests.Session()

    def _make_proxies(self) -> dict | None:
        p = get_proxy()
        return {"http": p, "https": p} if p else None

    def get(self, url: str) -> requests.Response:
        return self.session.get(
            url,
            headers=make_headers(self.token),
            proxies=self._make_proxies(),
            timeout=15,
        )

    def post(self, url: str, channel_id: str = None, **kwargs) -> requests.Response:
        proxies = self._make_proxies()
        try:
            return self.session.post(
                url,
                headers=make_headers(self.token, channel_id),
                proxies=proxies,
                timeout=15,
                **kwargs,
            )
        except requests.exceptions.ProxyError:
            if proxies:
                remove_proxy(proxies.get("http", ""))
            # プロキシなしでリトライ
            return self.session.post(
                url,
                headers=make_headers(self.token, channel_id),
                timeout=15,
                **kwargs,
            )

    def validate(self) -> bool:
        try:
            r = self.get("https://discord.com/api/v10/users/@me")
            if r.status_code == 200:
                self.username = r.json().get("username", "unknown")
                return True
        except Exception:
            pass
        return False


# ── 転送スパム本体 ──────────────────────────────────────────────────
def do_forward_spam(
    sessions: list[TokenSession],
    src_channel_id: str,
    src_message_id: str,
    dst_guild_id: str,
    count: int,
    delay_min: float,
    delay_max: float,
    result_channel,
    loop,
):
    def send(msg: str):
        asyncio.run_coroutine_threadsafe(
            result_channel.send(msg), loop
        )

    # 転送先チャンネル取得
    r = sessions[0].get(
        f"https://discord.com/api/v10/guilds/{dst_guild_id}/channels"
    )
    if r.status_code != 200:
        send(f"❌ サーバー取得失敗: {r.status_code}")
        return

    channels = [c for c in r.json() if c["type"] == 0]
    if not channels:
        send("❌ 転送先チャンネルが見つかりません")
        return

    send(
        f"🎯 転送先チャンネル数: {len(channels)}個\n"
        f"🔑 使用トークン数: {len(sessions)}個\n"
        f"🌐 プロキシプール: {len(proxy_pool)}個\n"
        f"⏳ スパム開始..."
    )

    success_total = 0
    lock      = threading.Lock()
    sess_idx  = 0
    sess_lock = threading.Lock()

    def next_session() -> TokenSession:
        nonlocal sess_idx
        with sess_lock:
            for _ in range(len(sessions)):
                s = sessions[sess_idx % len(sessions)]
                sess_idx += 1
                if not s.banned:
                    return s
            return sessions[0]

    def spam_channel(ch: dict):
        nonlocal success_total
        ch_id = ch["id"]

        for i in range(count):
            sess = next_session()
            try:
                payload = {
                    "message_reference": {
                        "type"      : 1,
                        "channel_id": src_channel_id,
                        "message_id": src_message_id,
                    },
                    "flags": 16384,
                }
                resp = sess.post(
                    f"https://discord.com/api/v10/channels/{ch_id}/messages",
                    channel_id=ch_id,
                    json=payload,
                )

                if resp.status_code in (200, 201):
                    with lock:
                        success_total += 1

                elif resp.status_code == 429:
                    data      = resp.json()
                    retry     = float(data.get("retry_after", 2.0))
                    is_global = data.get("global", False)
                    if is_global:
                        send(f"⚠️ グローバルレート制限 {retry:.1f}秒待機")
                    time.sleep(retry + random.uniform(0.5, 1.5))
                    continue

                elif resp.status_code == 403:
                    return

                elif resp.status_code == 401:
                    sess.banned = True
                    send(f"⚠️ トークンBAN: `{sess.username}`")
                    continue

            except Exception as e:
                print(f"エラー: {e}")

            time.sleep(random.uniform(delay_min, delay_max))

    threads = []
    for ch in channels:
        t = threading.Thread(target=spam_channel, args=(ch,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(random.uniform(0.1, 0.5))

    for t in threads:
        t.join()

    active = sum(1 for s in sessions if not s.banned)
    send(
        f"✅ 完了\n"
        f"転送成功: {success_total}件\n"
        f"対象チャンネル: {len(channels)}個\n"
        f"生存トークン: {active}/{len(sessions)}個\n"
        f"残プロキシ: {len(proxy_pool)}個"
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
        label="転送先サーバーID",
        placeholder="スパム先のサーバーID",
        style=discord.TextStyle.short,
        required=True,
    )
    settings = discord.ui.TextInput(
        label="最小間隔 / 最大間隔 / 回数 例: 2 / 8 / 10",
        placeholder="2 / 8 / 10",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        tokens = [
            t.strip()
            for t in self.user_tokens.value.strip().splitlines()
            if t.strip()
        ]
        if not tokens:
            await interaction.followup.send("❌ トークンを入力してください", ephemeral=True)
            return

        try:
            parts     = self.settings.value.replace(" ", "").split("/")
            delay_min = float(parts[0])
            delay_max = float(parts[1])
            count     = int(parts[2])
        except Exception:
            await interaction.followup.send(
                "❌ 設定の形式: `最小間隔 / 最大間隔 / 回数`\n例: `2 / 8 / 10`",
                ephemeral=True,
            )
            return

        dst_guild = self.dst_guild_id.value.strip()

        await interaction.followup.send(
            f"🔍 {len(tokens)}個のトークンを検証中...",
            ephemeral=True,
        )

        loop           = asyncio.get_event_loop()
        result_channel = interaction.channel

        def setup_and_run():
            # プロキシ取得
            refresh_proxy_pool(
                send_func=lambda m: asyncio.run_coroutine_threadsafe(
                    result_channel.send(m), loop
                )
            )

            # セッション作成 + 検証
            sessions = []
            for token in tokens:
                sess = TokenSession(token)
                if sess.validate():
                    sessions.append(sess)
                    asyncio.run_coroutine_threadsafe(
                        result_channel.send(f"✅ `{sess.username}`"),
                        loop,
                    )
                else:
                    asyncio.run_coroutine_threadsafe(
                        result_channel.send("❌ トークン無効: スキップ"),
                        loop,
                    )

            if not sessions:
                asyncio.run_coroutine_threadsafe(
                    result_channel.send("❌ 有効なトークンがありません"),
                    loop,
                )
                return

            do_forward_spam(
                sessions,
                self.src_channel_id.value.strip(),
                self.src_message_id.value.strip(),
                dst_guild,
                count,
                delay_min,
                delay_max,
                result_channel,
                loop,
            )

        t = threading.Thread(target=setup_and_run, daemon=True)
        t.start()


# ── スラッシュコマンド ─────────────────────────────────────────────
@bot.tree.command(name="spam", description="転送スパムを実行します")
@app_commands.checks.has_permissions(administrator=True)
async def spam_command(interaction: discord.Interaction):
    await interaction.response.send_modal(SpamModal())

@bot.tree.command(name="proxies", description="プロキシプールを更新します")
@app_commands.checks.has_permissions(administrator=True)
async def refresh_proxies(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    loop = asyncio.get_event_loop()
    ch   = interaction.channel

    def run():
        refresh_proxy_pool(
            send_func=lambda m: asyncio.run_coroutine_threadsafe(
                ch.send(m), loop
            )
        )

    await interaction.followup.send("🔄 プロキシ更新開始...")
    threading.Thread(target=run, daemon=True).start()


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")
    await bot.tree.sync()
    print("コマンド同期完了")
    # 起動時にプロキシを自動取得
    threading.Thread(target=refresh_proxy_pool, daemon=True).start()


# ── 起動 ───────────────────────────────────────────────────────────
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

bot.run(TOKEN)
