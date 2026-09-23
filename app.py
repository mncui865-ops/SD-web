# -*- coding: utf-8 -*-
"""
============================================================
تطبيق خليك واضح - Khaleek Wadeh
النسخة النهائية v4.1 - بدون حظر/متابعين + قسم رسائلنا + إرسال صور
============================================================
"""

from flask import (Flask, render_template_string, request, jsonify,
                   redirect, url_for, session, flash, abort)
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlencode
import re
import secrets
import time
import os
import logging
import json
import urllib.request

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
security_logger = logging.getLogger('security')

# ============================================================
# App Config
# ============================================================
app = Flask(__name__)

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(64)
    print("=" * 60)
    print("⚠️  تحذير: SECRET_KEY غير معيّن!")
    print("   الجلسات ستُفقد عند كل إعادة تشغيل.")
    print("   عيّن: export SECRET_KEY='your-strong-random-string'")
    print("=" * 60)
app.config['SECRET_KEY'] = _secret

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # ✅ رُفع لـ 25MB لدعم 5 صور

GOOGLE_CLIENT_ID = os.environ.get(
    'GOOGLE_CLIENT_ID',
    '870538398049-roo4rg1nln3vf58ljqnabjho57uprbh7.apps.googleusercontent.com'
)
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET',
    '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'
)
GOOGLE_REDIRECT_URI = os.environ.get(
    'GOOGLE_REDIRECT_URI',
    'http://localhost:5000/auth/callback'
)

_pending_oauth_states = {}

# ============================================================
# Constants
# ============================================================
WHATSAPP_URL = "https://whatsapp.com/channel/0029Vb9J50vCnA7wAkrieW09"

AVATARS = {
    'male': 'https://api.dicebear.com/7.x/avataaars/svg?seed=male&backgroundColor=b6e3f4',
    'female': 'https://api.dicebear.com/7.x/avataaars/svg?seed=female&backgroundColor=ffd5dc',
    'default': 'https://api.dicebear.com/7.x/avataaars/svg?seed=default&backgroundColor=c0aede',
}

ALLOWED_AVATAR_PREFIXES = (
    'data:image/jpeg;base64,',
    'data:image/png;base64,',
    'data:image/webp;base64,',
    'data:image/gif;base64,',
)
ALLOWED_AVATAR_URLS = set(AVATARS.values())

NICKNAME_PRESETS = [
    '🌟 نجم', '🔥 مشتعل', '💎 ماسي', '🦅 صقر', '🐉 تنين',
    '🌙 قمر', '⚡ برق', '🎯 دقيق', '🦁 أسد', '🐺 ذئب',
    '🌊 موج', '🌸 زهرة', '🦋 فراشة', '👑 ملك', '🎨 فنان',
    '🚀 صاروخ', '🛡️ درع', '🗡️ سيف', '🌞 شمس', '❄️ ثلج',
]

# ============================================================
# Databases
# ============================================================
users_db = {}
messages_db = {}
ids_db = {}
email_to_user = []
site_stats = {'visits': 0, 'started_at': datetime.now().isoformat()}

# ✅ الصور الافتراضية (6 صور)
gallery_db = [
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/uy4w7e.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#b95cff',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/53vqty.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#4d96ff',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/9wgs27.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#ff9a3c',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/7d1hud.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#22c55e',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/334h70.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#ec4899',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
    {
        'id': secrets.token_hex(6),
        'image': 'https://files.catbox.moe/uyibsf.png',
        'link': '',
        'title': 'خليك واضح',
        'platform': 'رابط',
        'icon_key': '',
        'color': '#14b8a6',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    },
]

_rate_buckets = {}


def rate_limit(key, max_calls=10, window=60):
    now = time.time()
    bucket = _rate_buckets.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True


# ============================================================
# Validators
# ============================================================
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
NAME_RE = re.compile(r'^[\w\s\u0600-\u06FF\.\-\']{1,40}$', re.UNICODE)
NICKNAME_RE = re.compile(
    r'^[\w\s\u0600-\u06FF\.\-\'\u2600-\u27BF\U0001F300-\U0001F9FF]{1,20}$',
    re.UNICODE
)
SLUG_RE = re.compile(r'^[a-zA-Z0-9_\-]{3,30}$')
SAFE_MSG_RE = re.compile(r'^[^\x00-\x08\x0b\x0c\x0e-\x1f]+$')


def hash_password(p):
    return generate_password_hash(p, method='pbkdf2:sha256:260000', salt_length=16)


def verify_password(stored, provided):
    try:
        return check_password_hash(stored, provided)
    except Exception:
        return False


def generate_unique_id():
    for _ in range(20):
        new_id = ''.join(str(secrets.randbelow(10)) for _ in range(8))
        if new_id not in ids_db:
            return new_id
    raise RuntimeError("cannot generate id")


def validate_username(u):
    return bool(u and USERNAME_RE.match(u))


def validate_name(n):
    if not n:
        return False
    n = n.strip()
    if not (1 <= len(n) <= 40):
        return False
    return bool(NAME_RE.match(n))


def validate_nickname(n):
    if not n:
        return True
    n = n.strip()
    if not (1 <= len(n) <= 20):
        return False
    return bool(NICKNAME_RE.match(n))


def validate_slug(s):
    if not s:
        return False
    return bool(SLUG_RE.match(s))


def sanitize_text(text, max_len=1000):
    if not text:
        return ''
    text = text.strip()
    if not SAFE_MSG_RE.match(text):
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text[:max_len]


def is_valid_avatar(avatar):
    if not avatar:
        return False
    if avatar in ALLOWED_AVATAR_URLS:
        return True
    if avatar.startswith(ALLOWED_AVATAR_PREFIXES):
        if len(avatar) > 5_500_000:
            return False
        return True
    if avatar.startswith('https://') or avatar.startswith('http://'):
        if len(avatar) > 500:
            return False
        return True
    return False


def validate_image_data_uri(data_uri):
    if not data_uri:
        return ''
    if not data_uri.startswith('data:image/'):
        return ''
    if not any(data_uri.startswith(p) for p in ALLOWED_AVATAR_PREFIXES):
        return ''
    if len(data_uri) > 5_500_000:
        return ''
    return data_uri


# ✅ دالة التحقق من صور الرسالة (حتى 5 صور)
def validate_message_images(images_list):
    if not images_list or not isinstance(images_list, list):
        return []
    if len(images_list) > 5:
        images_list = images_list[:5]
    allowed = (
        'data:image/jpeg;base64,',
        'data:image/png;base64,',
        'data:image/webp;base64,',
        'data:image/gif;base64,',
    )
    valid = []
    for img in images_list:
        if not img or not isinstance(img, str):
            continue
        if not img.startswith('data:image/'):
            continue
        if not any(img.startswith(p) for p in allowed):
            continue
        if len(img) > 3_500_000:
            continue
        valid.append(img)
    return valid


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_username' not in session:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return wrapper


def get_user_avatar(user):
    av = user.get('avatar') if user else None
    if av and is_valid_avatar(av):
        return av
    if user and user.get('gender') == 'female':
        return AVATARS['female']
    if user and user.get('gender') == 'male':
        return AVATARS['male']
    return AVATARS['default']


def client_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()[:45]
    return (request.remote_addr or 'unknown')[:45]


# ============================================================
# Accounts helpers
# ============================================================
def get_saved_accounts():
    return list(session.get('saved_accounts', []))


def add_saved_account(username):
    session['saved_accounts'] = [username]


def remove_saved_account(username):
    accounts = get_saved_accounts()
    if username in accounts:
        accounts.remove(username)
        session['saved_accounts'] = accounts


def switch_account(username):
    if username in get_saved_accounts() and username in users_db:
        user = users_db[username]
        session['user_username'] = username
        session['user_name'] = user['name']
        session['user_id'] = user['id']
        session['user_avatar'] = get_user_avatar(user)
        add_saved_account(username)
        return True
    return False


def load_saved_accounts_data():
    accounts = []
    for u in get_saved_accounts():
        if u in users_db:
            user = users_db[u]
            accounts.append({
                'username': u,
                'name': user['name'],
                'avatar': get_user_avatar(user),
                'id': user['id'],
                'is_current': u == session.get('user_username'),
            })
    return accounts


# ============================================================
# Platform detection
# ============================================================
PLATFORMS = [
    ('whatsapp.com', 'واتساب', 'wa', '#25D366'),
    ('wa.me', 'واتساب', 'wa', '#25D366'),
    ('chat.whatsapp.com', 'واتساب', 'wa', '#25D366'),
    ('facebook.com', 'فيسبوك', 'fb', '#1877F2'),
    ('fb.com', 'فيسبوك', 'fb', '#1877F2'),
    ('fb.watch', 'فيسبوك', 'fb', '#1877F2'),
    ('twitter.com', 'تويتر', 'tw', '#1DA1F2'),
    ('x.com', 'منصة X', 'tw', '#000000'),
    ('instagram.com', 'إنستغرام', 'ig', '#E4405F'),
    ('t.me', 'تيليجرام', 'tg', '#0088cc'),
    ('telegram.me', 'تيليجرام', 'tg', '#0088cc'),
    ('youtube.com', 'يوتيوب', 'yt', '#FF0000'),
    ('youtu.be', 'يوتيوب', 'yt', '#FF0000'),
    ('tiktok.com', 'تيك توك', 'tt', '#000000'),
    ('snapchat.com', 'سناب شات', 'sc', '#FFFC00'),
    ('linkedin.com', 'لينكدإن', 'li', '#0A66C2'),
    ('github.com', 'جيت هب', 'gh', '#181717'),
    ('discord.gg', 'ديسكورد', 'dc', '#5865F2'),
    ('discord.com', 'ديسكورد', 'dc', '#5865F2'),
    ('pinterest.com', 'بينترست', 'pin', '#BD081C'),
    ('reddit.com', 'ريديت', 'rd', '#FF4500'),
    ('threads.net', 'ثريدز', 'th', '#000000'),
]

PLATFORM_SVGS = {
    'wa': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
    'fb': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    'tw': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    'ig': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>',
    'tg': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
    'yt': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>',
    'tt': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>',
    'sc': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.206.793c.99 0 4.347.276 5.93 3.821.529 1.193.403 3.219.299 4.847l-.003.06c-.012.18-.022.345-.03.51.075.045.203.09.401.09.3-.016.659-.12 1.033-.301.165-.088.344-.104.464-.104.182 0 .359.029.509.09.45.149.734.479.734.838.015.449-.39.839-1.213 1.168-.089.029-.209.075-.344.119-.45.135-1.139.36-1.333.81-.09.224-.061.524.12.868l.015.015c.06.136 1.526 3.475 4.791 4.014.255.044.435.27.42.509 0 .075-.015.149-.045.225-.24.569-1.273.988-3.146 1.271-.059.091-.12.375-.164.57-.029.179-.074.36-.134.553-.076.271-.27.405-.555.405h-.03c-.135 0-.313-.031-.538-.074-.36-.075-.765-.135-1.273-.135-.3 0-.599.015-.913.074-.6.104-1.123.464-1.723.884-.853.599-1.826 1.288-3.294 1.288-.06 0-.119-.015-.18-.015h-.149c-1.468 0-2.427-.675-3.279-1.288-.599-.42-1.107-.779-1.707-.884-.314-.045-.629-.074-.928-.074-.54 0-.958.089-1.272.149-.211.043-.391.074-.54.074-.374 0-.523-.224-.583-.42-.061-.192-.09-.389-.135-.567-.046-.181-.105-.494-.166-.57-1.918-.222-2.95-.642-3.189-1.226-.031-.063-.052-.15-.055-.225-.015-.243.165-.465.42-.509 3.264-.54 4.73-3.879 4.791-4.02l.016-.029c.18-.345.224-.645.119-.869-.195-.434-.884-.658-1.332-.809-.121-.029-.24-.074-.346-.119-1.107-.435-1.257-.93-1.197-1.273.09-.479.674-.793 1.168-.793.146 0 .27.029.383.074.42.194.789.3 1.104.3.234 0 .384-.06.465-.105l-.046-.569c-.098-1.626-.225-3.651.307-4.837C7.392 1.077 10.739.807 11.727.807l.419-.015h.06z"/></svg>',
    'li': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    'gh': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>',
    'dc': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>',
    'pin': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.373 0 0 5.372 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z"/></svg>',
    'rd': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0z"/></svg>',
    'th': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.75-1.757-.513-.586-1.308-.883-2.359-.89h-.029c-.844 0-1.992.232-2.721 1.32L7.734 7.847c.98-1.454 2.568-2.256 4.478-2.256h.044c3.194.02 5.097 1.975 5.287 5.388.108.046.216.094.321.142 1.49.7 2.58 1.761 3.154 3.07.797 1.82.871 4.79-1.548 7.158-1.85 1.81-4.094 2.628-7.277 2.65Zm1.003-11.69c-.242 0-.487.007-.739.021-1.836.103-2.98.946-2.916 2.143.067 1.256 1.452 1.839 2.784 1.767 1.224-.065 2.818-.543 3.086-3.71a10.5 10.5 0 0 0-2.215-.221z"/></svg>',
}

# ============================================================
# Icons
# ============================================================
APP_ICONS = {
    'home': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    'messages': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    'public_messages': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    'edit': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    'logout': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
    'accounts': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'user': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    'help': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    'copy': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    'privacy': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    'shield': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
    'users': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'reply': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/></svg>',
    'link': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    'send': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    'stats': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    'camera': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>',
    'inbox': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
    'globe': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    'star': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    'star-filled': '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    'heart': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    'check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    'lock': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    'plus': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    'settings': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    'trash': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
    'upload': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    'image': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
    'sparkle': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0l2.245 7.755L22 10l-7.755 2.245L12 20l-2.245-7.755L2 10l7.755-2.245L12 0z"/></svg>',
    'eye': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    'eye-off': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
    'calendar': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    'id': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><path d="M14 9h4"/><path d="M14 13h4"/><path d="M6 17c0-1.5 1-2 2-2s2 .5 2 2"/></svg>',
    'share': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>',
    'arrow-left': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>',
    'images': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M21 15V7a2 2 0 0 0-2-2h-8"/><circle cx="8" cy="8" r="1.5"/><polyline points="17 13 13 9 5 17"/></svg>',
}


def detect_platform(url):
    if not url:
        return {'name': 'رابط', 'icon': '', 'color': '#6b7280', 'key': ''}
    u = url.lower()
    for key, name, icon_key, color in PLATFORMS:
        if key in u:
            return {
                'name': name,
                'icon': PLATFORM_SVGS.get(icon_key, ''),
                'color': color,
                'key': icon_key,
            }
    return {'name': 'رابط', 'icon': '', 'color': '#6b7280', 'key': ''}


# ============================================================
# Security
# ============================================================
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf():
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        if request.path == '/auth/callback':
            return True
        token = (request.form.get('_csrf_token') or
                 request.headers.get('X-CSRF-Token'))
        if not token:
            return False
        if not secrets.compare_digest(token, session.get('_csrf_token', '')):
            return False
    return True


@app.before_request
def security_gate():
    if request.path == '/' and request.method == 'GET':
        site_stats['visits'] = site_stats.get('visits', 0) + 1

    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        if not validate_csrf():
            if request.is_json:
                return jsonify({'status': 'error', 'message': 'CSRF token مفقود'}), 403
            flash('طلب مرفوض', 'error')
            return redirect(url_for('index'))

    if '..' in request.path or '%2e%2e' in request.path.lower():
        abort(404)


@app.context_processor
def inject_globals():
    accounts = load_saved_accounts_data() if session.get('user_username') else []
    return {
        'whatsapp_url': WHATSAPP_URL,
        'avatars': AVATARS,
        'csrf_token': generate_csrf_token,
        'saved_accounts': accounts,
        'current_user': session.get('user_username'),
        'site_stats': site_stats,
        'total_users': len(users_db),
        'total_messages': sum(len(v) for v in messages_db.values()),
        'icons': APP_ICONS,
        'nickname_presets': NICKNAME_PRESETS,
    }


