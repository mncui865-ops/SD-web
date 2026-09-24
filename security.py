# -*- coding: utf-8 -*-
"""
============================================================
🛡️ security.py - وحدة الحماية الشاملة
============================================================
توفر هذه الوحدة:
- Rate Limiting متقدم
- CSRF Protection
- XSS Filtering
- Security Headers (CSP, HSTS, etc.)
- Bot Detection (Honeypot)
- Input Sanitization
- Suspicious Pattern Detection
- Session Security
- Logging أمني
============================================================
"""

import re
import time
import secrets
import logging
import hashlib
from functools import wraps
from flask import request, session, jsonify, abort, redirect, url_for, flash

# ============================================================
# 🔧 الإعدادات القابلة للتخصيص
# ============================================================
CONFIG = {
    # Rate Limiting
    'RATE_LIMIT_GLOBAL': 180,        # طلبات/دقيقة لكل IP
    'RATE_LIMIT_SEND': 5,            # رسائل/دقيقة لكل IP
    'RATE_LIMIT_REPLY': 20,          # ردود/دقيقة لكل IP
    'RATE_LIMIT_LOGIN': 10,          # محاولات دخول/5 دقائق
    'RATE_LIMIT_API': 60,            # طلبات API/دقيقة
    'RATE_LIMIT_WINDOW': 60,         # النافذة الزمنية بالثواني

    # Security
    'MAX_CONTENT_LENGTH': 25 * 1024 * 1024,  # 25MB
    'MAX_URL_LENGTH': 2048,          # حد طول URL
    'MAX_JSON_SIZE': 100 * 1024,     # 100KB للـ JSON
    'SESSION_LIFETIME_DAYS': 7,

    # Bot Protection
    'ENABLE_HONEYPOT': True,
    'ENABLE_USER_AGENT_CHECK': True,

    # Logging
    'LOG_SUSPICIOUS': True,
    'SUSPICIOUS_LOG_FILE': 'security.log',
}


# ============================================================
# 📝 Logging أمني
# ============================================================
security_logger = logging.getLogger('security')
security_logger.setLevel(logging.WARNING)

