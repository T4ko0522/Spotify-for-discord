import discord
import os
import json
import time
from discord import app_commands
from discord import Embed
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError
from spotipy.exceptions import SpotifyException

load_dotenv('/Users/tako/VSCode/.env')
user_tokens = {}
TOKENS_FILE = '/Users/tako/VSCode/Project/Python/Spotify/users/token.json'  #なんかフルパスじゃないと動かん　なんでかはわからん

if os.path.exists(TOKENS_FILE):
    try:
        with open(TOKENS_FILE, 'r') as f:
            user_tokens = json.load(f)
    except json.JSONDecodeError:
        user_tokens = {}

def save_user_tokens():
    with open(TOKENS_FILE, 'w') as f:
        json.dump(user_tokens, f, indent=4)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
client = discord.Client(intents=intents, activity=discord.Game("Spotifyを再生中"))
tree = app_commands.CommandTree(client)

SPOTIPY_CLIENT_ID = os.getenv('ClientID')
SPOTIPY_CLIENT_SECRET = os.getenv('ClientSecret')
SPOTIPY_REDIRECT_URI = 'https://xs492099.xsrv.jp/callback.html'
SCOPE = 'user-top-read'
TOKEN = os.getenv('SpotifyBotTOKEN')

@client.event
async def on_ready():
    await tree.sync()
    print(f'login is successfullogged in {client.user}')

@tree.command(name='link', description="Spotifyと連携するための認証コードを獲得します。")
async def link(interaction: discord.Interaction):
    sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                            client_secret=SPOTIPY_CLIENT_SECRET,
                            redirect_uri=SPOTIPY_REDIRECT_URI,
                            scope=SCOPE,
                            cache_path=f'Spotify/User/.cache-{interaction.user.id}')
    auth_url = sp_oauth.get_authorize_url()

    embed = Embed(
        title="Spotify認証",
        description="以下のURLからSpotify認証を行ってください。",
        color=discord.Color.green()
    )
    embed.add_field(name="認証用URL", value=f"[ここをクリック]({auth_url})", inline=False)
    embed.set_footer(text="認証後、/login コマンドで認証コードを入力してください。")
    await interaction.response.send_message(embed=embed)

@tree.command(name='login', description="Spotify認証コードを使用してログインします。")
async def login(interaction: discord.Interaction, code: str):
    sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                            client_secret=SPOTIPY_CLIENT_SECRET,
                            redirect_uri=SPOTIPY_REDIRECT_URI,
                            scope=SCOPE,
                            cache_path=f'Spotify/User/.cache-{interaction.user.id}')
    try:
        token_info = sp_oauth.get_access_token(code)

        if 'access_token' not in token_info:
            embed = Embed(
                title="エラー",
                description="トークンは無効です。再度試してください。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return

        if is_token_expired(token_info['expires_at']):
            embed = Embed(
                title="エラー",
                description="トークンが既に無効です。再度試してください。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return

        user_tokens[str(interaction.user.id)] = {
            'access_token': token_info['access_token'],
            'refresh_token': token_info['refresh_token'],
            'expires_at': token_info['expires_at']
        }
        save_user_tokens()

        embed = Embed(
            title="ログイン成功",
            description="Spotifyにログインしました。",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    except SpotifyOauthError as e:
        error_message = str(e)
        if "invalid_grant" in error_message:
            embed = Embed(
                title="エラー",
                description="認証コードが無効です。再度正しい認証コードを入力してください。",
                color=discord.Color.red()
            )
        else:
            embed = Embed(
                title="Spotify APIエラー",
                description=f"Spotify APIエラーが発生しました:\n{e}",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        embed = Embed(
            title="予期しないエラー",
            description=f"予期しないエラーが発生しました:\n{e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

def is_token_expired(expires_at):
    return time.time() > expires_at

@tree.command(name='topsongs', description="直近1ヶ月で聞いた時間が長い曲を表示します。")
async def topsongs(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in user_tokens:
        embed = Embed(
            title="エラー",
            description="まず /login コマンドでSpotifyにログインしてください。",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    token_info = user_tokens[user_id]
    if is_token_expired(token_info['expires_at']):
        sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                client_secret=SPOTIPY_CLIENT_SECRET,
                                redirect_uri=SPOTIPY_REDIRECT_URI,
                                scope=SCOPE,
                                cache_path=f'Spotify/User/.cache-{interaction.user.id}')
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            user_tokens[user_id] = {
                'access_token': token_info['access_token'],
                'refresh_token': token_info['refresh_token'],
                'expires_at': token_info['expires_at']
            }
            save_user_tokens()
        except SpotifyException as e:
            embed = Embed(
                title="エラー",
                description="トークンの再取得に失敗しました。再度 /login コマンドを実行してください。",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return

    sp = Spotify(auth=user_tokens[user_id]['access_token'])
    try:
        results = sp.current_user_top_tracks(limit=10, time_range='short_term')
        if results:
            top_tracks = "\n".join([f"{idx + 1}. {track['name']} by {track['artists'][0]['name']}" for idx, track in enumerate(results['items'])])
            embed = Embed(
                title="トップトラック",
                description="直近1ヶ月で聞いた時間が長い曲10選",
                color=discord.Color.green()
            )
            embed.add_field(name="", value=top_tracks, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            embed = Embed(
                title="情報なし",
                description="トップトラックが見つかりませんでした。",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)

    except SpotifyException as e:
        embed = Embed(
            title="Spotify API エラー",
            description=f"Spotify APIエラーが発生しました:\n{e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@tree.command(name="help", description="コマンドリストを表示します。")
async def help_command(interaction: discord.Interaction):
    embed = Embed(
        title="Spotify Bot ヘルプ",
        description="Spotify Botの使い方です。",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="STEP 1",
        value="「/link」と入力し、URL先で認証コードを取得します。",
        inline=False
    )
    embed.add_field(
        name="STEP 2",
        value="「/login」と入力して、先ほど入手した認証コードを入力します。\n"
            "一度ログインしたら、再度ログインする必要は基本ありません（例外あり）。",
        inline=False
    )
    embed.add_field(
        name="STEP 3",
        value="「/topsongs」と入力すると、過去1ヶ月で聞いた時間が長い曲を10個表示されます。",
        inline=False
    )
    embed.add_field(
        name="問い合わせ先",
        value="[Twitter: @Tako_0522](https://x.com/Tako_0522)",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

client.run(TOKEN)