# ============================================================
# BASE TEMPLATE
# ============================================================
BASE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title or 'خليك واضح' }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { min-height: 100vh; background: linear-gradient(180deg, #f0f4f8 0%, #e8eef5 100%); background-attachment: fixed; color: #2d2f31; }
        body { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; line-height: 1.7; display: flex; flex-direction: column; }
        a { color: #b95cff; text-decoration: none; transition: 0.2s; font-weight: 500; }
        a:hover { color: #8b2fc9; text-decoration: underline; }

        .navbar { background: #fff; box-shadow: 0 2px 12px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #eef0f4; }
        .nav-container { max-width: 1200px; margin: 0 auto; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
        .nav-brand { font-weight: 800; color: #2d2f31; font-size: 17px; display: flex; align-items: center; gap: 6px; }
        .nav-brand svg { width: 22px; height: 22px; color: #f59e0b; }
        .nav-brand span { background: linear-gradient(90deg, #ff5757, #ff9a3c, #ffd93d, #6bcb77, #4d96ff, #b95cff, #ff5757); background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: rainbowSlide 4s linear infinite; }
        .nav-menu { list-style: none; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .nav-menu a { display: inline-flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 22px; font-size: 13.5px; font-weight: 700; color: #fff !important; text-decoration: none !important; transition: 0.25s; border: 0; box-shadow: 0 3px 10px rgba(0,0,0,0.12); white-space: nowrap; }
        .nav-menu a:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,0.22); }
        .nav-menu a svg { width: 16px; height: 16px; flex-shrink: 0; }

        .nav-btn-home   { background: linear-gradient(135deg, #4d96ff, #2c72e0); }
        .nav-btn-msgs   { background: linear-gradient(135deg, #ff9a3c, #e07b1a); }
        .nav-btn-public { background: linear-gradient(135deg, #14b8a6, #0d9488); }
        .nav-btn-edit   { background: linear-gradient(135deg, #22c55e, #16a34a); }
        .nav-btn-out    { background: linear-gradient(135deg, #6b7280, #4b5563); }
        .nav-btn-user   { background: linear-gradient(135deg, #ec4899, #be185d); }
        .nav-btn-acct   { background: linear-gradient(135deg, #6366f1, #4338ca); }
        .nav-btn-help   { background: linear-gradient(135deg, #14b8a6, #0d9488); }
        .nav-btn-nick   { background: linear-gradient(135deg, #f59e0b, #d97706); }
        .nav-btn-members{ background: linear-gradient(135deg, #8b5cf6, #7c3aed); }

        .nav-google-btn {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 9px 18px; border-radius: 22px;
            background: #fff; border: 2px solid #dadce0;
            font-size: 13.5px; font-weight: 700; color: #3c4043 !important;
            text-decoration: none !important; transition: all 0.25s;
            box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        }
        .nav-google-btn:hover {
            transform: translateY(-2px); border-color: #b95cff;
            box-shadow: 0 6px 18px rgba(185,92,255,0.28);
            color: #3c4043 !important; text-decoration: none !important;
        }
        .nav-google-btn svg { width: 18px; height: 18px; flex-shrink: 0; }

        .nav-toggle { display: none; }
        .nav-toggle-label { display: none; cursor: pointer; flex-direction: column; gap: 4px; }
        .nav-toggle-label span { width: 24px; height: 2px; background: #333; border-radius: 2px; }
        .user-badge img { width: 22px; height: 22px; border-radius: 50%; object-fit: cover; }
        .user-badge .uid { background: rgba(255,255,255,0.25); padding: 1px 6px; border-radius: 8px; font-weight: 700; font-size: 11px; direction: ltr; font-family: monospace; }

        .flash-messages { max-width: 1200px; margin: 12px auto 0; padding: 0 20px; }
        .flash { padding: 12px 16px; border-radius: 10px; margin-bottom: 8px; font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 8px; }
        .flash-success { background: #e6f9ee; color: #0d3d1f; border-right: 4px solid #22a04d; }
        .flash-warning { background: #fff6e0; color: #5c4000; border-right: 4px solid #f5a623; }
        .flash-error   { background: #fdecec; color: #5c0f0f; border-right: 4px solid #e64a4a; }

        main { flex: 1; padding-bottom: 40px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }

        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 26px; border-radius: 12px; font-size: 15px; font-weight: 700; cursor: pointer; border: 0; transition: 0.25s; text-decoration: none; text-align: center; }
        .btn svg { width: 18px; height: 18px; }
        .btn-blue { background: linear-gradient(135deg, #4d96ff, #2c72e0); color: #fff; box-shadow: 0 4px 14px rgba(77,150,255,0.35); }
        .btn-blue:hover { box-shadow: 0 6px 20px rgba(77,150,255,0.5); transform: translateY(-2px); color: #fff; text-decoration: none; }
        .btn-berry { background: linear-gradient(135deg, #b95cff, #8b2fc9); color: #fff; box-shadow: 0 4px 14px rgba(185,92,255,0.35); }
        .btn-berry:hover { box-shadow: 0 6px 20px rgba(185,92,255,0.5); transform: translateY(-2px); color: #fff; text-decoration: none; }
        .btn-primary { background: linear-gradient(135deg, #ff5757, #b95cff); color: #fff; box-shadow: 0 4px 14px rgba(185,92,255,0.35); }
        .btn-primary:hover { box-shadow: 0 6px 20px rgba(255,87,87,0.5); transform: translateY(-2px); color: #fff; text-decoration: none; }
        .btn-secondary { background: #fff; color: #2d2f31; border: 2px solid #e0e4ec; }
        .btn-secondary:hover { background: #fafbfd; color: #2d2f31; text-decoration: none; }
        .btn-dark { background: #2d2f31; color: #fff; }
        .btn-dark:hover { background: #1a1c1e; color: #fff; text-decoration: none; }
        .btn-green { background: #25D366; color: #fff; }
        .btn-green:hover { background: #1da851; color: #fff; text-decoration: none; }
        .btn-red { background: linear-gradient(135deg, #e74c3c, #c0392b); color: #fff; }
        .btn-red:hover { background: linear-gradient(135deg, #c0392b, #a93226); color: #fff; text-decoration: none; }
        .btn-block { width: 100%; }
        .btn-sm { padding: 8px 16px; font-size: 13px; border-radius: 8px; }
        .btn-gold { background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; box-shadow: 0 4px 14px rgba(245,158,11,0.35); }
        .btn-gold:hover { box-shadow: 0 6px 20px rgba(245,158,11,0.5); transform: translateY(-2px); color: #fff; text-decoration: none; }
        .btn-teal { background: linear-gradient(135deg, #14b8a6, #0d9488); color: #fff; box-shadow: 0 4px 14px rgba(20,184,166,0.35); }
        .btn-teal:hover { box-shadow: 0 6px 20px rgba(20,184,166,0.5); transform: translateY(-2px); color: #fff; text-decoration: none; }

        .google-btn {
            display: flex; align-items: center; justify-content: center; gap: 12px;
            width: 100%; padding: 14px 18px; background: #fff;
            border: 2px solid #dadce0; border-radius: 14px;
            font-size: 15px; font-weight: 700; color: #3c4043;
            cursor: pointer; transition: all 0.25s; text-decoration: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06); font-family: inherit;
        }
        .google-btn:hover {
            background: #f8f9fa; border-color: #b95cff;
            box-shadow: 0 6px 20px rgba(185,92,255,0.25);
            text-decoration: none; color: #3c4043; transform: translateY(-2px);
        }
        .google-btn svg { flex-shrink: 0; }

        .gallery { display: flex; flex-direction: column; gap: 80px; max-width: 700px; margin: 0 auto; padding: 20px 0; }
        .gallery-item-wrap { position: relative; border-radius: 24px; background: #fff; padding: 16px; box-shadow: 0 12px 40px rgba(0,0,0,0.12); transition: 0.4s; }
        .gallery-item-wrap::before, .gallery-item-wrap::after {
            content: ''; position: absolute; top: 0; bottom: 0; width: 16px;
            background-image: radial-gradient(circle, #ff5757 2.5px, transparent 3px), radial-gradient(circle, #ff9a3c 2.5px, transparent 3px), radial-gradient(circle, #ffd93d 2.5px, transparent 3px), radial-gradient(circle, #6bcb77 2.5px, transparent 3px), radial-gradient(circle, #4d96ff 2.5px, transparent 3px), radial-gradient(circle, #b95cff 2.5px, transparent 3px);
            background-size: 16px 16px; background-position: 0 0, 0 8px, 8px 0, 8px 8px, 0 0, 8px 8px; background-repeat: repeat-y; pointer-events: none; border-radius: 24px;
        }
        .gallery-item-wrap::before { left: -2px; }
        .gallery-item-wrap::after { right: -2px; }
        .gallery-item-wrap:hover { transform: translateY(-6px); box-shadow: 0 18px 54px rgba(185,92,255,0.28); }
        .gallery-inner { background: #fff; border-radius: 16px; padding: 8px; position: relative; z-index: 1; margin: 0 10px; }
        .gallery-item { position: relative; border-radius: 12px; overflow: hidden; cursor: pointer; background: #f3f4f6; }
        .gallery-item img { width: 100%; height: auto; display: block; transition: 0.6s; }
        .gallery-item:hover img { transform: scale(1.02); }
        .gallery-link-btn {
            display: flex; align-items: center; justify-content: center; gap: 10px;
            margin-top: 12px; padding: 13px 20px; border-radius: 12px;
            color: #fff !important; font-weight: 700; font-size: 15px;
            text-decoration: none !important; transition: all 0.25s;
            box-shadow: 0 4px 14px rgba(0,0,0,0.15); border: 0;
        }
        .gallery-link-btn:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.28); filter: brightness(1.08); color: #fff !important; }
        .gallery-link-btn svg { width: 22px; height: 22px; fill: #fff; flex-shrink: 0; }

        .lightbox { display: none; position: fixed; inset: 0; z-index: 9999; background: rgba(5, 8, 20, 0.94); backdrop-filter: blur(20px); align-items: center; justify-content: center; padding: 30px; cursor: zoom-out; }
        .lightbox.active { display: flex; }
        .lightbox img { max-width: 95vw; max-height: 90vh; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.7); cursor: default; }
        .lightbox .close-lb {
            position: absolute;
            top: 20px;
            right: 20px;
            left: auto;
            background: rgba(255,255,255,0.15);
            border: 0;
            color: #fff;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            font-size: 26px;
            font-weight: 300;
            line-height: 1;
            cursor: pointer;
            transition: 0.25s;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .lightbox .close-lb:hover {
            background: rgba(231, 76, 60, 0.85);
            transform: scale(1.1) rotate(90deg);
        }

        .form-wrapper { max-width: 500px; margin: 40px auto; background: #fff; border: 1px solid #eef0f4; padding: 32px; border-radius: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.06); }
        .form-title { text-align: center; font-size: 26px; margin-bottom: 8px; font-weight: 700; color: #2d2f31; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .form-title svg { width: 24px; height: 24px; stroke: #b95cff; }
        .form-sub { text-align: center; color: #888; font-size: 13px; margin-bottom: 24px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 14px; margin-bottom: 6px; color: #555; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .form-group label svg { width: 14px; height: 14px; stroke: #b95cff; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 12px 14px; border: 1px solid #dfe3ec; border-radius: 12px; font-size: 15px; outline: none; transition: 0.2s; font-family: inherit; background: #fafbfd; color: #2d2f31; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: #b95cff; background: #fff; box-shadow: 0 0 0 3px rgba(185,92,255,0.12); }
        .form-group textarea { resize: vertical; min-height: 80px; }

        .file-upload { display: flex; align-items: center; gap: 12px; padding: 14px; background: #fafbfd; border: 2px dashed rgba(185,92,255,0.4); border-radius: 14px; cursor: pointer; transition: 0.2s; }
        .file-upload:hover { border-color: #b95cff; background: #f9f5ff; }
        .file-upload input[type="file"] { display: none; }
        .file-upload .upload-icon { width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #ff5757, #b95cff); display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
        .file-upload .upload-icon svg { width: 22px; height: 22px; stroke: #fff; }
        .file-upload .upload-text { font-size: 14px; color: #555; }
        .file-upload .upload-text b { display: block; color: #2d2f31; }
        .file-upload .upload-text small { color: #999; font-size: 12px; }

        .avatar-picker { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; padding: 16px; background: #fafbfd; border-radius: 14px; border: 1px solid #eef0f4; flex-wrap: wrap; }
        .avatar-picker > img { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; background: #eee; border: 3px solid #fff; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }
        .avatar-picker .avatar-options { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .avatar-picker .avatar-options img { width: 46px; height: 46px; cursor: pointer; border: 2px solid transparent; transition: 0.2s; border-radius: 50%; }
        .avatar-picker .avatar-options img:hover { border-color: #b95cff; }
        .avatar-picker .avatar-options img.selected { border-color: #b95cff; box-shadow: 0 0 12px rgba(185,92,255,0.4); }

        .alert { padding: 12px 14px; border-radius: 10px; font-size: 14px; margin-bottom: 14px; display: none; }
        .alert.show { display: block; }
        .alert-warning { background: #fff6e0; color: #5c4000; border: 1px solid #f5d78e; }
        .alert-error   { background: #fdecec; color: #5c0f0f; border: 1px solid #f5b8b8; }
        .alert-success { background: #e6f9ee; color: #0d3d1f; border: 1px solid #a9e6bf; }

        .id-box { background: linear-gradient(135deg, rgba(255,87,87,0.15), rgba(185,92,255,0.15)); border: 1px solid rgba(185,92,255,0.2); padding: 22px; border-radius: 18px; text-align: center; margin-bottom: 20px; position: relative; }
        .id-box h3 { font-size: 14px; margin-bottom: 8px; color: #666; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .id-box h3 svg { width: 16px; height: 16px; stroke: #b95cff; }
        .id-box .id-value { font-size: 34px; font-weight: 800; letter-spacing: 6px; direction: ltr; font-family: 'Courier New', monospace; color: #b95cff; }
        .id-box .id-hint { font-size: 12px; margin-top: 8px; color: #888; }
        .id-box .copy-id-btn { position: absolute; top: 12px; left: 12px; background: #fff; border: 1px solid #eef0f4; color: #b95cff; padding: 6px 12px; border-radius: 8px; font-size: 12px; cursor: pointer; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; }
        .id-box .copy-id-btn svg { width: 14px; height: 14px; }

        .profile-header { background: #fff; border: 1px solid #eef0f4; border-radius: 20px; padding: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.06); text-align: center; margin-bottom: 20px; }
        .profile-header .avatar { width: 130px; height: 130px; border-radius: 50%; object-fit: cover; background: #eee; border: 5px solid #fff; box-shadow: 0 8px 24px rgba(0,0,0,0.12); margin-bottom: 14px; cursor: zoom-in; transition: 0.2s; }
        .profile-header .avatar:hover { transform: scale(1.05); box-shadow: 0 12px 32px rgba(185,92,255,0.3); }
        .profile-header h2 { font-size: 26px; margin-bottom: 4px; font-weight: 700; color: #2d2f31; }
        .profile-header .username { color: #888; font-size: 14px; direction: ltr; font-family: monospace; }
        .profile-header .nickname-badge { display: inline-flex; align-items: center; gap: 4px; margin-top: 8px; padding: 5px 14px; border-radius: 20px; background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.15)); color: #d97706; font-size: 13px; font-weight: 700; border: 1px solid rgba(245,158,11,0.3); }
        .profile-header .nickname-badge svg { width: 14px; height: 14px; fill: #d97706; }
        .profile-actions { display: flex; gap: 10px; justify-content: center; margin-top: 18px; flex-wrap: wrap; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: #fff; border: 1px solid #eef0f4; padding: 18px; border-radius: 16px; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.04); }
        .stat-card .num { font-size: 26px; font-weight: 800; background: linear-gradient(135deg, #ff5757, #b95cff); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-card .lbl { font-size: 13px; color: #888; margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 4px; }
        .stat-card .lbl svg { width: 14px; height: 14px; stroke: #888; }

        .info-row { display: flex; justify-content: space-between; padding: 12px 16px; background: #fafbfd; border-radius: 10px; margin-bottom: 8px; font-size: 14px; align-items: center; }
        .info-row .info-label { color: #888; font-weight: 500; display: flex; align-items: center; gap: 6px; }
        .info-row .info-label svg { width: 14px; height: 14px; stroke: #b95cff; }
        .info-row .info-value { color: #2d2f31; font-weight: 600; }

        .msg-card { background: #fff; border: 1px solid #eef0f4; border-radius: 16px; padding: 18px 20px; margin-bottom: 14px; border-right: 4px solid #b95cff; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
        .msg-card .msg-content { font-size: 15px; margin-bottom: 10px; color: #2d2f31; white-space: pre-wrap; word-break: break-word; }
        .msg-card .msg-meta { font-size: 12px; color: #999; margin-bottom: 10px; display: flex; align-items: center; gap: 4px; }
        .msg-card .msg-meta svg { width: 12px; height: 12px; stroke: #999; }
        .msg-reply { background: #e6f9ee; border-radius: 10px; padding: 10px 12px; font-size: 14px; margin-top: 10px; border-right: 3px solid #22a04d; color: #0d3d1f; white-space: pre-wrap; word-break: break-word; display: flex; align-items: flex-start; gap: 6px; }
        .msg-reply svg { width: 14px; height: 14px; stroke: #22a04d; flex-shrink: 0; margin-top: 3px; }
        .reply-form { display: flex; gap: 8px; margin-top: 10px; }
        .reply-form input { flex: 1; padding: 10px 12px; border: 1px solid #dfe3ec; border-radius: 10px; font-size: 14px; outline: none; background: #fafbfd; color: #2d2f31; }
        .reply-form input:focus { border-color: #b95cff; background: #fff; }
        .reply-form button { padding: 10px 18px; background: linear-gradient(135deg, #ff5757, #b95cff); color: #fff; border: 0; border-radius: 10px; cursor: pointer; font-weight: 700; display: inline-flex; align-items: center; gap: 6px; }
        .reply-form button svg { width: 14px; height: 14px; }

        .share-box { background: #fff; border: 1px solid #eef0f4; padding: 22px; border-radius: 18px; margin-bottom: 20px; box-shadow: 0 4px 14px rgba(0,0,0,0.04); }
        .share-box h3 { margin-bottom: 10px; font-size: 17px; font-weight: 700; color: #2d2f31; display: inline-flex; align-items: center; gap: 8px; }
        .share-box h3 svg { width: 18px; height: 18px; stroke: #b95cff; }
        .share-box p { color: #888; }
        .share-row { display: flex; gap: 8px; margin-top: 10px; }
        .share-row input { flex: 1; padding: 12px; border: 1px solid #dfe3ec; border-radius: 10px; font-size: 14px; text-align: left; direction: ltr; background: #fafbfd; color: #2d2f31; }
        .share-row button { padding: 12px 18px; background: linear-gradient(135deg, #ff5757, #b95cff); color: #fff; border: 0; border-radius: 10px; cursor: pointer; font-weight: 700; white-space: nowrap; display: inline-flex; align-items: center; gap: 6px; }
        .share-row button svg { width: 16px; height: 16px; }
        .share-row button.copied { background: #22a04d; }

        .wa-banner { background: linear-gradient(135deg, #25D366, #128C7E); color: #fff; padding: 22px; border-radius: 18px; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; box-shadow: 0 8px 24px rgba(37,211,102,0.25); }
        .wa-banner .wa-text h3 { font-size: 17px; margin-bottom: 4px; color: #fff; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        .wa-banner .wa-text h3 svg { width: 20px; height: 20px; fill: #fff; }
        .wa-banner .wa-text p { font-size: 13px; opacity: 0.95; color: #fff; }
        .wa-banner .wa-btn { background: #fff; color: #128C7E; padding: 10px 20px; border-radius: 10px; font-weight: 700; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
        .wa-banner .wa-btn:hover { color: #25D366; text-decoration: none; }

        .whatsapp-float { position: fixed; bottom: 24px; left: 24px; background: #25D366; color: #fff; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 24px rgba(37,211,102,0.5); z-index: 999; transition: 0.3s; text-decoration: none; }
        .whatsapp-float:hover { transform: scale(1.1); text-decoration: none; }
        .whatsapp-float svg { width: 32px; height: 32px; fill: #fff; }

        .footer { background: #2d2f31; color: #b8bcc4; margin-top: 60px; padding: 40px 20px 20px; }
        .footer-container { max-width: 1200px; margin: 0 auto; display: grid; gap: 30px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        .footer h4 { color: #fff; margin-bottom: 12px; font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
        .footer h4 svg { width: 16px; height: 16px; stroke: #b95cff; }
        .footer ul { list-style: none; }
        .footer ul li { margin-bottom: 8px; font-size: 14px; display: flex; align-items: center; gap: 6px; }
        .footer ul li svg { width: 14px; height: 14px; stroke: #b95cff; flex-shrink: 0; }
        .footer a { color: #b8bcc4; }
        .footer a:hover { color: #b95cff; text-decoration: none; }
        .footer p { font-size: 13px; line-height: 1.7; color: #b8bcc4; }
        .footer-bottom { text-align: center; padding-top: 20px; margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 14px; color: #b8bcc4; }
        .footer-brand { display: inline-block; font-weight: 800; font-size: 18px; white-space: nowrap; background: linear-gradient(90deg, #ff5757, #ff9a3c, #ffd93d, #6bcb77, #4d96ff, #b95cff, #ff5757); background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: rainbowSlide 4s linear infinite; }
        .fbi-brand { display: block; margin-top: 8px; font-family: monospace; letter-spacing: 3px; font-size: 13px; opacity: 0.75; font-weight: 700; color: #b8bcc4; }

        .empty { text-align: center; padding: 40px 20px; color: #999; }
        .empty svg { width: 60px; height: 60px; stroke: #ccc; margin-bottom: 12px; }

        .hero { text-align: center; padding: 70px 20px 50px; }
        .hero h1 { font-size: 72px; font-weight: 800; display: inline-block; line-height: 1; white-space: nowrap; margin-bottom: 20px; background: linear-gradient(90deg, #ff5757, #ff9a3c, #ffd93d, #6bcb77, #4d96ff, #b95cff, #ff5757); background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: rainbowSlide 4s linear infinite; }
        @keyframes rainbowSlide { 0% { background-position: 0% 50%; } 100% { background-position: 300% 50%; } }
        .hero p { font-size: 18px; margin-bottom: 30px; max-width: 600px; margin-left: auto; margin-right: auto; color: #666; font-weight: 500; }
        .hero-buttons { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
        .section { padding: 30px 0; }
        .section-title { text-align: center; font-size: 24px; margin-bottom: 30px; position: relative; padding-bottom: 14px; font-weight: 700; color: #2d2f31; display: flex; align-items: center; justify-content: center; gap: 10px; }
        .section-title svg { width: 26px; height: 26px; stroke: #b95cff; }
        .section-title::after { content: ''; position: absolute; bottom: 0; left: 50%; transform: translateX(-50%); width: 90px; height: 4px; background: linear-gradient(90deg, #ff5757, #ffd93d, #6bcb77, #4d96ff, #b95cff); border-radius: 4px; }

        .accounts-box { background: #fff; border: 1px solid #eef0f4; padding: 22px; border-radius: 18px; margin-bottom: 20px; box-shadow: 0 4px 14px rgba(0,0,0,0.04); }
        .accounts-box h3 { margin-bottom: 14px; font-size: 17px; font-weight: 700; color: #2d2f31; display: flex; align-items: center; gap: 8px; }
        .accounts-box h3 svg { width: 18px; height: 18px; stroke: #b95cff; }
        .accounts-list { display: grid; gap: 10px; }
        .account-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: #fafbfd; border-radius: 12px; border: 1px solid #eef0f4; transition: 0.2s; }
        .account-item.current { background: linear-gradient(135deg, rgba(255,87,87,0.08), rgba(185,92,255,0.08)); border-color: rgba(185,92,255,0.35); }
        .account-item img { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .account-item .acc-info { flex: 1; }
        .account-item .acc-name { font-weight: 700; color: #2d2f31; font-size: 15px; }
        .account-item .acc-user { color: #888; font-size: 13px; direction: ltr; }
        .account-item .acc-actions { display: flex; gap: 6px; }
        .account-item .acc-actions button { padding: 7px 14px; border-radius: 9px; font-size: 13px; font-weight: 700; cursor: pointer; border: 0; }
        .acc-switch { background: linear-gradient(135deg, #4d96ff, #2c72e0); color: #fff; }
        .acc-remove { background: #fdecec; color: #c0392b; }
        .acc-remove:hover { background: #f5b8b8; }

        .flags-section { display: flex; justify-content: center; align-items: flex-end; gap: 40px; flex-wrap: wrap; margin: 30px auto 10px; padding: 20px; }
        .flag-container { text-align: center; }

        .sudan-flag { width: 200px; height: 120px; position: relative; border-radius: 8px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
        .flag-red { position: absolute; top: 0; left: 0; right: 0; height: 33.33%; background-color: #D21034; background-image: radial-gradient(circle, rgba(255,255,255,0.4) 1.2px, transparent 1.6px); background-size: 9px 9px; }
        .flag-white { position: absolute; top: 33.33%; left: 0; right: 0; height: 33.33%; background-color: #FFFFFF; background-image: radial-gradient(circle, rgba(0,0,0,0.15) 1.2px, transparent 1.6px); background-size: 9px 9px; }
        .flag-black { position: absolute; bottom: 0; left: 0; right: 0; height: 33.34%; background-color: #000000; background-image: radial-gradient(circle, rgba(255,255,255,0.4) 1.2px, transparent 1.6px); background-size: 9px 9px; }
        .flag-green-triangle { position: absolute; top: 0; left: 0; bottom: 0; width: 33%; background-color: #007229; background-image: radial-gradient(circle, rgba(255,255,255,0.4) 1.2px, transparent 1.6px); background-size: 9px 9px; clip-path: polygon(0 0, 100% 50%, 0 100%); z-index: 2; }

        .sudan-old-flag { width: 200px; height: 120px; position: relative; border-radius: 8px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
        .old-flag-blue { position: absolute; top: 0; left: 0; right: 0; height: 33.33%; background-color: #0F52BA; background-image: radial-gradient(circle, rgba(255,255,255,0.4) 1.2px, transparent 1.6px); background-size: 9px 9px; }
        .old-flag-yellow { position: absolute; top: 33.33%; left: 0; right: 0; height: 33.33%; background-color: #FFD700; background-image: radial-gradient(circle, rgba(0,0,0,0.15) 1.2px, transparent 1.6px); background-size: 9px 9px; }
        .old-flag-green { position: absolute; bottom: 0; left: 0; right: 0; height: 33.34%; background-color: #007A3D; background-image: radial-gradient(circle, rgba(255,255,255,0.4) 1.2px, transparent 1.6px); background-size: 9px 9px; }

        .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 20px; }
        .feature-card { background: #fff; border: 1px solid #eef0f4; border-radius: 16px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.04); transition: 0.25s; }
        .feature-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(185,92,255,0.15); border-color: rgba(185,92,255,0.3); }
        .feature-card .feature-icon { width: 56px; height: 56px; border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 14px; }
        .feature-card .feature-icon svg { width: 26px; height: 26px; stroke-width: 2; }
        .feature-card h4 { font-size: 15px; font-weight: 700; color: #2d2f31; margin-bottom: 6px; }
        .feature-card p { font-size: 13px; color: #888; line-height: 1.6; }

        .live-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; max-width: 720px; margin: 0 auto 30px; }
        .live-stat { background: #fff; border: 1px solid #eef0f4; border-radius: 14px; padding: 16px; text-align: center; box-shadow: 0 3px 12px rgba(0,0,0,0.04); }
        .live-stat .ls-num { font-size: 24px; font-weight: 800; background: linear-gradient(135deg, #ff5757, #b95cff); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
        .live-stat .ls-lbl { font-size: 12px; color: #888; margin-top: 2px; display: flex; align-items: center; justify-content: center; gap: 4px; }
        .live-stat .ls-lbl svg { width: 12px; height: 12px; stroke: #888; }

        .nickname-presets { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
        .nickname-presets button {
            padding: 8px 14px; border-radius: 20px; border: 2px solid #eef0f4;
            background: #fafbfd; cursor: pointer; font-size: 14px; font-weight: 600;
            transition: 0.2s; color: #2d2f31; font-family: inherit;
            display: inline-flex; align-items: center; gap: 6px;
        }
        .nickname-presets button:hover { border-color: #f59e0b; background: #fffbeb; transform: translateY(-2px); }
        .nickname-presets button.selected { border-color: #f59e0b; background: #fef3c7; color: #d97706; box-shadow: 0 4px 14px rgba(245,158,11,0.3); }

        .custom-link-box {
            background: linear-gradient(135deg, rgba(77,150,255,0.08), rgba(99,102,241,0.08));
            border: 2px solid rgba(77,150,255,0.25);
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 20px;
        }
        .custom-link-box h3 { font-size: 17px; font-weight: 700; color: #2d2f31; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .custom-link-box h3 svg { width: 18px; height: 18px; stroke: #4d96ff; }
        .custom-link-box .status-badge {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 3px 10px; border-radius: 10px; font-size: 12px; font-weight: 700;
            margin-right: 8px;
        }
        .status-badge svg { width: 12px; height: 12px; }
        .status-active { background: #e6f9ee; color: #0d3d1f; border: 1px solid #a9e6bf; }
        .status-active svg { stroke: #22a04d; }
        .status-disabled { background: #fdecec; color: #5c0f0f; border: 1px solid #f5b8b8; }
        .status-disabled svg { stroke: #c0392b; }

        .members-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
        .member-card { background: #fff; border: 1px solid #eef0f4; border-radius: 16px; padding: 16px; display: flex; align-items: center; gap: 14px; box-shadow: 0 4px 14px rgba(0,0,0,0.04); transition: 0.25s; }
        .member-card:hover { transform: translateY(-3px); box-shadow: 0 10px 28px rgba(185,92,255,0.15); border-color: rgba(185,92,255,0.3); }
        .member-avatar { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 2px solid #fff; box-shadow: 0 2px 10px rgba(0,0,0,0.08); flex-shrink: 0; }
        .member-info { flex: 1; min-width: 0; }
        .member-name { font-weight: 800; color: #2d2f31; font-size: 15px; }
        .member-nick { font-size: 12px; color: #d97706; font-weight: 700; margin-top: 2px; display: flex; align-items: center; gap: 3px; }
        .member-nick svg { width: 12px; height: 12px; fill: #d97706; }
        .member-username { font-size: 12px; color: #888; direction: ltr; font-family: monospace; margin-top: 2px; }
        .member-meta { display: flex; gap: 10px; font-size: 11px; color: #999; margin-top: 6px; flex-wrap: wrap; }
        .member-meta span { display: inline-flex; align-items: center; gap: 3px; }
        .member-meta svg { width: 11px; height: 11px; stroke: #999; }
        .member-date { font-size: 11px; color: #aaa; margin-top: 4px; display: flex; align-items: center; gap: 3px; }
        .member-date svg { width: 11px; height: 11px; stroke: #aaa; }
        .member-card .btn { flex-shrink: 0; }

        /* ============ Public Messages (رسائلنا) ============ */
        .pub-timeline {
            display: flex; flex-direction: column; gap: 18px;
            max-width: 780px; margin: 0 auto;
        }
        .pub-card {
            background: #fff; border: 1px solid #eef0f4; border-radius: 18px;
            padding: 18px 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.05);
            transition: 0.25s; position: relative;
            border-right: 4px solid #14b8a6;
        }
        .pub-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 32px rgba(20,184,166,0.15);
            border-right-color: #0d9488;
        }
        .pub-header {
            display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
            flex-wrap: wrap;
        }
        .pub-avatar {
            width: 52px; height: 52px; border-radius: 50%; object-fit: cover;
            border: 3px solid #fff; box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            flex-shrink: 0; background: #eee;
        }
        .pub-avatar-anon {
            width: 52px; height: 52px; border-radius: 50%;
            background: linear-gradient(135deg, #6b7280, #4b5563);
            display: flex; align-items: center; justify-content: center;
            color: #fff; flex-shrink: 0;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }
        .pub-avatar-anon svg { width: 26px; height: 26px; stroke: #fff; }
        .pub-users {
            display: flex; align-items: center; gap: 10px; flex: 1;
            flex-wrap: wrap;
        }
        .pub-user {
            display: flex; align-items: center; gap: 8px;
            padding: 6px 12px; background: #fafbfd;
            border-radius: 12px; border: 1px solid #eef0f4;
        }
        .pub-user-avatar {
            width: 32px; height: 32px; border-radius: 50%;
            object-fit: cover; flex-shrink: 0;
            border: 2px solid #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }
        .pub-user-avatar-anon {
            width: 32px; height: 32px; border-radius: 50%;
            background: linear-gradient(135deg, #9ca3af, #6b7280);
            display: flex; align-items: center; justify-content: center;
            color: #fff; flex-shrink: 0;
        }
        .pub-user-avatar-anon svg { width: 16px; height: 16px; stroke: #fff; }
        .pub-user-info { display: flex; flex-direction: column; line-height: 1.3; }
        .pub-user-name { font-size: 13px; font-weight: 800; color: #2d2f31; }
        .pub-user-sub { font-size: 11px; color: #888; }
        .pub-user-nick { font-size: 11px; color: #d97706; font-weight: 700; display: inline-flex; align-items: center; gap: 2px; }
        .pub-user-nick svg { width: 10px; height: 10px; fill: #d97706; }
        .pub-arrow {
            color: #14b8a6; font-size: 22px; font-weight: 800;
            flex-shrink: 0;
        }
        .pub-content {
            font-size: 15px; color: #2d2f31; line-height: 1.8;
            padding: 14px 16px; background: #fafbfd;
            border-radius: 12px; white-space: pre-wrap;
            word-break: break-word; margin-bottom: 12px;
            border-right: 3px solid #14b8a6;
        }
        .pub-images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 8px;
            margin-bottom: 12px;
        }
        .pub-images-grid img {
            width: 100%; aspect-ratio: 1; object-fit: cover;
            border-radius: 12px; cursor: zoom-in;
            border: 1px solid #eef0f4; transition: 0.2s;
        }
        .pub-images-grid img:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 20px rgba(20,184,166,0.25);
        }
        .pub-footer {
            display: flex; align-items: center; justify-content: space-between;
            gap: 10px; flex-wrap: wrap;
        }
        .pub-date {
            font-size: 12px; color: #999;
            display: flex; align-items: center; gap: 4px;
        }
        .pub-date svg { width: 12px; height: 12px; stroke: #999; }
        .pub-tags { display: flex; gap: 6px; flex-wrap: wrap; }
        .pub-tag {
            font-size: 11px; font-weight: 700;
            padding: 3px 10px; border-radius: 10px;
            display: inline-flex; align-items: center; gap: 3px;
        }
        .pub-tag svg { width: 11px; height: 11px; }
        .tag-public { background: #d1fae5; color: #065f46; }
        .tag-public svg { stroke: #065f46; }
        .tag-nick { background: #fef3c7; color: #92400e; }
        .tag-nick svg { fill: #92400e; stroke: #92400e; }
        .tag-anon { background: #e5e7eb; color: #374151; }
        .tag-anon svg { stroke: #374151; }

        .pub-filters {
            display: flex; gap: 8px; justify-content: center;
            flex-wrap: wrap; margin-bottom: 24px;
        }
        .pub-filter-btn {
            padding: 8px 18px; border-radius: 20px;
            background: #fff; border: 2px solid #eef0f4;
            font-size: 13px; font-weight: 700; color: #666;
            cursor: pointer; transition: 0.25s; font-family: inherit;
            display: inline-flex; align-items: center; gap: 6px;
        }
        .pub-filter-btn:hover {
            border-color: #14b8a6; color: #0d9488;
            transform: translateY(-2px);
        }
        .pub-filter-btn.active {
            background: linear-gradient(135deg, #14b8a6, #0d9488);
            color: #fff; border-color: #0d9488;
            box-shadow: 0 4px 14px rgba(20,184,166,0.35);
        }
        .pub-filter-btn svg { width: 14px; height: 14px; }

        /* ============ Choice cards in send form ============ */
        .reveal-choices {
            display: grid; gap: 10px;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            margin-bottom: 18px;
        }
        .reveal-choice {
            position: relative;
            padding: 16px 14px;
            border: 2px solid #eef0f4;
            border-radius: 14px;
            background: #fafbfd;
            cursor: pointer;
            transition: 0.25s;
            text-align: center;
            display: flex; flex-direction: column;
            align-items: center; gap: 8px;
        }
        .reveal-choice:hover {
            border-color: #b95cff;
            background: #f9f5ff;
            transform: translateY(-2px);
        }
        .reveal-choice input[type="radio"] {
            position: absolute; opacity: 0; pointer-events: none;
        }
        .reveal-choice .rc-icon {
            width: 44px; height: 44px; border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            color: #fff; flex-shrink: 0;
        }
        .reveal-choice .rc-icon svg { width: 22px; height: 22px; stroke: #fff; }
        .reveal-choice .rc-title {
            font-size: 14px; font-weight: 800; color: #2d2f31;
        }
        .reveal-choice .rc-desc {
            font-size: 11px; color: #888; line-height: 1.4;
        }
        .reveal-choice.selected {
            border-color: #b95cff;
            background: linear-gradient(135deg, rgba(185,92,255,0.08), rgba(20,184,166,0.08));
            box-shadow: 0 6px 20px rgba(185,92,255,0.2);
        }
        .reveal-choice.selected .rc-title { color: #8b2fc9; }

        .rc-public { background: linear-gradient(135deg, #14b8a6, #0d9488); }
        .rc-nick { background: linear-gradient(135deg, #f59e0b, #d97706); }
        .rc-anon { background: linear-gradient(135deg, #6b7280, #4b5563); }

        /* ============ Message images grid (send form) ============ */
        .msg-images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 10px;
            margin-top: 14px;
        }
        .msg-image-item {
            position: relative; border-radius: 12px; overflow: hidden;
            border: 1px solid #eef0f4; background: #f3f4f6;
            aspect-ratio: 1;
        }
        .msg-image-item img {
            width: 100%; height: 100%; object-fit: cover;
            cursor: zoom-in;
        }
        .msg-image-remove {
            position: absolute; top: 5px; left: 5px;
            background: rgba(231,76,60,0.92); color: #fff;
            border: 0; width: 28px; height: 28px;
            border-radius: 50%; cursor: pointer;
            font-size: 16px; line-height: 1; font-weight: 700;
            display: flex; align-items: center; justify-content: center;
        }
        .msg-image-remove:hover { background: #c0392b; }
        .msg-image-index {
            position: absolute; bottom: 5px; right: 5px;
            background: rgba(0,0,0,0.6); color: #fff;
            font-size: 11px; padding: 2px 8px; border-radius: 8px;
            font-weight: 700;
        }

        @media (max-width: 768px) {
            .nav-toggle-label { display: flex; }
            .nav-menu { display: none; flex-direction: column; width: 100%; margin-top: 12px; gap: 8px; }
            .nav-toggle:checked ~ .nav-menu { display: flex; }
            .nav-menu a, .nav-menu .nav-google-btn { width: 100%; justify-content: center; }
            .hero h1 { font-size: 42px; }
            .form-wrapper { margin: 20px 12px; padding: 22px; }
            .gallery { gap: 50px; }
            .flags-section { gap: 20px; }
            .sudan-flag, .sudan-old-flag { width: 140px; height: 84px; }
            .share-row { flex-direction: column; }
            .members-grid { grid-template-columns: 1fr; }
            .pub-user-name { font-size: 12px; }
            .pub-images-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); }
            .msg-images-grid { grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <div class="nav-brand">
                {{ icons.sparkle|safe }}
                <span>خليك واضح</span>
            </div>
            <input type="checkbox" id="nav-toggle" class="nav-toggle">
            <label for="nav-toggle" class="nav-toggle-label"><span></span><span></span><span></span></label>
            <ul class="nav-menu">
                <li><a href="{{ url_for('index') }}" class="nav-btn-home">
                    {{ icons.home|safe }} الرئيسية
                </a></li>
                <li><a href="{{ url_for('public_messages') }}" class="nav-btn-public">
                    {{ icons.public_messages|safe }} رسائلنا
                </a></li>
                {% if session.user_username %}
                    <li><a href="{{ url_for('profile') }}" class="nav-btn-user user-badge">
                        <img src="{{ session.user_avatar }}" alt="">
                        <span>{{ session.user_name }}</span>
                        <span class="uid">#{{ session.user_id }}</span>
                    </a></li>
                    <li><a href="{{ url_for('members_list') }}" class="nav-btn-members">
                        {{ icons.users|safe }} الأعضاء
                    </a></li>
                    <li><a href="{{ url_for('nickname_page') }}" class="nav-btn-nick">
                        {{ icons.star|safe }} اللقب
                    </a></li>
                    <li><a href="{{ url_for('messages') }}" class="nav-btn-msgs">
                        {{ icons.messages|safe }} رسائلي
                    </a></li>
                    <li><a href="{{ url_for('edit_profile') }}" class="nav-btn-edit">
                        {{ icons.edit|safe }} تعديل
                    </a></li>
                    <li><a href="{{ url_for('signout') }}" class="nav-btn-out">
                        {{ icons.logout|safe }} خروج
                    </a></li>
                {% else %}
                    <li><a href="{{ url_for('members_list') }}" class="nav-btn-members">
                        {{ icons.users|safe }} الأعضاء
                    </a></li>
                    <li><a href="{{ url_for('signin') }}" class="nav-google-btn">
                        <svg viewBox="0 0 48 48" width="18" height="18">
                            <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
                            <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
                            <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
                            <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
                        </svg>
                        <span>تسجيل Google</span>
                    </a></li>
                {% endif %}
                <li><a href="{{ url_for('help_page') }}" class="nav-btn-help">
                    {{ icons.help|safe }} تعليمات
                </a></li>
            </ul>
        </div>
    </nav>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        <div class="flash-messages">
            {% for category, message in messages %}
            <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
        </div>
        {% endif %}
    {% endwith %}

    <main>{{ content|safe }}</main>

    <footer class="footer">
        <div class="footer-container">
            <div>
                <h4>{{ icons.globe|safe }} حول خليك واضح</h4>
                <p>منصة تواصل اجتماعي تتيح للمستخدمين إرسال رسائل وأسئلة مجهولة المصدر.</p>
            </div>
            <div>
                <h4>{{ icons.link|safe }} روابط سريعة</h4>
                <ul>
                    <li>{{ icons.home|safe }} <a href="{{ url_for('index') }}">الرئيسية</a></li>
                    <li>{{ icons.public_messages|safe }} <a href="{{ url_for('public_messages') }}">رسائلنا</a></li>
                    <li>{{ icons.users|safe }} <a href="{{ url_for('members_list') }}">الأعضاء</a></li>
                    <li>{{ icons.help|safe }} <a href="{{ url_for('help_page') }}">تعليمات</a></li>
                </ul>
            </div>
            <div>
                <h4>{{ icons.stats|safe }} إحصائيات</h4>
                <ul>
                    <li>{{ icons.users|safe }} المستخدمون: <b style="color:#b95cff;">{{ total_users }}</b></li>
                    <li>{{ icons.messages|safe }} الرسائل: <b style="color:#b95cff;">{{ total_messages }}</b></li>
                    <li>{{ icons.star|safe }} الزيارات: <b style="color:#b95cff;">{{ site_stats.visits }}</b></li>
                </ul>
            </div>
            <div>
                <h4>{{ icons.heart|safe }} تابعنا</h4>
                <ul>
                    <li>{{ icons.link|safe }} <a href="{{ whatsapp_url }}" target="_blank" rel="noopener">قناة واتساب</a></li>
                </ul>
            </div>
        </div>

        <div class="flags-section">
            <div class="flag-container">
                <div class="sudan-old-flag">
                    <div class="old-flag-blue"></div>
                    <div class="old-flag-yellow"></div>
                    <div class="old-flag-green"></div>
                </div>
            </div>
            <div class="flag-container">
                <div class="sudan-flag">
                    <div class="flag-red"></div>
                    <div class="flag-white"></div>
                    <div class="flag-black"></div>
                    <div class="flag-green-triangle"></div>
                </div>
            </div>
        </div>

        <div class="footer-bottom" style="margin-top:20px;">
            جميع الحقوق محفوظة © 2026 -
            <span class="footer-brand">خليك واضح</span>
            <span class="fbi-brand">𝙵𝙱𝙸 𝚂𝚄𝙳𝙰𝙽𝙴𝚂𝙴</span>
        </div>
    </footer>

    <div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
        <button class="close-lb" onclick="closeLightbox(event, true)" aria-label="إغلاق">×</button>
        <img id="lightbox-img" src="" alt="" onclick="event.stopPropagation()">
    </div>

    <a class="whatsapp-float" href="{{ whatsapp_url }}" target="_blank" rel="noopener" title="قناة واتساب">
        <svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
    </a>

    <script>
    const CSRF_TOKEN = "{{ csrf_token() }}";
    function openLightbox(src) {
        document.getElementById('lightbox-img').src = src;
        document.getElementById('lightbox').classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    function closeLightbox(e, force) {
        if (!force && e && e.target && e.target.id === 'lightbox-img') return;
        if (!force && e && e.target && e.target.classList && e.target.classList.contains('close-lb')) return;
        document.getElementById('lightbox').classList.remove('active');
        document.body.style.overflow = '';
    }
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            document.getElementById('lightbox').classList.remove('active');
            document.body.style.overflow = '';
        }
    });
    function copyBtn(btn, text) {
        const done = () => {
            btn.classList.add('copied');
            const orig = btn.innerHTML;
            btn.innerHTML = 'تم النسخ';
            setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = orig; }, 1500);
        };
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
        } else fallbackCopy(text, done);
    }
    function fallbackCopy(text, cb) {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); if (cb) cb(); } catch(e) {}
        document.body.removeChild(ta);
    }
    function replyMessage(msgId) {
        const input = document.getElementById('reply-input-' + msgId);
        const text = input.value.trim();
        if (!text) return;
        fetch('/reply/' + encodeURIComponent(msgId), {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRF-Token': CSRF_TOKEN},
            body: 'reply=' + encodeURIComponent(text) + '&_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(data => {
            if (data.status === 'succ') location.reload();
            else alert(data.message || 'خطأ');
        });
    }
    function switchAccount(username) {
        fetch('/accounts/switch/' + encodeURIComponent(username), {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: '_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(data => {
            if (data.status === 'succ') window.location.href = '/profile';
            else alert(data.message || 'خطأ');
        });
    }
    function removeAccount(username) {
        if (!confirm('إزالة @' + username + ' من هذه القائمة؟')) return;
        fetch('/accounts/remove/' + encodeURIComponent(username), {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: '_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(data => {
            if (data.status === 'succ') location.reload();
        });
    }
    function filterPublicMessages(filter, btn) {
        document.querySelectorAll('.pub-filter-btn').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        document.querySelectorAll('.pub-card').forEach(card => {
            const tags = card.dataset.tags || '';
            if (filter === 'all' || tags.includes(filter)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }
    </script>
</body>
</html>
"""


def render_page(content_html, page_title=None, **kwargs):
    return render_template_string(
        BASE_TEMPLATE,
        content=content_html,
        page_title=page_title,
        **kwargs
    )


# ============================================================
# PAGE CONTENTS
# ============================================================
SIGNIN_CONTENT = r"""
<div class="form-wrapper" style="max-width: 440px;">
    <div style="text-align:center; margin-bottom:20px;">
        <div style="font-size:52px; font-weight:900; background: linear-gradient(135deg, #ff5757, #b95cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">خليك واضح</div>
    </div>
    <h2 class="form-title">تسجيل Google</h2>
    <p class="form-sub">ادخل بحساب Google للبدء</p>

    {% if follow %}
    <div class="alert alert-warning show" style="margin-bottom:16px;">
        سجّل لمتابعة <b>@{{ follow }}</b>
    </div>
    {% endif %}

    <a href="{{ url_for('auth_google') }}{% if follow %}?follow={{ follow }}{% endif %}" class="google-btn">
        <svg viewBox="0 0 48 48" width="22" height="22">
            <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
            <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
            <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
            <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
        </svg>
        <span>الدخول باستخدام Google</span>
    </a>

    <div style="text-align:center; margin-top:22px; color:#888; font-size:13px; line-height:1.6;">
        سيتم إنشاء حسابك تلقائياً عند أول دخول<br>
        <small>حساب واحد فقط لكل متصفح</small>
    </div>
</div>
"""

INDEX_CONTENT = r"""
<section class="hero">
    <h1>خليك واضح</h1>
    <p>هل أنت مستعد لمعرفة ملاحظات الناس عنك بدون أن تعرف المرسل؟</p>
    <div class="hero-buttons">
        {% if session.user_username %}
            <a href="{{ url_for('profile') }}" class="btn btn-berry">{{ icons.user|safe }} بروفايلي</a>
            <a href="{{ url_for('nickname_page') }}" class="btn btn-gold">{{ icons.star|safe }} اختر لقبك</a>
        {% else %}
            <a href="{{ url_for('signin') }}" class="google-btn" style="max-width:300px;">
                <svg viewBox="0 0 48 48" width="22" height="22">
                    <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
                    <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
                    <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
                    <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
                </svg>
                <span>تسجيل Google</span>
            </a>
        {% endif %}
    </div>
</section>

<section class="section" style="padding-top:0;">
    <div class="container">
        <div class="live-stats">
            <div class="live-stat"><div class="ls-num">{{ total_users }}</div><div class="ls-lbl">{{ icons.users|safe }} عضو مسجل</div></div>
            <div class="live-stat"><div class="ls-num">{{ total_messages }}</div><div class="ls-lbl">{{ icons.messages|safe }} رسالة مرسلة</div></div>
            <div class="live-stat"><div class="ls-num">{{ site_stats.visits }}</div><div class="ls-lbl">{{ icons.eye|safe }} زيارة للموقع</div></div>
        </div>
    </div>
</section>

{% if gallery %}
<section class="section">
    <div class="container">
        <div class="wa-banner">
            <div class="wa-text">
                <h3>
                    <svg viewBox="0 0 24 24" fill="#fff" style="width:20px;height:20px;">
                        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                    </svg>
                    انضم لقناة خليك واضح على واتساب
                </h3>
                <p>احصل على آخر التحديثات والميزات الجديدة</p>
            </div>
            <a href="{{ whatsapp_url }}" target="_blank" rel="noopener" class="wa-btn">انضم الآن</a>
        </div>

        <div class="gallery">
            {% for item in gallery %}
            <div class="gallery-item-wrap">
                <div class="gallery-inner">
                    <div class="gallery-item" onclick="openLightbox('{{ item.image }}')">
                        <img src="{{ item.image }}" alt="{{ item.title or item.platform }}" loading="lazy">
                    </div>
                    {% if item.link %}
                    <a href="{{ item.link }}" target="_blank" rel="noopener noreferrer"
                       class="gallery-link-btn" style="background: {{ item.color }};">
                        {{ item.icon|safe }}
                        <span>{{ item.title or item.platform }}</span>
                    </a>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

<!-- ✅ قسم أحدث الرسائل العامة في الرئيسية -->
{% if recent_public_messages %}
<section class="section" style="padding-top:20px;">
    <div class="container">
        <h2 class="section-title">
            {{ icons.public_messages|safe }} أحدث الرسائل العامة
        </h2>
        <p style="text-align:center; color:#888; font-size:14px; margin-bottom:24px;">
            آخر {{ recent_public_messages|length }} رسائل مرسلة في الموقع
        </p>

        <div class="pub-timeline" style="max-width:780px; margin:0 auto;">
            {% for m in recent_public_messages %}
            <div class="pub-card" data-tags="{{ m.reveal_type }}">
                <div class="pub-header">
                    {% if m.reveal_type == 'profile' and m.sender %}
                        <a href="{{ url_for('view_profile', username=m.sender.username) }}" style="text-decoration:none;">
                            <img src="{{ m.sender.avatar }}" alt="" class="pub-avatar">
                        </a>
                    {% elif m.reveal_type == 'nickname' and m.sender %}
                        <div class="pub-avatar-anon">{{ icons.star|safe }}</div>
                    {% else %}
                        <div class="pub-avatar-anon">{{ icons.lock|safe }}</div>
                    {% endif %}

                    <div class="pub-users">
                        <div class="pub-user">
                            {% if m.reveal_type == 'profile' and m.sender %}
                                <img src="{{ m.sender.avatar }}" alt="" class="pub-user-avatar">
                                <div class="pub-user-info">
                                    <span class="pub-user-name">{{ m.sender.name }}</span>
                                    {% if m.sender.nickname %}
                                    <span class="pub-user-nick">{{ icons.star_filled|safe }} {{ m.sender.nickname }}</span>
                                    {% endif %}
                                    <span class="pub-user-sub">@{{ m.sender.username }}</span>
                                </div>
                            {% elif m.reveal_type == 'nickname' and m.sender %}
                                <div class="pub-user-avatar-anon">{{ icons.star|safe }}</div>
                                <div class="pub-user-info">
                                    <span class="pub-user-name">{{ m.sender.nickname or 'مستخدم' }}</span>
                                    <span class="pub-user-sub" style="color:#d97706;">كشف اللقب فقط</span>
                                </div>
                            {% else %}
                                <div class="pub-user-avatar-anon">{{ icons.lock|safe }}</div>
                                <div class="pub-user-info">
                                    <span class="pub-user-name">مجهول</span>
                                    <span class="pub-user-sub">مرسل مجهول</span>
                                </div>
                            {% endif %}
                        </div>

                        <div class="pub-arrow">→</div>

                        <div class="pub-user">
                            <img src="{{ m.recipient.avatar }}" alt="" class="pub-user-avatar">
                            <div class="pub-user-info">
                                <span class="pub-user-name">{{ m.recipient.name }}</span>
                                {% if m.recipient.nickname %}
                                <span class="pub-user-nick">{{ icons.star_filled|safe }} {{ m.recipient.nickname }}</span>
                                {% endif %}
                                <span class="pub-user-sub">@{{ m.recipient.username }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {% if m.images %}
                <div class="pub-images-grid">
                    {% for img in m.images %}
                    <img src="{{ img }}" alt=""
                         onclick="openLightbox(this.src)">
                    {% endfor %}
                </div>
                {% endif %}

                {% if m.content %}
                <div class="pub-content">{{ m.content }}</div>
                {% endif %}

                <div class="pub-footer">
                    <div class="pub-date">
                        {{ icons.calendar|safe }} {{ m.created_at }}
                    </div>
                    <div class="pub-tags">
                        {% if m.reveal_type == 'profile' %}
                        <span class="pub-tag tag-public">{{ icons.user|safe }} بروفايل</span>
                        {% elif m.reveal_type == 'nickname' %}
                        <span class="pub-tag tag-nick">{{ icons.star|safe }} لقب</span>
                        {% else %}
                        <span class="pub-tag tag-anon">{{ icons.lock|safe }} مجهول</span>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

        <div style="text-align:center; margin-top:28px;">
            <a href="{{ url_for('public_messages') }}" class="btn btn-teal">
                {{ icons.public_messages|safe }} عرض كل الرسائل
            </a>
        </div>
    </div>
</section>
{% endif %}

<section class="section">
    <div class="container">
        <h2 class="section-title">{{ icons.sparkle|safe }} لماذا خليك واضح؟</h2>
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(255,87,87,0.15), rgba(255,154,60,0.15));">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#ff5757" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                </div>
                <h4>خصوصية كاملة</h4>
                <p>رسائل مجهولة تماماً، هوية المرسل محمية</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(20,184,166,0.15), rgba(13,148,136,0.15));">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#14b8a6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                </div>
                <h4>قسم رسائلنا</h4>
                <p>شاهد جميع المحادثات العامة في الموقع</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(77,150,255,0.15), rgba(44,114,224,0.15));">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#4d96ff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                </div>
                <h4>سريع وسهل</h4>
                <p>سجّل بحساب Google بضغطة واحدة</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(34,197,94,0.15), rgba(22,163,74,0.15));">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                </div>
                <h4>حماية متقدمة</h4>
                <p>تشفير، CSRF، Rate Limiting</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.15));">
                    <svg viewBox="0 0 24 24" fill="currentColor" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </div>
                <h4>لقب مميز</h4>
                <p>اختر لقباً يظهر بجانب اسمك</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background: linear-gradient(135deg, rgba(236,72,153,0.15), rgba(190,24,93,0.15));">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#ec4899" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <h4>إرسال صور</h4>
                <p>أرسل حتى 5 صور مع رسالتك</p>
            </div>
        </div>
    </div>
</section>
"""


# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    gallery_render = []
    for g in gallery_db:
        icon_key = g.get('icon_key', '')
        icon_svg = PLATFORM_SVGS.get(icon_key, '') if icon_key else ''
        gallery_render.append({**g, 'icon': icon_svg})

    # ✅ جمع أحدث 5 رسائل عامة
    recent_public_messages = []
    for recipient_username, msgs in messages_db.items():
        recipient = users_db.get(recipient_username)
        if not recipient:
            continue
        for m in msgs:
            sender_username = m.get('sender')
            reveal_type = m.get('reveal_type', 'anonymous')
            sender_data = None

            if sender_username and sender_username in users_db:
                sender = users_db[sender_username]
                if reveal_type == 'profile':
                    sender_data = {
                        'username': sender_username,
                        'name': sender['name'],
                        'nickname': sender.get('nickname', ''),
                        'avatar': get_user_avatar(sender),
                    }
                elif reveal_type == 'nickname':
                    sender_data = {
                        'username': sender_username,
                        'name': sender.get('nickname') or 'مستخدم',
                        'nickname': sender.get('nickname', ''),
                        'avatar': None,
                    }

            imgs = m.get('images') or ([m['image']] if m.get('image') else [])

            recent_public_messages.append({
                'id': m['id'],
                'content': m['content'],
                'images': imgs,
                'created_at': m['created_at'],
                'reveal_type': reveal_type,
                'sender': sender_data,
                'recipient': {
                    'username': recipient_username,
                    'name': recipient['name'],
                    'nickname': recipient.get('nickname', ''),
                    'avatar': get_user_avatar(recipient),
                },
            })

    recent_public_messages.sort(key=lambda x: x['created_at'], reverse=True)
    recent_public_messages = recent_public_messages[:5]

    content = render_template_string(
        INDEX_CONTENT,
        gallery=gallery_render,
        recent_public_messages=recent_public_messages,
    )
    return render_page(content, page_title='خليك واضح - الرئيسية')


@app.route('/signin')
def signin():
    follow = (request.args.get('follow') or '').strip()
    if follow and not validate_username(follow):
        follow = ''
    content = render_template_string(SIGNIN_CONTENT, follow=follow)
    return render_page(content, page_title='تسجيل الدخول')


@app.route('/signout')
def signout():
    session.clear()
    flash('تم تسجيل الخروج', 'success')
    return redirect(url_for('index'))


@app.route('/auth/google')
def auth_google():
    now = time.time()
    cutoff = now - 600
    for s in list(_pending_oauth_states.keys()):
        if _pending_oauth_states[s] < cutoff:
            del _pending_oauth_states[s]

    state = secrets.token_hex(24)
    session['oauth_state'] = state
    session.permanent = True
    _pending_oauth_states[state] = now

    follow = request.args.get('follow', '')
    if follow and validate_username(follow):
        session['follow_target'] = follow

    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params))


@app.route('/auth/callback')
def auth_callback():
    error = request.args.get('error')
    if error:
        flash('تم إلغاء تسجيل الدخول', 'warning')
        return redirect(url_for('signin'))

    state = request.args.get('state', '')
    in_session = state and session.get('oauth_state') == state
    in_memory = state and state in _pending_oauth_states

    if not (in_session or in_memory):
        security_logger.warning(f'OAuth state mismatch from {client_ip()}')
        flash('انتهت صلاحية الجلسة الأمنية', 'error')
        return redirect(url_for('signin'))

    session.pop('oauth_state', None)
    _pending_oauth_states.pop(state, None)

    code = request.args.get('code', '')
    if not code:
        flash('لم يتم استلام الكود', 'error')
        return redirect(url_for('signin'))

    token_data = urlencode({
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }).encode()

    try:
        req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_json = json.loads(resp.read().decode())
    except Exception as e:
        security_logger.error(f'OAuth token error: {e}')
        flash('فشل الاتصال بـ Google', 'error')
        return redirect(url_for('signin'))

    access_token = token_json.get('access_token')
    if not access_token:
        flash('لم يتم استلام التوكن', 'error')
        return redirect(url_for('signin'))

    try:
        req = urllib.request.Request(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            userinfo = json.loads(resp.read().decode())
    except Exception as e:
        security_logger.error(f'OAuth userinfo error: {e}')
        flash('فشل جلب معلومات المستخدم', 'error')
        return redirect(url_for('signin'))

    email = (userinfo.get('email') or '').lower()
    google_name = userinfo.get('name') or email.split('@')[0]
    picture = userinfo.get('picture') or ''
    email_verified = userinfo.get('email_verified', False)

    if not email or not email_verified:
        flash('البريد غير موثق', 'error')
        return redirect(url_for('signin'))

    username = None
    for u, data in users_db.items():
        if data.get('email') == email:
            username = u
            break

    is_new = False

    if not username:
        base_username = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@')[0])[:15] or 'user'
        candidate = base_username
        i = 1
        while candidate in users_db or not validate_username(candidate):
            candidate = f"{base_username}{i}"[:20]
            i += 1
            if i > 100:
                candidate = 'u' + secrets.token_hex(5)[:10]
                break
        username = candidate
        new_id = generate_unique_id()
        now_str = datetime.now().isoformat()

        default_slug = username.lower()
        existing_slugs = {u.get('custom_slug') for u in users_db.values() if u.get('custom_slug')}
        while default_slug in existing_slugs:
            default_slug = default_slug + secrets.token_hex(2)

        users_db[username] = {
            'id': new_id,
            'username': username,
            'name': sanitize_text(google_name, 40) or 'مستخدم',
            'email': email,
            'password': '',
            'gender': 'male',
            'avatar': picture if picture.startswith('http') else AVATARS['default'],
            'nickname': '',
            'custom_slug': default_slug,
            'link_disabled': False,
            'created_at': now_str,
            'updated_at': now_str,
            'provider': 'google',
        }
        ids_db[new_id] = username
        messages_db[username] = []
        is_new = True
    else:
        user = users_db[username]
        if picture and picture.startswith('http'):
            user['avatar'] = picture
        if 'nickname' not in user:
            user['nickname'] = ''
        if 'custom_slug' not in user:
            user['custom_slug'] = user['username'].lower()
        if 'link_disabled' not in user:
            user['link_disabled'] = False

    add_saved_account(username)

    session.permanent = True
    user = users_db[username]
    session['user_username'] = username
    session['user_name'] = user['name']
    session['user_id'] = user['id']
    session['user_avatar'] = get_user_avatar(user)

    if is_new:
        flash(f'أهلاً {user["name"]}!', 'success')
    else:
        flash(f'مرحباً بعودتك {user["name"]}', 'success')

    follow_target = session.pop('follow_target', None)
    if follow_target and follow_target in users_db and follow_target != username:
        return redirect(url_for('view_profile', username=follow_target))

    return redirect(url_for('profile'))


@app.route('/members')
def members_list():
    members = []
    for username, user in users_db.items():
        members.append({
            'username': username,
            'name': user['name'],
            'nickname': user.get('nickname', ''),
            'id': user['id'],
            'avatar': get_user_avatar(user),
            'created_at': user['created_at'][:10],
            'messages_count': len(messages_db.get(username, [])),
        })
    members.sort(key=lambda m: m['created_at'], reverse=True)

    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:1100px;">
            <h2 class="section-title">{{ icons.users|safe }} جميع الأعضاء ({{ total }})</h2>
            {% if members %}
            <div class="members-grid">
                {% for m in members %}
                <div class="member-card">
                    <img src="{{ m.avatar }}" alt="{{ m.name }}" class="member-avatar">
                    <div class="member-info">
                        <div class="member-name">{{ m.name }}</div>
                        {% if m.nickname %}
                        <div class="member-nick">{{ icons.star_filled|safe }} {{ m.nickname }}</div>
                        {% endif %}
                        <div class="member-username">@{{ m.username }}</div>
                        <div class="member-meta">
                            <span>#{{ m.id }}</span>
                            <span>{{ icons.messages|safe }} {{ m.messages_count }}</span>
                        </div>
                        <div class="member-date">{{ icons.calendar|safe }} {{ m.created_at }}</div>
                    </div>
                    <a href="{{ url_for('view_profile', username=m.username) }}" class="btn btn-blue btn-sm">
                        {{ icons.eye|safe }} زيارة
                    </a>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                <p>لا يوجد أعضاء بعد</p>
            </div>
            {% endif %}
        </div>
    </section>
    """, members=members, total=len(members))
    return render_page(content, page_title=f'الأعضاء ({len(members)})')


@app.route('/profile')
@login_required
def profile():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        session.clear()
        return redirect(url_for('signin'))

    msgs = messages_db.get(username, [])
    messages_count = len(msgs)
    replies_count = sum(1 for m in msgs if m.get('replied'))

    try:
        created = datetime.fromisoformat(user['created_at'])
        days_active = max(1, (datetime.now() - created).days + 1)
    except Exception:
        days_active = 1

    slug = user.get('custom_slug') or user['username']
    share_url = f"{request.host_url.rstrip('/')}/c/{slug}"
    avatar_url = get_user_avatar(user)

    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:820px;">
            <div class="id-box">
                <button class="copy-id-btn" onclick="copyBtn(this, '{{ user.id }}')">{{ icons.copy|safe }} نسخ</button>
                <h3>{{ icons.id|safe }} معرّفك الفريد (ID)</h3>
                <div class="id-value">{{ user.id }}</div>
                <div class="id-hint">احتفظ بهذا الرقم</div>
            </div>
            <div class="profile-header">
                <img class="avatar" src="{{ avatar_url }}" alt="{{ user.name }}"
                     onclick="openLightbox('{{ avatar_url }}')">
                <h2>{{ user.name }}</h2>
                <div class="username">@{{ user.username }}</div>
                {% if user.nickname %}
                <div class="nickname-badge">{{ icons.star_filled|safe }} {{ user.nickname }}</div>
                {% endif %}
                <div class="profile-actions">
                    <a href="{{ url_for('edit_profile') }}" class="btn btn-primary btn-sm">{{ icons.edit|safe }} تعديل</a>
                    <a href="{{ url_for('nickname_page') }}" class="btn btn-gold btn-sm">{{ icons.star|safe }} اللقب</a>
                    <a href="{{ url_for('messages') }}" class="btn btn-berry btn-sm">{{ icons.messages|safe }} رسائلي</a>
                    <a href="{{ url_for('public_messages') }}" class="btn btn-teal btn-sm">{{ icons.public_messages|safe }} رسائلنا</a>
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-card"><div class="num">{{ messages_count }}</div><div class="lbl">{{ icons.messages|safe }} الرسائل</div></div>
                <div class="stat-card"><div class="num">{{ replies_count }}</div><div class="lbl">{{ icons.reply|safe }} الردود</div></div>
                <div class="stat-card"><div class="num">{{ days_active }}</div><div class="lbl">{{ icons.calendar|safe }} يوم معنا</div></div>
            </div>

            <div class="custom-link-box">
                <h3>{{ icons.link|safe }} رابطك المخصص
                    {% if user.link_disabled %}
                    <span class="status-badge status-disabled">{{ icons.eye_off|safe }} معطّل</span>
                    {% else %}
                    <span class="status-badge status-active">{{ icons.check|safe }} نشط</span>
                    {% endif %}
                </h3>
                <p style="font-size:13px; color:#666; margin-bottom:12px;">
                    يمكنك تغيير الرابط الخاص بك أو تعطيله مؤقتاً.
                </p>
                <div class="share-row">
                    <input id="custom-link" type="text" value="{{ share_url }}" readonly onclick="this.select();">
                    <button onclick="copyBtn(this, '{{ share_url }}')">{{ icons.copy|safe }} نسخ</button>
                </div>
                <div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap;">
                    <button class="btn btn-blue btn-sm" onclick="showLinkEditor()">{{ icons.edit|safe }} تغيير الرابط</button>
                    {% if user.link_disabled %}
                    <button class="btn btn-green btn-sm" onclick="toggleLink(false)">{{ icons.eye|safe }} تفعيل</button>
                    {% else %}
                    <button class="btn btn-dark btn-sm" onclick="toggleLink(true)">{{ icons.eye_off|safe }} تعطيل</button>
                    {% endif %}
                </div>
                <div id="link-editor" style="display:none; margin-top:14px; padding-top:14px; border-top:1px dashed rgba(77,150,255,0.3);">
                    <label style="font-size:13px; color:#555; font-weight:600; display:block; margin-bottom:6px;">اكتب الرابط الجديد:</label>
                    <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        <span style="font-size:13px; color:#888; direction:ltr; white-space:nowrap;">/c/</span>
                        <input id="new-link" type="text" placeholder="my-custom-link" maxlength="30"
                               style="flex:1; min-width:150px; padding:10px 12px; border:1px solid #dfe3ec; border-radius:10px; font-size:14px; direction:ltr; background:#fafbfd;">
                        <button class="btn btn-primary btn-sm" onclick="saveLink()">{{ icons.check|safe }} حفظ</button>
                        <button class="btn btn-secondary btn-sm" onclick="hideLinkEditor()">إلغاء</button>
                    </div>
                    <small style="color:#999; font-size:12px; margin-top:6px; display:block;">
                        استخدم فقط حروف إنجليزية وأرقام و _ و - (3-30 حرف)
                    </small>
                    <div id="link-alert" class="alert" style="margin-top:10px;"></div>
                </div>
            </div>

            <div class="share-box" style="text-align:right;">
                <h3 style="margin-bottom:14px;">{{ icons.user|safe }} معلومات حسابك</h3>
                <div class="info-row"><span class="info-label">{{ icons.user|safe }} الاسم:</span><span class="info-value">{{ user.name }}</span></div>
                <div class="info-row"><span class="info-label">{{ icons.star|safe }} اللقب:</span><span class="info-value">{{ user.nickname or '—' }}</span></div>
                <div class="info-row"><span class="info-label">{{ icons.user|safe }} اسم المستخدم:</span><span class="info-value" style="direction:ltr;">@{{ user.username }}</span></div>
                <div class="info-row"><span class="info-label">{{ icons.users|safe }} الجنس:</span><span class="info-value">{{ 'ذكر' if user.gender == 'male' else 'أنثى' }}</span></div>
                <div class="info-row"><span class="info-label">{{ icons.id|safe }} ID:</span><span class="info-value" style="font-family:monospace; direction:ltr;">{{ user.id }}</span></div>
                <div class="info-row"><span class="info-label">{{ icons.calendar|safe }} تاريخ التسجيل:</span><span class="info-value">{{ user.created_at[:10] }}</span></div>
            </div>

            <div class="share-box">
                <h3>{{ icons.share|safe }} شارك رابطك</h3>
                <p style="font-size:13px; color:#888;">شارك هذا الرابط لاستقبال الرسائل المجهولة</p>
                <div style="margin-top:10px;">
                    <a href="https://wa.me/?text={{ share_url }}" target="_blank" rel="noopener"
                       class="btn btn-green btn-block" style="text-align:center; padding:14px; font-size:15px;">
                        <svg viewBox="0 0 24 24" fill="currentColor" style="width:20px; height:20px;">
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                        </svg>
                        <span>مشاركة عبر واتساب</span>
                    </a>
                </div>
            </div>
        </div>
    </section>
    <script>
    function showLinkEditor() {
        document.getElementById('link-editor').style.display = 'block';
        document.getElementById('new-link').focus();
    }
    function hideLinkEditor() {
        document.getElementById('link-editor').style.display = 'none';
        document.getElementById('link-alert').className = 'alert';
    }
    function saveLink() {
        const slug = document.getElementById('new-link').value.trim();
        if (!slug) { showLinkAlert('اكتب الرابط أولاً', 'error'); return; }
        fetch('/set-link', {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'slug=' + encodeURIComponent(slug) + '&_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(d => {
            if (d.status === 'succ') {
                showLinkAlert('تم حفظ الرابط بنجاح', 'success');
                setTimeout(() => location.reload(), 800);
            } else {
                showLinkAlert(d.message || 'خطأ', 'error');
            }
        });
    }
    function toggleLink(disable) {
        if (!confirm(disable ? 'تعطيل الرابط الخاص بك؟' : 'تفعيل الرابط؟')) return;
        fetch('/toggle-link', {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'disable=' + (disable ? '1' : '0') + '&_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(d => {
            if (d.status === 'succ') location.reload();
        });
    }
    function showLinkAlert(msg, type) {
        const el = document.getElementById('link-alert');
        el.className = 'alert ' + (type === 'success' ? 'alert-success' : 'alert-error') + ' show';
        el.textContent = msg;
    }
    </script>
    """,
        user=user, avatar_url=avatar_url,
        messages_count=messages_count, replies_count=replies_count,
        days_active=days_active, share_url=share_url,
    )
    return render_page(content, page_title=f'@{username}')


@app.route('/view/<username>')
def view_profile(username):
    if not validate_username(username) or username not in users_db:
        flash('المستخدم غير موجود', 'error')
        return redirect(url_for('index'))

    user = users_db[username]
    avatar_url = get_user_avatar(user)

    msgs_count = len(messages_db.get(username, []))

    try:
        created = datetime.fromisoformat(user['created_at'])
        days_active = max(1, (datetime.now() - created).days + 1)
    except Exception:
        days_active = 1

    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:760px;">
            <div class="profile-header">
                <img class="avatar" src="{{ avatar_url }}" alt="{{ user.name }}"
                     onclick="openLightbox('{{ avatar_url }}')">
                <h2>{{ user.name }}</h2>
                <div class="username">@{{ user.username }}</div>
                {% if user.nickname %}
                <div class="nickname-badge">{{ icons.star_filled|safe }} {{ user.nickname }}</div>
                {% endif %}
                <div class="profile-actions">
                    <a href="{{ url_for('send_message', username=user.username) }}" class="btn btn-berry btn-sm">{{ icons.send|safe }} أرسل رسالة</a>
                    {% if not session.user_username %}
                        <a href="{{ url_for('signin') }}" class="btn btn-blue btn-sm">{{ icons.accounts|safe }} تسجيل الدخول</a>
                    {% endif %}
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-card"><div class="num">{{ messages_count }}</div><div class="lbl">{{ icons.messages|safe }} الرسائل</div></div>
                <div class="stat-card"><div class="num">{{ days_active }}</div><div class="lbl">{{ icons.calendar|safe }} يوم معنا</div></div>
            </div>
        </div>
    </section>
    """,
        user=user, avatar_url=avatar_url,
        messages_count=msgs_count, days_active=days_active,
    )
    return render_page(content, page_title=f'@{username}')


@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        session.clear()
        return redirect(url_for('signin'))

    if request.method == 'POST':
        name = sanitize_text(request.form.get('name') or '', 40)
        new_username = (request.form.get('username') or '').strip()
        gender = request.form.get('gender') or ''
        avatar = (request.form.get('avatar') or '').strip()

        if not validate_name(name):
            return jsonify({'status': 'error', 'message': 'اسم غير صحيح'})
        if not validate_username(new_username):
            return jsonify({'status': 'error', 'message': 'اسم مستخدم غير صحيح'})
        if new_username != username and new_username in users_db:
            return jsonify({'status': 'error', 'message': 'الاسم مستخدم'})
        if gender not in ('male', 'female'):
            return jsonify({'status': 'error', 'message': 'اختر الجنس'})

        if avatar and avatar.startswith('data:image/'):
            avatar = validate_image_data_uri(avatar)
            if not avatar:
                return jsonify({'status': 'error', 'message': 'صورة غير صالحة أو كبيرة جداً'})
        elif avatar and not (avatar in ALLOWED_AVATAR_URLS or avatar.startswith('http')):
            avatar = user.get('avatar') or AVATARS['default']

        if new_username != username:
            old_username = username
            user_data = users_db.pop(old_username)
            messages_db[new_username] = messages_db.pop(old_username, [])
            user_data['username'] = new_username
            users_db[new_username] = user_data
            ids_db[user_data['id']] = new_username
            saved = get_saved_accounts()
            if old_username in saved:
                saved[saved.index(old_username)] = new_username
                session['saved_accounts'] = saved
            username = new_username
            user = user_data
            session['user_username'] = new_username

        user['name'] = name
        user['gender'] = gender
        user['avatar'] = avatar
        user['updated_at'] = datetime.now().isoformat()
        session['user_name'] = name
        session['user_avatar'] = get_user_avatar(user)
        return jsonify({'status': 'succ', 'redirect': url_for('profile')})

    avatar_url = get_user_avatar(user)
    content = render_template_string(r"""
    <div class="form-wrapper" style="max-width:560px;">
        <h2 class="form-title">{{ icons.edit|safe }} تعديل البروفايل</h2>
        <p class="form-sub">يمكنك تعديل معلوماتك وصورتك</p>
        <div id="edit-alert" class="alert"></div>
        <form id="edit-form">
            <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">

            <div class="form-group">
                <label>{{ icons.camera|safe }} الصورة الشخصية</label>
                <div class="avatar-picker">
                    <img id="avatar-preview" src="{{ avatar_url }}" alt="avatar"
                         onclick="openLightbox(this.src)" style="cursor:zoom-in;">
                    <div class="avatar-options">
                        <img src="{{ avatars.male }}" data-url="{{ avatars.male }}" onclick="selectAvatar('{{ avatars.male }}')" title="ذكر" {% if user.avatar == avatars.male %}class="selected"{% endif %}>
                        <img src="{{ avatars.female }}" data-url="{{ avatars.female }}" onclick="selectAvatar('{{ avatars.female }}')" title="أنثى" {% if user.avatar == avatars.female %}class="selected"{% endif %}>
                        <img src="{{ avatars.default }}" data-url="{{ avatars.default }}" onclick="selectAvatar('{{ avatars.default }}')" title="افتراضي" {% if user.avatar == avatars.default or not user.avatar %}class="selected"{% endif %}>
                    </div>
                </div>
                <input type="hidden" name="avatar" id="avatar-url" value="{{ user.avatar or avatars.default }}">

                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                    <label class="file-upload" style="flex:1; min-width:200px;">
                        <input type="file" accept="image/*" onchange="handleFileUpload(this)">
                        <div class="upload-icon">{{ icons.upload|safe }}</div>
                        <div class="upload-text">
                            <b>ارفع صورة من جهازك</b>
                            <small>سيتم ضغطها تلقائياً</small>
                        </div>
                    </label>
                    {% if user.avatar and user.avatar not in avatars.values() %}
                    <button type="button" class="btn btn-red btn-sm" onclick="removeAvatar()" style="align-self:center;">
                        {{ icons.trash|safe }} حذف الصورة
                    </button>
                    {% endif %}
                </div>
            </div>

            <div class="form-group">
                <label>{{ icons.user|safe }} الاسم الكامل</label>
                <input type="text" name="name" value="{{ user.name }}" required maxlength="40">
            </div>
            <div class="form-group">
                <label>{{ icons.id|safe }} اسم المستخدم</label>
                <input type="text" name="username" value="{{ user.username }}" required pattern="[a-zA-Z0-9_]{3,20}" style="direction: ltr;" maxlength="20">
            </div>
            <div class="form-group">
                <label>{{ icons.users|safe }} الجنس</label>
                <select name="gender" required>
                    <option value="male" {% if user.gender == 'male' %}selected{% endif %}>ذكر</option>
                    <option value="female" {% if user.gender == 'female' %}selected{% endif %}>أنثى</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary btn-block">{{ icons.check|safe }} حفظ التعديلات</button>
        </form>
        <div class="form-sub" style="margin-top:18px; margin-bottom:0;">
            <a href="{{ url_for('profile') }}"><b>{{ icons.arrow_left|safe }} رجوع</b></a>
        </div>
    </div>
    <script>
    function selectAvatar(url) {
        document.getElementById('avatar-url').value = url;
        document.getElementById('avatar-preview').src = url;
        document.querySelectorAll('.avatar-options img').forEach(img => {
            img.classList.toggle('selected', img.dataset.url === url);
        });
    }
    function handleFileUpload(input) {
        const file = input.files[0];
        if (!file) return;
        if (!file.type.startsWith('image/')) { alert('الرجاء اختيار صورة'); input.value = ''; return; }
        if (file.size > 20 * 1024 * 1024) { alert('حجم الصورة كبير'); input.value = ''; return; }
        const reader = new FileReader();
        reader.onload = e => {
            const img = new Image();
            img.onload = () => {
                const MAX_DIM = 1200;
                let { width, height } = img;
                if (width > MAX_DIM || height > MAX_DIM) {
                    if (width > height) { height = Math.round(height * MAX_DIM / width); width = MAX_DIM; }
                    else { width = Math.round(width * MAX_DIM / height); height = MAX_DIM; }
                }
                const canvas = document.createElement('canvas');
                canvas.width = width; canvas.height = height;
                canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                const dataUri = canvas.toDataURL('image/jpeg', 0.85);
                if (dataUri.length > 5_500_000) { alert('الصورة كبيرة جداً'); input.value = ''; return; }
                document.getElementById('avatar-url').value = dataUri;
                document.getElementById('avatar-preview').src = dataUri;
                document.querySelectorAll('.avatar-options img').forEach(im => im.classList.remove('selected'));
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
    function removeAvatar() {
        if (!confirm('حذف الصورة الشخصية والعودة للصورة الافتراضية؟')) return;
        document.getElementById('avatar-url').value = '{{ avatars.default }}';
        document.getElementById('avatar-preview').src = '{{ avatars.default }}';
        document.querySelectorAll('.avatar-options img').forEach(im => {
            im.classList.toggle('selected', im.dataset.url === '{{ avatars.default }}');
        });
    }
    document.getElementById('edit-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const fd = new FormData(this);
        fd.append('_csrf_token', CSRF_TOKEN);
        const alertBox = document.getElementById('edit-alert');
        alertBox.className = 'alert';
        fetch('/edit', { method: 'POST', body: fd, credentials: 'same-origin' })
            .then(r => r.json())
            .then(d => {
                if (d.status === 'succ') {
                    alertBox.className = 'alert alert-success show';
                    alertBox.textContent = 'تم الحفظ بنجاح!';
                    setTimeout(() => window.location.href = d.redirect || '/profile', 800);
                } else {
                    alertBox.className = 'alert alert-error show';
                    alertBox.textContent = d.message || 'خطأ';
                }
            })
            .catch(() => {
                alertBox.className = 'alert alert-error show';
                alertBox.textContent = 'خطأ في الاتصال';
            });
    });
    </script>
    """, user=user, avatar_url=avatar_url)
    return render_page(content, page_title='تعديل البروفايل')


@app.route('/nickname')
@login_required
def nickname_page():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        session.clear()
        return redirect(url_for('signin'))

    content = render_template_string(r"""
    <div class="form-wrapper" style="max-width:580px;">
        <h2 class="form-title">{{ icons.star|safe }} اختر لقبك</h2>
        <p class="form-sub">سيظهر اللقب بجانب اسمك في صفحتك وفي قسم رسائلنا</p>
        <div id="nick-alert" class="alert"></div>
        <form id="nick-form">
            <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
            <div class="form-group">
                <label>اللقب (اختياري)</label>
                <input type="text" name="nickname" id="nickname-input" value="{{ user.nickname or '' }}"
                       placeholder="اكتب لقبك أو اختر من الأسفل" maxlength="20"
                       style="text-align:center; font-size:16px; font-weight:700;">
            </div>
            <div style="margin-bottom:16px;">
                <label style="font-size:13px; color:#888; display:block; margin-bottom:6px;">أو اختر لقباً جاهزاً:</label>
                <div class="nickname-presets" id="presets">
                    {% for p in nickname_presets %}
                    <button type="button" onclick="selectNick('{{ p }}', this)"
                            {% if user.nickname == p %}class="selected"{% endif %}>{{ p }}</button>
                    {% endfor %}
                </div>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button type="submit" class="btn btn-gold" style="flex:1; min-width:150px;">{{ icons.check|safe }} حفظ اللقب</button>
                {% if user.nickname %}
                <button type="button" class="btn btn-red" onclick="removeNick()">{{ icons.trash|safe }} إزالة اللقب</button>
                {% endif %}
            </div>
        </form>
        <div class="form-sub" style="margin-top:18px; margin-bottom:0;">
            <a href="{{ url_for('profile') }}"><b>{{ icons.arrow_left|safe }} رجوع للبروفايل</b></a>
        </div>
    </div>
    <script>
    function selectNick(nick, btn) {
        document.getElementById('nickname-input').value = nick;
        document.querySelectorAll('#presets button').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
    }
    document.getElementById('nick-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const nick = document.getElementById('nickname-input').value.trim();
        fetch('/set-nickname', {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'nickname=' + encodeURIComponent(nick) + '&_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(d => {
            const a = document.getElementById('nick-alert');
            if (d.status === 'succ') {
                a.className = 'alert alert-success show';
                a.textContent = 'تم حفظ اللقب بنجاح!';
                setTimeout(() => window.location.href = '/profile', 800);
            } else {
                a.className = 'alert alert-error show';
                a.textContent = d.message || 'خطأ';
            }
        });
    });
    function removeNick() {
        if (!confirm('إزالة اللقب؟')) return;
        fetch('/set-nickname', {
            method: 'POST',
            headers: {'X-CSRF-Token': CSRF_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'nickname=&_csrf_token=' + encodeURIComponent(CSRF_TOKEN),
            credentials: 'same-origin'
        }).then(r => r.json()).then(d => { if (d.status === 'succ') location.reload(); });
    }
    </script>
    """, user=user)
    return render_page(content, page_title='اختر لقبك')


@app.route('/set-nickname', methods=['POST'])
@login_required
def set_nickname():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        return jsonify({'status': 'error', 'message': 'المستخدم غير موجود'})
    nickname = (request.form.get('nickname') or '').strip()
    if nickname and not validate_nickname(nickname):
        return jsonify({'status': 'error', 'message': 'اللقب غير صالح (1-20 حرف)'})
    user['nickname'] = nickname
    user['updated_at'] = datetime.now().isoformat()
    return jsonify({'status': 'succ'})


@app.route('/set-link', methods=['POST'])
@login_required
def set_custom_link():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        return jsonify({'status': 'error', 'message': 'المستخدم غير موجود'})
    slug = (request.form.get('slug') or '').strip().lower()
    if not validate_slug(slug):
        return jsonify({'status': 'error', 'message': 'الرابط غير صالح'})
    for u, data in users_db.items():
        if data.get('custom_slug') == slug and u != username:
            return jsonify({'status': 'error', 'message': 'هذا الرابط مستخدم'})
    user['custom_slug'] = slug
    user['updated_at'] = datetime.now().isoformat()
    return jsonify({'status': 'succ'})


@app.route('/toggle-link', methods=['POST'])
@login_required
def toggle_custom_link():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        return jsonify({'status': 'error', 'message': 'المستخدم غير موجود'})
    disable = request.form.get('disable') == '1'
    user['link_disabled'] = disable
    user['updated_at'] = datetime.now().isoformat()
    return jsonify({'status': 'succ'})


@app.route('/messages')
@login_required
def messages():
    username = session['user_username']
    user = users_db.get(username)
    if not user:
        session.clear()
        return redirect(url_for('signin'))

    msgs = messages_db.get(username, [])
    slug = user.get('custom_slug') or user['username']
    share_url = f"{request.host_url.rstrip('/')}/c/{slug}"

    content = render_template_string(r"""
    <section class="section">
        <div class="container">
            <h2 class="section-title">{{ icons.inbox|safe }} رسائلك الواردة</h2>
            <div class="share-box">
                <h3>{{ icons.link|safe }} رابطك الخاص</h3>
                <div class="share-row">
                    <input id="share-link" type="text" value="{{ share_url }}" readonly onclick="this.select();">
                    <button onclick="copyBtn(this, '{{ share_url }}')">{{ icons.copy|safe }} نسخ</button>
                </div>
            </div>
            {% if messages %}
                {% for m in messages %}
                <div class="msg-card" id="msg-{{ m.id }}">
                    {% set imgs = m.images if m.images else ([m.image] if m.image else []) %}
                    {% if imgs %}
                    <div class="pub-images-grid" style="margin-bottom:12px;">
                        {% for img in imgs %}
                        <img src="{{ img }}" alt="صورة مرفقة"
                             onclick="openLightbox(this.src)">
                        {% endfor %}
                    </div>
                    {% endif %}
                    {% if m.content %}
                    <div class="msg-content">{{ m.content }}</div>
                    {% endif %}
                    <div class="msg-meta">{{ icons.calendar|safe }} {{ m.created_at }}</div>
                    {% if m.replied %}
                        <div class="msg-reply">{{ icons.reply|safe }} <div><b>ردك:</b> {{ m.reply }}</div></div>
                    {% else %}
                        <div class="reply-form">
                            <input id="reply-input-{{ m.id }}" type="text" placeholder="اكتب ردك..." maxlength="500">
                            <button onclick="replyMessage('{{ m.id }}');">{{ icons.reply|safe }} رد</button>
                        </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>
                    <p>لا توجد رسائل بعد</p>
                </div>
            {% endif %}
        </div>
    </section>
    """, messages=msgs, share_url=share_url)
    return render_page(content, page_title='رسائلي')


@app.route('/reply/<msg_id>', methods=['POST'])
@login_required
def reply_message(msg_id):
    if not re.match(r'^[a-f0-9]{12}$', msg_id or ''):
        return jsonify({'status': 'error', 'message': 'معرّف غير صالح'})
    username = session['user_username']
    reply_text = sanitize_text(request.form.get('reply') or '', 500)
    if not reply_text:
        return jsonify({'status': 'error', 'message': 'الرد فارغ'})
    for m in messages_db.get(username, []):
        if m['id'] == msg_id:
            m['replied'] = True
            m['reply'] = reply_text
            return jsonify({'status': 'succ', 'reply': reply_text})
    return jsonify({'status': 'error', 'message': 'الرسالة غير موجودة'})


# ============================================================
# ⭐ قسم رسائلنا (Public Messages) - مشاهدة فقط
# ============================================================
@app.route('/public-messages')
def public_messages():
    public_msgs = []
    for recipient_username, msgs in messages_db.items():
        recipient = users_db.get(recipient_username)
        if not recipient:
            continue
        for m in msgs:
            sender_username = m.get('sender')
            reveal_type = m.get('reveal_type', 'anonymous')
            sender_data = None

            if sender_username and sender_username in users_db:
                sender = users_db[sender_username]
                if reveal_type == 'profile':
                    sender_data = {
                        'username': sender_username,
                        'name': sender['name'],
                        'nickname': sender.get('nickname', ''),
                        'avatar': get_user_avatar(sender),
                        'id': sender['id'],
                        'display_type': 'profile',
                    }
                elif reveal_type == 'nickname':
                    sender_data = {
                        'username': sender_username,
                        'name': sender.get('nickname') or 'مستخدم',
                        'nickname': sender.get('nickname', ''),
                        'avatar': None,
                        'id': None,
                        'display_type': 'nickname',
                    }

            imgs = m.get('images') or ([m['image']] if m.get('image') else [])

            public_msgs.append({
                'id': m['id'],
                'content': m['content'],
                'images': imgs,
                'created_at': m['created_at'],
                'replied': m.get('replied', False),
                'reply': m.get('reply'),
                'reveal_type': reveal_type,
                'sender': sender_data,
                'recipient': {
                    'username': recipient_username,
                    'name': recipient['name'],
                    'nickname': recipient.get('nickname', ''),
                    'avatar': get_user_avatar(recipient),
                    'id': recipient['id'],
                },
            })

    public_msgs.sort(key=lambda x: x['created_at'], reverse=True)
    total = len(public_msgs)
    public_count = sum(1 for m in public_msgs if m['reveal_type'] == 'profile')
    nick_count = sum(1 for m in public_msgs if m['reveal_type'] == 'nickname')
    anon_count = sum(1 for m in public_msgs if m['reveal_type'] == 'anonymous')

    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:880px;">
            <h2 class="section-title">{{ icons.public_messages|safe }} رسائلنا العامة ({{ total }})</h2>
            <p style="text-align:center; color:#888; font-size:14px; margin-bottom:20px;">
                جميع الرسائل المرسلة في الموقع — مشاهدة فقط
            </p>

            <div class="pub-filters">
                <button class="pub-filter-btn active" onclick="filterPublicMessages('all', this)">
                    {{ icons.public_messages|safe }} الكل ({{ total }})
                </button>
                <button class="pub-filter-btn" onclick="filterPublicMessages('profile', this)">
                    {{ icons.user|safe }} بروفايل ({{ public_count }})
                </button>
                <button class="pub-filter-btn" onclick="filterPublicMessages('nickname', this)">
                    {{ icons.star|safe }} لقب ({{ nick_count }})
                </button>
                <button class="pub-filter-btn" onclick="filterPublicMessages('anonymous', this)">
                    {{ icons.lock|safe }} مجهول ({{ anon_count }})
                </button>
            </div>

            {% if messages %}
            <div class="pub-timeline">
                {% for m in messages %}
                <div class="pub-card" data-tags="{{ m.reveal_type }}">
                    <div class="pub-header">
                        {% if m.reveal_type == 'profile' and m.sender %}
                            <a href="{{ url_for('view_profile', username=m.sender.username) }}" style="text-decoration:none;">
                                <img src="{{ m.sender.avatar }}" alt="{{ m.sender.name }}" class="pub-avatar">
                            </a>
                        {% elif m.reveal_type == 'nickname' and m.sender %}
                            <div class="pub-avatar-anon">{{ icons.star|safe }}</div>
                        {% else %}
                            <div class="pub-avatar-anon">{{ icons.lock|safe }}</div>
                        {% endif %}

                        <div class="pub-users">
                            <div class="pub-user">
                                {% if m.reveal_type == 'profile' and m.sender %}
                                    <img src="{{ m.sender.avatar }}" alt="" class="pub-user-avatar">
                                    <div class="pub-user-info">
                                        <span class="pub-user-name">{{ m.sender.name }}</span>
                                        {% if m.sender.nickname %}
                                        <span class="pub-user-nick">{{ icons.star_filled|safe }} {{ m.sender.nickname }}</span>
                                        {% endif %}
                                        <span class="pub-user-sub">@{{ m.sender.username }} · #{{ m.sender.id }}</span>
                                    </div>
                                {% elif m.reveal_type == 'nickname' and m.sender %}
                                    <div class="pub-user-avatar-anon">{{ icons.star|safe }}</div>
                                    <div class="pub-user-info">
                                        <span class="pub-user-name">{{ m.sender.nickname or 'مستخدم' }}</span>
                                        <span class="pub-user-sub" style="color:#d97706;">كشف اللقب فقط</span>
                                    </div>
                                {% else %}
                                    <div class="pub-user-avatar-anon">{{ icons.lock|safe }}</div>
                                    <div class="pub-user-info">
                                        <span class="pub-user-name">مجهول</span>
                                        <span class="pub-user-sub">مرسل مجهول الهوية</span>
                                    </div>
                                {% endif %}
                            </div>

                            <div class="pub-arrow">→</div>

                            <div class="pub-user">
                                <img src="{{ m.recipient.avatar }}" alt="" class="pub-user-avatar">
                                <div class="pub-user-info">
                                    <a href="{{ url_for('view_profile', username=m.recipient.username) }}" style="text-decoration:none;">
                                        <span class="pub-user-name">{{ m.recipient.name }}</span>
                                    </a>
                                    {% if m.recipient.nickname %}
                                    <span class="pub-user-nick">{{ icons.star_filled|safe }} {{ m.recipient.nickname }}</span>
                                    {% endif %}
                                    <span class="pub-user-sub">@{{ m.recipient.username }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {% if m.images %}
                    <div class="pub-images-grid">
                        {% for img in m.images %}
                        <img src="{{ img }}" alt="صورة مرفقة"
                             onclick="openLightbox(this.src)">
                        {% endfor %}
                    </div>
                    {% endif %}

                    {% if m.content %}
                    <div class="pub-content">{{ m.content }}</div>
                    {% endif %}

                    <div class="pub-footer">
                        <div class="pub-date">
                            {{ icons.calendar|safe }} {{ m.created_at }}
                        </div>
                        <div class="pub-tags">
                            {% if m.reveal_type == 'profile' %}
                            <span class="pub-tag tag-public">{{ icons.user|safe }} كشف البروفايل</span>
                            {% elif m.reveal_type == 'nickname' %}
                            <span class="pub-tag tag-nick">{{ icons.star|safe }} كشف اللقب</span>
                            {% else %}
                            <span class="pub-tag tag-anon">{{ icons.lock|safe }} مجهول</span>
                            {% endif %}
                            {% if m.replied %}
                            <span class="pub-tag tag-public">{{ icons.reply|safe }} تم الرد</span>
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                <p>لا توجد رسائل عامة بعد</p>
                <a href="{{ url_for('index') }}" class="btn btn-teal" style="margin-top:14px;">ابدأ بإرسال رسالة</a>
            </div>
            {% endif %}
        </div>
    </section>
    """, messages=public_msgs, total=total,
         public_count=public_count, nick_count=nick_count, anon_count=anon_count)
    return render_page(content, page_title=f'رسائلنا العامة ({total})')


@app.route('/c/<slug>', methods=['GET', 'POST'])
def custom_link(slug):
    if not validate_slug(slug):
        flash('الرابط غير صالح', 'error')
        return redirect(url_for('index'))
    target_username = None
    for u, data in users_db.items():
        if data.get('custom_slug') == slug:
            target_username = u
            break
    if not target_username:
        flash('الرابط غير موجود', 'error')
        return redirect(url_for('index'))
    user = users_db[target_username]
    if user.get('link_disabled'):
        flash('هذا الرابط معطّل حالياً', 'warning')
        return redirect(url_for('index'))
    return _handle_send_message(target_username, user)


@app.route('/u/<username>', methods=['GET', 'POST'])
def send_message(username):
    if not validate_username(username) or username not in users_db:
        flash('الرابط غير موجود', 'error')
        return redirect(url_for('index'))
    user = users_db[username]
    return _handle_send_message(username, user)


def _handle_send_message(username, user):
    if request.method == 'POST':
        content_text = sanitize_text(request.form.get('content') or '', 1000)
        reveal_type = request.form.get('reveal_type') or ''

        # ✅ استقبال حتى 5 صور (JSON array)
        images_raw = request.form.get('message_images') or '[]'
        try:
            images_list = json.loads(images_raw)
        except Exception:
            images_list = []
        images_list = validate_message_images(images_list)

        if reveal_type not in ('profile', 'nickname', 'anonymous'):
            flash('يجب اختيار طريقة إظهار هويتك (إجباري)', 'warning')
            return redirect(request.path)

        # يجب أن يكون هناك نص أو صورة واحدة على الأقل
        if not content_text and not images_list:
            flash('الرجاء كتابة رسالة أو إرفاق صورة على الأقل', 'warning')
            return redirect(request.path)

        sender_username = session.get('user_username')

        if reveal_type in ('profile', 'nickname') and not sender_username:
            flash('يجب تسجيل الدخول لكشف البروفايل أو اللقب', 'warning')
            return redirect(request.path)

        if reveal_type == 'nickname':
            sender_user = users_db.get(sender_username)
            if not sender_user or not sender_user.get('nickname'):
                flash('يجب تعيين لقب أولاً من صفحة "اللقب"', 'warning')
                return redirect(url_for('nickname_page'))

        msg_record = {
            'id': secrets.token_hex(6),
            'content': content_text,
            'images': images_list,
            'image': images_list[0] if images_list else '',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'replied': False,
            'reply': None,
            'sender': sender_username if reveal_type in ('profile', 'nickname') else None,
            'reveal_type': reveal_type,
        }

        messages_db.setdefault(username, []).append(msg_record)
        flash('تم إرسال رسالتك!', 'success')
        return redirect(request.path)

    content = render_template_string(r"""
    <div class="form-wrapper" style="max-width:600px;">
        <div style="text-align:center; margin-bottom:20px;">
            <img src="{{ owner_avatar }}" alt="{{ username }}" style="width:80px; height:80px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 6px 20px rgba(0,0,0,0.12);">
        </div>
        <h2 class="form-title">{{ icons.send|safe }} أرسل رسالة</h2>
        <p class="form-sub">إلى @{{ username }}</p>

        <form method="POST" id="send-form">
            <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">

            <div class="form-group">
                <label style="font-weight:700; color:#2d2f31; font-size:15px;">
                    {{ icons.shield|safe }} اختر طريقة إظهار هويتك <span style="color:#e74c3c;">*</span>
                </label>
                <div class="reveal-choices">
                    <label class="reveal-choice" data-value="profile">
                        <input type="radio" name="reveal_type" value="profile" required>
                        <div class="rc-icon rc-public">{{ icons.user|safe }}</div>
                        <div class="rc-title">كشف البروفايل</div>
                        <div class="rc-desc">سيظهر اسمك وصورتك ورابط بروفايلك للمستلم</div>
                    </label>
                    <label class="reveal-choice" data-value="nickname">
                        <input type="radio" name="reveal_type" value="nickname" required>
                        <div class="rc-icon rc-nick">{{ icons.star|safe }}</div>
                        <div class="rc-title">كشف اللقب فقط</div>
                        <div class="rc-desc">سيظهر لقبك فقط بدون بروفايلك</div>
                    </label>
                    <label class="reveal-choice" data-value="anonymous">
                        <input type="radio" name="reveal_type" value="anonymous" required>
                        <div class="rc-icon rc-anon">{{ icons.lock|safe }}</div>
                        <div class="rc-title">مجهول</div>
                        <div class="rc-desc">لن تظهر أي معلومات عنك</div>
                    </label>
                </div>
            </div>

            <div class="form-group">
                <label>{{ icons.messages|safe }} نص الرسالة <small style="color:#999;">(اختياري إذا أرفقت صورة)</small></label>
                <textarea name="content" placeholder="اكتب رسالتك..." maxlength="1000" style="min-height:120px;"></textarea>
            </div>

            {# ✅ قسم إرفاق حتى 5 صور #}
            <div class="form-group">
                <label>
                    {{ icons.images|safe }} إرفاق صور
                    <small style="color:#999;">(اختياري — حتى 5 صور)</small>
                </label>
                <input type="hidden" name="message_images" id="message-images-data" value="[]">

                <label class="file-upload" id="upload-label" style="cursor:pointer;">
                    <input type="file" accept="image/*" multiple onchange="handleMessageImages(this)">
                    <div class="upload-icon">{{ icons.upload|safe }}</div>
                    <div class="upload-text">
                        <b>اضغط لاختيار صور (يمكن اختيار عدة صور)</b>
                        <small>JPG / PNG / WEBP / GIF — حتى 5 صور</small>
                    </div>
                </label>

                <div id="images-preview-grid" class="msg-images-grid"></div>

                <div id="images-counter" style="display:none; margin-top:10px; text-align:center; font-size:13px; font-weight:700; color:#b95cff;"></div>
            </div>

            <button type="submit" class="btn btn-berry btn-block">{{ icons.send|safe }} إرسال</button>
        </form>

        <div class="form-sub" style="margin-top:18px; margin-bottom:0; font-size:12px;">
            ستظهر رسالتك في <a href="{{ url_for('public_messages') }}"><b>قسم رسائلنا</b></a>
        </div>
    </div>
    <script>
    const MAX_IMAGES = 5;
    let currentImages = [];

    document.querySelectorAll('.reveal-choice').forEach(choice => {
        const radio = choice.querySelector('input[type="radio"]');
        radio.addEventListener('change', () => {
            document.querySelectorAll('.reveal-choice').forEach(c => c.classList.remove('selected'));
            if (radio.checked) choice.classList.add('selected');
        });
        choice.addEventListener('click', (e) => {
            if (e.target.tagName !== 'INPUT') {
                radio.checked = true;
                radio.dispatchEvent(new Event('change'));
            }
        });
    });

    function handleMessageImages(input) {
        const files = Array.from(input.files || []);
        if (!files.length) return;

        const remaining = MAX_IMAGES - currentImages.length;
        if (remaining <= 0) {
            alert('الحد الأقصى ' + MAX_IMAGES + ' صور');
            input.value = '';
            return;
        }

        const toProcess = files.slice(0, remaining);
        if (files.length > remaining) {
            alert('سيتم إضافة ' + remaining + ' صور فقط (الحد ' + MAX_IMAGES + ')');
        }

        let processed = 0;
        toProcess.forEach(file => {
            if (!file.type.startsWith('image/')) {
                processed++;
                if (processed === toProcess.length) finalize(input);
                return;
            }
            if (file.size > 15 * 1024 * 1024) {
                alert('صورة كبيرة جداً: ' + file.name);
                processed++;
                if (processed === toProcess.length) finalize(input);
                return;
            }
            compressImage(file, dataUri => {
                if (dataUri) currentImages.push(dataUri);
                processed++;
                if (processed === toProcess.length) finalize(input);
            });
        });
    }

    function compressImage(file, callback) {
        const reader = new FileReader();
        reader.onload = e => {
            const img = new Image();
            img.onload = () => {
                const MAX_DIM = 1400;
                let { width, height } = img;
                if (width > MAX_DIM || height > MAX_DIM) {
                    if (width > height) {
                        height = Math.round(height * MAX_DIM / width);
                        width = MAX_DIM;
                    } else {
                        width = Math.round(width * MAX_DIM / height);
                        height = MAX_DIM;
                    }
                }
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                const dataUri = canvas.toDataURL('image/jpeg', 0.82);
                if (dataUri.length > 3_500_000) {
                    alert('الصورة كبيرة جداً بعد الضغط: ' + file.name);
                    callback(null);
                    return;
                }
                callback(dataUri);
            };
            img.onerror = () => callback(null);
            img.src = e.target.result;
        };
        reader.onerror = () => callback(null);
        reader.readAsDataURL(file);
    }

    function finalize(input) {
        input.value = '';
        renderImagePreviews();
        document.getElementById('message-images-data').value = JSON.stringify(currentImages);
    }

    function renderImagePreviews() {
        const grid = document.getElementById('images-preview-grid');
        const counter = document.getElementById('images-counter');
        grid.innerHTML = '';

        currentImages.forEach((src, index) => {
            const wrap = document.createElement('div');
            wrap.className = 'msg-image-item';
            wrap.innerHTML = `
                <img src="${src}" onclick="openLightbox('${src}')">
                <button type="button" class="msg-image-remove" onclick="removeImageAt(${index})">×</button>
                <span class="msg-image-index">${index+1}</span>
            `;
            grid.appendChild(wrap);
        });

        if (currentImages.length > 0) {
            counter.style.display = 'block';
            counter.textContent = 'عدد الصور المرفقة: ' + currentImages.length + ' / ' + MAX_IMAGES;
        } else {
            counter.style.display = 'none';
        }
    }

    function removeImageAt(index) {
        currentImages.splice(index, 1);
        document.getElementById('message-images-data').value = JSON.stringify(currentImages);
        renderImagePreviews();
    }
    </script>
    """, username=username, owner_avatar=get_user_avatar(user))
    return render_page(content, page_title=f'إرسال رسالة إلى @{username}')


@app.route('/accounts')
@login_required
def accounts():
    accounts_list = load_saved_accounts_data()
    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:700px;">
            <h2 class="section-title">{{ icons.accounts|safe }} إدارة الحسابات</h2>
            <div class="accounts-box">
                <h3>{{ icons.accounts|safe }} الحساب المحفوظ</h3>
                <div class="accounts-list">
                    {% for acc in accounts %}
                    <div class="account-item {% if acc.is_current %}current{% endif %}">
                        <img src="{{ acc.avatar }}" alt="{{ acc.name }}">
                        <div class="acc-info">
                            <div class="acc-name">{{ acc.name }}
                                {% if acc.is_current %}<span style="color:#22a04d; font-size:12px;">(الحالي)</span>{% endif %}
                            </div>
                            <div class="acc-user">@{{ acc.username }} · #{{ acc.id }}</div>
                        </div>
                        <div class="acc-actions">
                            {% if not acc.is_current %}
                            <button class="acc-switch" onclick="switchAccount('{{ acc.username }}')">تبديل</button>
                            {% endif %}
                            <button class="acc-remove" onclick="removeAccount('{{ acc.username }}')">إزالة</button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            <div style="text-align:center; margin-top:24px;">
                <a href="{{ url_for('profile') }}" class="btn btn-secondary">{{ icons.arrow_left|safe }} رجوع للبروفايل</a>
            </div>
        </div>
    </section>
    """, accounts=accounts_list)
    return render_page(content, page_title='إدارة الحسابات')


@app.route('/accounts/switch/<username>', methods=['POST'])
def accounts_switch(username):
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': 'اسم غير صالح'})
    if username not in get_saved_accounts():
        return jsonify({'status': 'error', 'message': 'الحساب غير محفوظ'})
    if switch_account(username):
        flash(f'تم التبديل إلى @{username}', 'success')
        return jsonify({'status': 'succ'})
    return jsonify({'status': 'error', 'message': 'فشل التبديل'})


@app.route('/accounts/remove/<username>', methods=['POST'])
def accounts_remove(username):
    if not validate_username(username):
        return jsonify({'status': 'error', 'message': 'اسم غير صالح'})
    remove_saved_account(username)
    if session.get('user_username') == username:
        session.pop('user_username', None)
        session.pop('user_name', None)
        session.pop('user_id', None)
        session.pop('user_avatar', None)
    return jsonify({'status': 'succ'})


@app.route('/help')
def help_page():
    content = render_template_string(r"""
    <section class="section">
        <div class="container" style="max-width:800px;">
            <h2 class="section-title">{{ icons.help|safe }} التعليمات</h2>
            <div class="form-wrapper" style="max-width:100%; margin:0;">
                <h3 style="color:#b95cff; display:flex; align-items:center; gap:8px;">{{ icons.user|safe }} كيف أسجل؟</h3>
                <p>اضغط على "تسجيل Google" ثم اختر حساب Google الخاص بك.</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.public_messages|safe }} ما هو قسم "رسائلنا"؟</h3>
                <p>قسم عام يعرض جميع الرسائل المرسلة في الموقع (مشاهدة فقط). يمكنك رؤية من أرسل لمن، وطريقة إظهار الهوية (بروفايل / لقب / مجهول).</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.shield|safe }} ما خيارات إظهار الهوية عند الإرسال؟</h3>
                <p>عند إرسال رسالة، يجب اختيار واحد من: <b>كشف البروفايل</b> (يظهر اسمك وصورتك ورابطك)، <b>كشف اللقب فقط</b> (يظهر لقبك فقط)، أو <b>مجهول</b> (لا تظهر أي معلومات).</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.images|safe }} كيف أرسل صوراً مع رسالتي؟</h3>
                <p>عند إرسال رسالة، يمكنك إرفاق <b>حتى 5 صور</b> (اختياري). يمكنك إرسال نص فقط، أو صور فقط، أو نص + صور. اضغط على "اختيار صور" واختر حتى 5 صور من جهازك.</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.star|safe }} كيف أختار لقباً؟</h3>
                <p>اذهب لصفحة "اللقب" من القائمة العلوية، واختر لقباً جاهزاً أو اكتب لقبك الخاص.</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.link|safe }} كيف أغيّر رابطي الخاص؟</h3>
                <p>من صفحة بروفايلك، اضغط "تغيير الرابط" في قسم "رابطك المخصص"، واكتب الرابط الجديد.</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.camera|safe }} كيف أغير صورتي؟</h3>
                <p>من صفحة "تعديل"، اختر صورة جاهزة أو ارفع صورة من جهازك.</p>

                <h3 style="color:#b95cff; margin-top:20px; display:flex; align-items:center; gap:8px;">{{ icons.share|safe }} كيف أنشر رابطي؟</h3>
                <p>من صفحة بروفايلك، انسخ الرابط وشاركه عبر واتساب مباشرة.</p>
            </div>
        </div>
    </section>
    """)
    return render_page(content, page_title='التعليمات')


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(413)
def too_large(e):
    flash('حجم الملف كبير جداً. الحد الأقصى 25MB', 'error')
    return redirect(request.referrer or url_for('index'))


@app.errorhandler(404)
def not_found(e):
    error_content = r"""
    <div class="empty" style="padding:80px 20px;">
        <h1 style="font-size:80px; color:#b95cff; margin-bottom:10px;">404</h1>
        <p style="font-size:18px; color:#666; margin-bottom:20px;">الصفحة غير موجودة</p>
        <a href="/" class="btn btn-blue" style="margin-top:15px;">العودة للرئيسية</a>
    </div>
    """
    return render_page(error_content, page_title='404 - الصفحة غير موجودة'), 404


@app.errorhandler(500)
def server_error(e):
    security_logger.error(f'500 error: {e}')
    error_content = r"""
    <div class="empty" style="padding:80px 20px;">
        <h1 style="font-size:80px; color:#e74c3c; margin-bottom:10px;">500</h1>
        <p style="font-size:18px; color:#666; margin-bottom:20px;">حدث خطأ في الخادم</p>
        <a href="/" class="btn btn-blue" style="margin-top:15px;">العودة للرئيسية</a>
    </div>
    """
    return render_page(error_content, page_title='500 - خطأ في الخادم'), 500


# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("✓ تطبيق خليك واضح v4.1 يعمل على:")
    print("   🌐 http://localhost:5000")
    print("=" * 60)
    print("✨ الميزات الجديدة في v4.1:")
    print("   • إرسال حتى 5 صور مع الرسالة (اختياري)")
    print("   • نص فقط / صور فقط / نص + صور")
    print("   • معاينة مباشرة + ضغط تلقائي + إمكانية الحذف")
    print("   • قسم ثالث في الرئيسية: أحدث الرسائل العامة")
    print("   • عرض الصور في رسائلي + رسائلنا + الرئيسية")
    print("=" * 60)
    print("⚠️  في Google Console أضف:")
    print(f"   {GOOGLE_REDIRECT_URI}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