if not security_logger.handlers:
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        '%(asctime)s [SECURITY] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    security_logger.addHandler(console)

    # File handler
    try:
        file_handler = logging.FileHandler(
            CONFIG['SUSPICIOUS_LOG_FILE'], encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        security_logger.addHandler(file_handler)
    except Exception:
        pass


# ============================================================
# 🌐 أدوات مساعدة
# ============================================================
def get_client_ip():
    """استخراج IP العميل بأمان"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        # التحقق من صيغة IP
        if re.match(r'^[0-9a-fA-F:.]{3,45}$', ip):
            return ip[:45]
    real_ip = request.headers.get('X-Real-IP', '')
    if real_ip and re.match(r'^[0-9a-fA-F:.]{3,45}$', real_ip):
        return real_ip[:45]
    return (request.remote_addr or 'unknown')[:45]


def get_user_agent():
    """استخراج User-Agent بأمان"""
    ua = request.headers.get('User-Agent', '')
    return ua[:500] if ua else 'unknown'


def get_fingerprint():
    """بصمة فريدة للعميل (IP + UA hash)"""
    ip = get_client_ip()
    ua = get_user_agent()
    raw = f"{ip}|{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ============================================================
# ⏱️ Rate Limiting متقدم
# ============================================================
_rate_buckets = {}
_rate_cleanup_last = time.time()


def _cleanup_rate_buckets():
    """تنظيف دوري للـ buckets القديمة"""
    global _rate_cleanup_last
    now = time.time()
    if now - _rate_cleanup_last < 300:  # كل 5 دقائق
        return
    _rate_cleanup_last = now

    window = CONFIG['RATE_LIMIT_WINDOW'] * 10
    for key in list(_rate_buckets.keys()):
        bucket = _rate_buckets[key]
        if not bucket or (now - bucket[-1]) > window:
            del _rate_buckets[key]


def rate_limit(key, max_calls, window=60):
    """
    التحقق من حد الطلبات
    Returns: True إذا مسموح، False إذا تجاوز الحد
    """
    _cleanup_rate_buckets()
    now = time.time()
    bucket = _rate_buckets.setdefault(key, [])
    # احتفظ بالطلبات داخل النافذة الزمنية فقط
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= max_calls:
        return False
    bucket.append(now)
    return True


def get_rate_limit_info(key, window=60):
    """معلومات عن حالة الحد الحالي"""
    now = time.time()
    bucket = _rate_buckets.get(key, [])
    active = [t for t in bucket if now - t < window]
    return {
        'count': len(active),
        'remaining': max(0, CONFIG['RATE_LIMIT_GLOBAL'] - len(active)),
        'reset_in': (active[0] + window - now) if active else 0
    }


# ============================================================
# 🚨 اكتشاف الأنماط المشبوهة
# ============================================================
SUSPICIOUS_PATTERNS = [
    # Path Traversal
    '..', '%2e%2e', '....//', '..\\', '%5c',
    # SQL Injection
    'union select', 'union all select', "' or '1'='1", '" or "1"="1',
    'or 1=1--', "' or 1=1", 'drop table', 'insert into', 'delete from',
    # XSS
    '<script', '</script>', 'javascript:', 'vbscript:', 'onerror=',
    'onload=', 'onclick=', 'onmouseover=', '<iframe', '<object',
    '<embed', '<applet', 'expression(', 'eval(',
    # Command Injection
    '; ls ', '; cat ', '| ls', '| cat', '`ls`', '`cat`', '$(', '${',
    # File Inclusion
    'etc/passwd', 'etc/shadow', 'proc/self', 'php://', 'file://',
    # Other
    'base64_decode', 'shell_exec', 'system(', 'exec(',
]

SAFE_HEADERS = {
    'host', 'user-agent', 'accept', 'accept-language', 'accept-encoding',
    'connection', 'content-type', 'content-length', 'cookie', 'referer',
    'origin', 'x-forwarded-for', 'x-real-ip', 'x-csrf-token',
    'sec-fetch-site', 'sec-fetch-mode', 'sec-fetch-dest', 'sec-ch-ua',
    'sec-ch-ua-mobile', 'sec-ch-ua-platform',
}


def detect_suspicious_request():
    """فحص الطلب بحثاً عن أنماط مشبوهة"""
    if not CONFIG['LOG_SUSPICIOUS']:
        return False

    checks = []

    # فحص URL
    url = request.url.lower()
    checks.append(('url', url))

    # فحص Query String
    if request.query_string:
        try:
            qs = request.query_string.decode('utf-8', errors='ignore').lower()
            checks.append(('query', qs))
        except Exception:
            pass

    # فحص Path
    checks.append(('path', request.path.lower()))

    # فحص Headers المشبوهة
    for header_name, header_value in request.headers:
        if header_name.lower() not in SAFE_HEADERS:
            if any(c in header_value for c in ['<', '>', 'script', 'select']):
                security_logger.warning(
                    f'🚨 Header مشبوه [{header_name}] من {get_client_ip()}'
                )
                return True

    # فحص الأنماط
    for source, text in checks:
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern in text:
                security_logger.warning(
                    f'🚨 نمط مشبوه [{pattern}] في {source} '
                    f'من {get_client_ip()} | UA: {get_user_agent()[:100]}'
                )
                return True

    return False


# ============================================================
# 🍯 Honeypot ضد البوتات
# ============================================================
def is_bot_via_honeypot():
    """
    التحقق من Honeypot
    Returns: True إذا كان بوت
    """
    if not CONFIG['ENABLE_HONEYPOT']:
        return False

    # حقول وهمية يجب أن تكون فارغة
    honeypot_fields = ['website', 'url', 'homepage', 'email_confirm', 'phone']

    for field in honeypot_fields:
        value = request.form.get(field, '')
        if value and value.strip():
            security_logger.warning(
                f'🤖 Bot detected (honeypot: {field}) '
                f'من {get_client_ip()} | القيمة: {value[:50]}'
            )
            return True

    return False


def is_bot_via_user_agent():
    """فحص User-Agent للبحث عن بوتات معروفة"""
    if not CONFIG['ENABLE_USER_AGENT_CHECK']:
        return False

    ua = get_user_agent().lower()

    # UA فارغ = بوت
    if not ua or ua == 'unknown':
        security_logger.warning(f'🤖 UA فارغ من {get_client_ip()}')
        return True

    # قائمة البوتات السيئة (ليست محركات بحث شرعية)
    bad_bots = [
        'curl', 'wget', 'python-requests', 'python-urllib',
        'java/', 'libwww-perl', 'scrapy', 'httpclient',
        'go-http-client', 'okhttp', 'axios', 'node-fetch',
        'postman', 'insomnia', 'sqlmap', 'nikto', 'nmap',
        'masscan', 'hydra', 'metasploit', 'burpsuite',
    ]

    for bot in bad_bots:
        if bot in ua:
            security_logger.warning(
                f'🤖 Bot UA detected [{bot}] من {get_client_ip()}'
            )
            return True

    return False


def check_request_size():
    """فحص حجم الطلب"""
    content_length = request.content_length or 0
    if content_length > CONFIG['MAX_CONTENT_LENGTH']:
        security_logger.warning(
            f'📦 طلب كبير جداً: {content_length} bytes من {get_client_ip()}'
        )
        return False
    return True


# ============================================================
# 🔐 CSRF Protection
# ============================================================
def generate_csrf_token():
    """توليد أو إرجاع CSRF token"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf():
    """التحقق من CSRF token"""
    if request.method not in ('POST', 'PUT', 'DELETE', 'PATCH'):
        return True

    # استثناءات
    if request.path in ('/auth/callback',):
        return True

    token = (request.form.get('_csrf_token') or
             request.headers.get('X-CSRF-Token') or
             request.headers.get('X-CSRFToken'))

    if not token:
        security_logger.warning(
            f'🚫 CSRF token مفقود من {get_client_ip()} | {request.path}'
        )
        return False

    expected = session.get('_csrf_token', '')
    if not expected:
        security_logger.warning(
            f'🚫 لا يوجد CSRF في الجلسة من {get_client_ip()}'
        )
        return False

    # مقارنة آمنة (مقاومة Timing)
    try:
        if not secrets.compare_digest(token, expected):
            security_logger.warning(
                f'🚫 CSRF token غير صالح من {get_client_ip()} | {request.path}'
            )
            return False
    except Exception:
        return False

    return True


def regenerate_csrf():
    """توليد CSRF جديد (بعد تسجيل الدخول)"""
    session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


# ============================================================
# 🧼 Input Sanitization
# ============================================================
# الأنماط المسموحة
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
NAME_RE = re.compile(r'^[\w\s\u0600-\u06FF\.\-\']{1,40}$', re.UNICODE)
SLUG_RE = re.compile(r'^[a-zA-Z0-9_\-]{3,30}$')
SAFE_TEXT_RE = re.compile(r'^[^\x00-\x08\x0b\x0c\x0e-\x1f]+$')
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# أنماط XSS للنقاء
XSS_PATTERNS = [
    (re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL), ''),
    (re.compile(r'<script[^>]*>', re.IGNORECASE), ''),
    (re.compile(r'javascript:', re.IGNORECASE), ''),
    (re.compile(r'vbscript:', re.IGNORECASE), ''),
    (re.compile(r'on\w+\s*=', re.IGNORECASE), ''),
    (re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL), ''),
    (re.compile(r'<iframe[^>]*>', re.IGNORECASE), ''),
    (re.compile(r'<object[^>]*>', re.IGNORECASE), ''),
    (re.compile(r'<embed[^>]*>', re.IGNORECASE), ''),
    (re.compile(r'<applet[^>]*>', re.IGNORECASE), ''),
    (re.compile(r'expression\s*\(', re.IGNORECASE), ''),
    (re.compile(r'eval\s*\(', re.IGNORECASE), ''),
]


