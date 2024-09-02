import discord
import os
import json
import time
from discord import app_commands
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth,SpotifyOauthError
from spotipy.exceptions import SpotifyException
load_dotenv('Spotify/User/.env')
user_tokens = {}
TOKENS_FILE = 'Spotify/User/token.json'

#トークン読み込み
if os.path.exists(TOKENS_FILE):
    try:
        with open(TOKENS_FILE, 'r') as f:
            user_tokens = json.load(f)
    except json.JSONDecodeError:
        user_tokens = {}

#トークンをファイルに保存する関数
def save_user_tokens():
    with open(TOKENS_FILE, 'w') as f:
        json.dump(user_tokens, f, indent=4)

#Discord設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
client = discord.Client(intents=intents, activity=discord.Game("Spotifyを再生中"))
tree = app_commands.CommandTree(client)

#Client,RedirectURI,TOKEN,SCOPE
SPOTIPY_CLIENT_ID = os.getenv('ClientID2')
SPOTIPY_CLIENT_SECRET = os.getenv('ClientSecret2')
SPOTIPY_REDIRECT_URI = 'http://xs492099.xsrv.jp/callback'
SCOPE = 'user-top-read'
TOKEN = os.getenv('SpotifyBotTOKEN')


#起動確認
@client.event
async def on_ready():
    await tree.sync()
    print(f'┎-------------------------------┒\n┃      login is successful      ┃\n┃    logged in {client.user}     ┃\n┖-------------------------------┚')


# Spotifyと連携するための認証コードを獲得するコマンド
@tree.command(name='link', description="Spotifyと連携するための認証コードを獲得します。")
async def link(interaction: discord.Interaction):
    sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                            client_secret=SPOTIPY_CLIENT_SECRET,
                            redirect_uri=SPOTIPY_REDIRECT_URI,
                            scope=SCOPE,
                            #トークンキャッシュ保存先
                            cache_path=f'Spotify/User/.cache-{interaction.user.id}')
    auth_url = sp_oauth.get_authorize_url()
    await interaction.response.send_message(f"認証用URL:\n {auth_url}\n\n認証後、/l1ogin コマンドで認証コードを入力してください。")


#Spotify認証コードを使用してログインするコマンド
@tree.command(name='login', description="Spotify認証コードを使用してログインします。")
async def login(interaction: discord.Interaction, code: str):
    sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                            client_secret=SPOTIPY_CLIENT_SECRET,
                            redirect_uri=SPOTIPY_REDIRECT_URI,
                            scope=SCOPE,
                            cache_path=f'Spotify/User/.cache-{interaction.user.id}')
    try:
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        if 'access_token' not in token_info:
            await interaction.response.send_message("トークンは無効です。\n再度試してください。")
            return

        #トークンの有効期限をチェック
        if is_token_expired(token_info['expires_at']):
            await interaction.response.send_message("既に無効です。\n再度試してください。")
            return

        #jsonファイルにUserID, tokenを保存
        user_tokens[str(interaction.user.id)] = {
            'access_token': token_info['access_token'],
            'refresh_token': token_info['refresh_token'],
            'expires_at': token_info['expires_at']
        }
        save_user_tokens()
        await interaction.response.send_message("Spotifyにログインしました。")
    except SpotifyOauthError as e:
        error_message = str(e)
        if "invalid_grant" in error_message:
            await interaction.response.send_message("認証コードが無効です。\n再度正しい認証コードを入力してください。")
        else:
            await interaction.response.send_message(f"Spotify APIエラーが発生しました:\n {e}")
    except Exception as e:
        await interaction.response.send_message(f"予期しないエラーが発生しました:\n {e}")
#トークンの有効期限をチェックする関数
def is_token_expired(expires_at):
    return time.time() > expires_at


# 直近1ヶ月で聞いた時間が長い曲を表示するコマンド
@tree.command(name='topsongs', description="直近1ヶ月で聞いた時間が長い曲を表示します。")
async def topsongs(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    #UserIDに対応するTokenがなかった場合
    if user_id not in user_tokens:
        await interaction.response.send_message("まず /login コマンドでSpotifyにログインしてください。")
        return
    token_info = user_tokens[user_id]
    #もしTokenが期限切れなら
    if is_token_expired(token_info['expires_at']):
        sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                client_secret=SPOTIPY_CLIENT_SECRET,
                                redirect_uri=SPOTIPY_REDIRECT_URI,
                                scope=SCOPE,
                                cache_path=f'Spotify/User/.cache-{interaction.user.id}')
        #refresh tokenでもう一度accesss tokenを入手
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            user_tokens[user_id] = {
                'access_token': token_info['access_token'],
                'refresh_token': token_info['refresh_token'],
                'expires_at': token_info['expires_at']
            }
            save_user_tokens()
        #refresh tokenでの入手ができなかった場合
        except SpotifyException as e:
            await interaction.response.send_message("トークンの再取得に失敗しました。再度 /login コマンドを実行してください。")
            return
    sp = Spotify(auth=user_tokens[user_id]['access_token'])
    #TopSongsを表示
    try:
        results = sp.current_user_top_tracks(limit=10, time_range='short_term')
        if results:
            top_tracks = "\n".join([f"{idx + 1}. {track['name']} by {track['artists'][0]['name']}" for idx, track in enumerate(results['items'])])
            await interaction.response.send_message(f"直近1ヶ月で聞いた時間が長い曲\n\n{top_tracks}")
        #TopSongsが見つからない場合
        else:
            await interaction.response.send_message("トップトラックが見つかりませんでした。")
    except SpotifyException as e:
        print(f"Spotify API エラー: {e}")
        print(f"HTTPステータス: {e.http_status}")
        print(f"理由: {e.reason}")
        print(f'エラー{token_info}')
        await interaction.response.send_message(f"Spotify APIエラーが発生しました: {e}")


#コマンドリストを表示するコマンド
@tree.command(name="help", description="コマンドリストを表示します。")
async def help_command(interaction: discord.Interaction):
    help_message = (
        "使い方\n"
        "STEP1 : 「/link」と入力し、URL先で認証コードを取得する。\n"
        "STEP2 : 「/login」と入力して、先ほど入手した認証コードを入力。\n"
        "＊一度ログインしたら基本再度ログインする必要はありません（例外あり）\n"
        "STEP3 : 「/topsongs」と入力すると、過去1ヶ月で聞いた時間が長い曲を10個表示される。\n\n"
        "問い合わせ先\n"
        "Discord tako._.v\n"
        "Twitter Tako_0522\n"
    )
    await interaction.response.send_message(help_message)


# Discordクライアントを起動
client.run(TOKEN)