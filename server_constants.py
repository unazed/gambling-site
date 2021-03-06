from ipaddress import ip_network
from functools import partial
import math


def get_mimetype(name):
    return MIMETYPES.get(name.split(".")[-1], "text/plain")


def when_authenticated(name, must_have_auth=True):
    def inner(auth):
        if not auth and not must_have_auth:
            return f"html/events/{name}"
        elif not auth:
            return SUPPORTED_WS_EVENTS['forbidden']
        return f"html/events/auth/{name}"
    return inner


def retrieve_profile(client, username):
    if username not in client.server.logins:
        return SUPPORTED_WS_EVENTS['notify'], {
            "$$reason": "profile doesn't exist",
            "$$type": "error"
            }
    return SUPPORTED_WS_EVENTS['show_profile'], {
        "$$username": f'"{username}"'
        }

ERROR_CODES = {
    "400": "Websockets are unsupported on your platform "
         "consider upgrading your browser. Without websockets "
         "we would not be able to serve this webpage to you."
}

SUPPORTED_WS_ACTIONS = [
    "event_handler",
    "register",
    "login", "logout",
    "navigation",
    "initialize_chat",
    "send_message",
    "profile_info",
    "userlist_update",
    "load_wallet",
    "create_transaction",
    "check_transaction",
    "load_transactions",
    "verify_recaptcha",
    "ping", "view_lottery",
    "load_lotteries",
    "join_lottery",
    "lottery_heartbeat",
    "lottery_clientseed",
    "leave_lottery",
    "view_jackpot",
    "refresh_jackpot",
    "join_jackpot",
    "jackpot_results",
    "place_bet",
    "leave_jackpot",
    "load_history"
]

RECAPTCHA_MIN_SCORE = 0.1
XP_MULTIPLIER = 2.5
JACKPOT_HOUSE_PERC = 0.95

SUPPORTED_CURRENCIES = ["bitcoin", "ethereum"]

SUPPORTED_WS_EVENTS = {
    # Gambling events
    "home": "html/events/home.js",
    "profile/*": retrieve_profile,
    "navigation": "html/events/navigation.js",
    "login": "html/events/login.js",
    "login_fail": "html/events/input_fail.js",
    "register": "html/events/register.js",
    "register_fail": "html/events/input_fail.js",
    "logout": "html/events/logout.js",
    "forbidden": "html/events/forbidden.js",
    "chatbox": "html/events/chatbox.js",
    "notify": "html/events/notify.js",
    "provably_fair": when_authenticated("provably_fair.js"),
    "wallet": when_authenticated("wallet.js"),
    "show_profile": when_authenticated("show_profile.js"),
    "view_lottery": when_authenticated("lottery.js"),
    "join_lottery": when_authenticated("lottery_view.js"),
    "reset_lottery": when_authenticated("lottery_clear_interval.js"),
    "view_jackpot": when_authenticated("view_jackpot.js"),
    "load_jackpot": when_authenticated("load_jackpot.js")
}

MAX_LOTTERY_NUMBERS = 10

MIMETYPES = {
    "js": "text/javascript",
    "css": "text/css",
    "html": "text/html",
    "ico": "image/x-icon",
    "svg": "image/svg+xml"
}

DEFAULT_RANK = "default"
UPGRADED_RANK = "upgraded"

LOTTERY_START_TIME = 20
LOTTERY_USER_JOIN_TIME_BONUS = 10

JACKPOT_START_TIME = 20
JACKPOT_USER_JOIN_TIME_BONUS = 10

RANK_PROPERTIES = {
    DEFAULT_RANK: {
        "max_usernames": 100,
        "max_tasks": 2
        },
    UPGRADED_RANK: {
        "max_usernames": 1000,
        "max_tasks": 2
        }
    }

RETRY_ATTEMPTS = 1

MAX_LEVEL = 100
LEVEL_INDICES = []
_level_xp_acc = 0
for _level in range(1 + MAX_LEVEL):
    _level_xp_acc += math.ceil(_level / 10) * 100
    LEVEL_INDICES.append(_level_xp_acc)

SENSITIVE_USER_KEYS = ["email"]

WHITELISTED_RANGES = [*map(ip_network, [
    "103.21.244.0/22", "2400:cb00::/32",
    "103.22.200.0/22", "2606:4700::/32",
    "103.31.4.0/22", "2803:f800::/32",
    "104.16.0.0/13", "2405:b500::/32",
    "104.24.0.0/14", "2405:8100::/32",
    "108.162.192.0/18", "2a06:98c0::/29",
    "131.0.72.0/22", "2c0f:f248::/32",
    "141.101.64.0/18",
    "162.158.0.0/15",
    "172.64.0.0/13",
    "173.245.48.0/20",
    "188.114.96.0/20",
    "190.93.240.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    ])]

SUBDOMAIN_MAP = {
    "www": "html/",
    "admin": "admin/"
    }

ALLOWED_FOLDERS = {
    "html/css": {
        "Cache-Control": "nostore"
        },
    "html/js": {
        "Cache-Control": "nostore"
        },
    "html/img": {
        "Cache-Control": "nostore",
        "__read_params": {
            "mode": "rb"
            }
        },
    "admin/js": {
        "Cache-Control": "nostore"
        },
    "admin/css": {
        "Cache-Control": "nostore"
        }
    }

ALLOWED_FILES = {
    "favicon.ico": {
        "__redirect": "html/img/favicon.ico",
        "__read_params": {
            "mode": "rb"
            }
        }
    }