def sanitize_text(text, max_len=1000):
    """تنظيف النص من الأحرف الضارة"""
    if not text or not isinstance(text, str):
        return ''

    # إزالة أحرف التحكم
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # إزالة XSS
    for pattern, replacement in XSS_PATTERNS:
        text = pattern.sub(replacement, text)

    # حدود الطول
    text = text.strip()
    return text[:max_len]


def sanitize_html(text):
    """تنظيف HTML بشكل صارم (يسمح بـ HTML أساسي فقط)"""
    if not text or not isinstance(text, str):
        return ''

    # إزالة كل الوسوم الخطيرة
    text = re.sub(
        r'<(script|style|iframe|object|embed|applet|link|meta)[^>]*>.*?</\1>',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r'<(script|style|iframe|object|embed|applet|link|meta)[^>]*/?>',
        '',
        text,
        flags=re.IGNORECASE
    )
    # إزالة onclick, onerror, etc
    text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+on\w+\s*=\s*[^\s>]+', '', text, flags=re.IGNORECASE)
    # إزالة javascript:
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'vbscript:', '', text, flags=re.IGNORECASE)
    # إزالة data: URLs الخطيرة
    text = re.sub(r'data:text/html', 'data:text/plain', text, flags=re.IGNORECASE)

    return text.strip()


def escape_html(text):
    """تحويل الأحرف الخاصة إلى HTML entities"""
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;')
            .replace('/', '&#x2F;'))


# ============================================================
# 🔗 URL & Avatar Validation
# ============================================================
def is_safe_url(url, max_len=500):
    """التحقق من أن URL آمن"""
    if not url or not isinstance(url, str):
        return False
    if len(url) > max_len:
        return False

    # منع البروتوكولات الخطيرة
    lower = url.lower().strip()
    dangerous = ['javascript:', 'vbscript:', 'data:', 'file:', 'about:', 'blob:']
    for d in dangerous:
        if lower.startswith(d):
            # نسمح بـ data:image فقط
            if d == 'data:' and lower.startswith('data:image/'):
                continue
            return False

    # يجب أن يبدأ بـ http:// أو https://
    if not (lower.startswith('http://') or lower.startswith('https://')):
        return False

    # التحقق من صيغة URL
    if not re.match(r'^https?://[^\s<>"\'{}|\\^`\[\]]+$', url):
        return False

    # منع null bytes
    if '\x00' in url or '%00' in url:
        return False

    return True


def is_safe_data_uri(uri, max_size=6_000_000):
    """التحقق من data URI للصور"""
    if not uri or not isinstance(uri, str):
        return False
    if len(uri) > max_size:
        return False

    allowed = (
        'data:image/jpeg;base64,',
        'data:image/jpg;base64,',
        'data:image/png;base64,',
        'data:image/webp;base64,',
        'data:image/gif;base64,',
    )
    return any(uri.startswith(p) for p in allowed)


def validate_username(u):
    return bool(u and isinstance(u, str) and USERNAME_RE.match(u))


def validate_name(n):
    if not n or not isinstance(n, str):
        return False
    n = n.strip()
    if not (1 <= len(n) <= 40):
        return False
    return bool(NAME_RE.match(n))


def validate_slug(s):
    return bool(s and isinstance(s, str) and SLUG_RE.match(s))


def validate_email(e):
    return bool(e and isinstance(e, str) and EMAIL_RE.match(e) and len(e) <= 120)


# ============================================================
# 🌐 Security Headers
# ============================================================
SECURITY_HEADERS = {
    'X-Frame-Options': 'SAMEORIGIN',
    'X-Content-Type-Options': 'nosniff',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': (
        'geolocation=(), microphone=(), camera=(), '
        'payment=(), usb=(), magnetometer=(), gyroscope=()'
    ),
    'Content-Security-Policy': (
        "default-src 'self'; "
        "img-src 'self' data: https: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "media-src 'self' https:; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    ),
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
}


def apply_security_headers(response, is_https=False):
    """تطبيق رؤوس الأمان على الاستجابة"""
    for header, value in SECURITY_HEADERS.items():
        # HSTS فقط في HTTPS
        if header == 'Strict-Transport-Security' and not is_https:
            continue
        response.headers[header] = value

    # إزالة رؤوس تكشف التقنية
    response.headers.pop('Server', None)
    response.headers.pop('X-Powered-By', None)

    return response


# ============================================================
# 🎯 Middleware - الحماية الشاملة
# ============================================================
def init_security(app):
    """
    تفعيل الحماية الشاملة على التطبيق
    استدع: init_security(app) بعد إنشاء app
    """

    # إعدادات Flask
    app.config['MAX_CONTENT_LENGTH'] = CONFIG['MAX_CONTENT_LENGTH']
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_PATH'] = '/'

    @app.before_request
    def _security_before_request():
        # 1. فحص حجم الطلب
        if not check_request_size():
            abort(413)

        # 2. فحص طول URL
        if len(request.url) > CONFIG['MAX_URL_LENGTH']:
            security_logger.warning(
                f'🔗 URL طويل جداً من {get_client_ip()}: {len(request.url)} حرف'
            )
            abort(414)

        # 3. فحص الأنماط المشبوهة
        if detect_suspicious_request():
            abort(400)

        # 4. فحص البوتات
        if is_bot_via_user_agent():
            if request.method in ('POST', 'PUT', 'DELETE'):
                abort(403)

        # 5. Rate Limiting شامل
        ip = get_client_ip()
        fingerprint = get_fingerprint()

        # الحد العام
        if not rate_limit(f'global:{ip}', CONFIG['RATE_LIMIT_GLOBAL'], 60):
            security_logger.warning(
                f'⏱️ تجاوز الحد العام من {ip} | {request.path}'
            )
            abort(429)

        # حد بصمة الجهاز (يتجاوز تغيير IP)
        if not rate_limit(f'fp:{fingerprint}', CONFIG['RATE_LIMIT_GLOBAL'] * 2, 60):
            security_logger.warning(
                f'⏱️ تجاوز حد البصمة من {ip} | {request.path}'
            )
            abort(429)

        # حد الإرسال
        if request.method == 'POST' and (
            request.path.startswith('/u/') or
            request.path.startswith('/c/')
        ):
            if not rate_limit(f'send:{ip}', CONFIG['RATE_LIMIT_SEND'], 60):
                flash('تم إرسال رسائل كثيرة! انتظر دقيقة.', 'error')
                return redirect(request.path)

        # حد الردود
        if request.method == 'POST' and '/reply/' in request.path:
            if not rate_limit(f'reply:{ip}', CONFIG['RATE_LIMIT_REPLY'], 60):
                return jsonify({
                    'status': 'error',
                    'message': 'محاولات كثيرة، انتظر قليلاً'
                }), 429

        # حد تسجيل الدخول
        if request.path == '/auth/google':
            if not rate_limit(f'login:{ip}', CONFIG['RATE_LIMIT_LOGIN'], 300):
                security_logger.warning(
                    f'🔐 محاولات دخول كثيرة من {ip}'
                )
                flash('محاولات تسجيل كثيرة! انتظر 5 دقائق.', 'error')
                return redirect(url_for('index'))

        # حد API
        if request.path.startswith('/api/'):
            if not rate_limit(f'api:{ip}', CONFIG['RATE_LIMIT_API'], 60):
                return jsonify({
                    'status': 'error',
                    'message': 'تجاوزت حد API'
                }), 429

        # 6. CSRF Protection
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if not validate_csrf():
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'status': 'error',
                        'message': 'CSRF token مفقود أو غير صالح'
                    }), 403
                flash('طلب مرفوض لأسباب أمنية', 'error')
                return redirect(url_for('index'))

    @app.after_request
    def _security_after_request(response):
        is_https = (
            request.is_secure or
            request.headers.get('X-Forwarded-Proto') == 'https'
        )
        return apply_security_headers(response, is_https=is_https)

    @app.errorhandler(400)
    def _bad_request(e):
        return jsonify({
            'status': 'error',
            'message': 'طلب غير صالح'
        }), 400

    @app.errorhandler(403)
    def _forbidden(e):
        return jsonify({
            'status': 'error',
            'message': 'ممنوع'
        }), 403

    @app.errorhandler(413)
    def _too_large(e):
        return jsonify({
            'status': 'error',
            'message': 'الطلب كبير جداً'
        }), 413

    @app.errorhandler(414)
    def _uri_too_long(e):
        return jsonify({
            'status': 'error',
            'message': 'الرابط طويل جداً'
        }), 414

    @app.errorhandler(429)
    def _too_many_requests(e):
        return jsonify({
            'status': 'error',
            'message': 'طلبات كثيرة جداً. حاول لاحقاً.'
        }), 429

    return app


# ============================================================
# 🍯 Honeypot HTML Helper
# ============================================================
def honeypot_field():
    """
    إرجاع حقل Honeypot HTML
    ضعه داخل <form> في أي مكان
    """
    return '''
    <div style="position:absolute;left:-9999px;top:-9999px;opacity:0;height:0;width:0;overflow:hidden;" aria-hidden="true">
        <label for="website_confirm">Website (اتركه فارغاً)</label>
        <input type="text" id="website_confirm" name="website" 
               value="" tabindex="-1" autocomplete="off">
    </div>
    '''


# ============================================================
# 🎯 Decorators للحماية
# ============================================================
def require_rate_limit(max_calls, window=60, key_prefix='custom'):
    """Decorator لتحديد Rate Limit مخصص"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = get_client_ip()
            key = f'{key_prefix}:{ip}:{request.path}'
            if not rate_limit(key, max_calls, window):
                if request.is_json:
                    return jsonify({
                        'status': 'error',
                        'message': 'تجاوزت حد الطلبات'
                    }), 429
                abort(429)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_no_bot(f):
    """Decorator لرفض البوتات"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if is_bot_via_honeypot() or is_bot_via_user_agent():
            if request.is_json:
                return jsonify({'status': 'error', 'message': 'مرفوض'}), 403
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def require_same_origin(f):
    """Decorator لفرض Same-Origin"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        origin = request.headers.get('Origin', '')
        referer = request.headers.get('Referer', '')
        host = request.host_url.rstrip('/')

        if origin and not origin.startswith(host):
            security_logger.warning(
                f'🌐 Origin مختلف: {origin} من {get_client_ip()}'
            )
            abort(403)

        return f(*args, **kwargs)
    return wrapper


# ============================================================
# 📊 Security Stats (اختياري)
# ============================================================
_security_stats = {
    'blocked_requests': 0,
    'rate_limited': 0,
    'bots_detected': 0,
    'csrf_failures': 0,
    'suspicious_patterns': 0,
    'started_at': time.time(),
}


def get_security_stats():
    """إرجاع إحصائيات الحماية"""
    return dict(_security_stats)


def reset_security_stats():
    """تصفير الإحصائيات"""
    for k in _security_stats:
        if k != 'started_at':
            _security_stats[k] = 0
    _security_stats['started_at'] = time.time()


# ============================================================
# 🧪 اختبار سريع
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("🛡️  security.py - وحدة الحماية")
    print("=" * 60)
    print("\n📋 الاختبارات:\n")

    # اختبار sanitize_text
    tests = [
        ("<script>alert('xss')</script>", "نص عادي"),
        ("javascript:alert(1)", "نص عادي"),
        ("hello <b>world</b>", "hello <b>world</b>"),
        ("عربي 123", "عربي 123"),
        ("\x00\x01evil", "evil"),
    ]

    for inp, expected in tests:
        result = sanitize_text(inp)
        status = "✅" if expected in result or result == expected else "⚠️"
        print(f"{status} sanitize_text({inp!r})")
        print(f"   → {result!r}\n")

    # اختبار is_safe_url
    urls = [
        ("https://google.com", True),
        ("javascript:alert(1)", False),
        ("data:text/html,<script>", False),
        ("https://example.com/image.jpg", True),
        ("file:///etc/passwd", False),
        ("http://site.com?q=<script>", False),
    ]

    print("\n🔗 اختبار URL Validation:")
    for url, expected in urls:
        result = is_safe_url(url)
        status = "✅" if result == expected else "❌"
        print(f"{status} is_safe_url({url!r}) = {result}")

    # اختبار validate_username
    print("\n👤 اختبار Username Validation:")
    usernames = [
        ("user_123", True),
        ("ab", False),
        ("user@#$", False),
        ("a" * 25, False),
        ("ValidUser", True),
    ]
    for u, expected in usernames:
        result = validate_username(u)
        status = "✅" if result == expected else "❌"
        print(f"{status} validate_username({u!r}) = {result}")

    print("\n" + "=" * 60)
    print("✅ كل الاختبارات اكتملت")
    print("=" * 60)
