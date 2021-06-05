from ipaddress import ip_network
from functools import partial
import math


def get_mimetype(name):
    return MIMETYPES.get(name.split(".")[-1], "text/plain")


def when_authenticated(name, must_have_auth=False):
    def inner(auth):
        if not auth and not must_have_auth:
            return f"events/{name}"
        elif not auth:
            return SUPPORTED_WS_EVENTS['forbidden']
        return f"events/auth/{name}"
    return inner


def service_item(client, name):
    if not client.authentication:
        return SUPPORTED_WS_EVENTS['forbidden']
    elif name not in SUPPORTED_SERVICES:
        return SUPPORTED_WS_EVENTS['home']
    return "events/auth/service.js", {
        "$$service": f'"{name}"'
        }


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
    "load_wallet"
]

SUPPORTED_WS_EVENTS = {
    # Gambling events
    "home": "events/home.js",
    "service/*": service_item,
    "profile/*": retrieve_profile,
    "navigation": "events/navigation.js",
    "login": "events/login.js",
    "login_fail": "events/input_fail.js",
    "register": "events/register.js",
    "register_fail": "events/input_fail.js",
    "logout": "events/logout.js",
    "forbidden": "events/forbidden.js",
    "chatbox": "events/chatbox.js",
    "notify": "events/notify.js",
    "wallet": when_authenticated("wallet.js", True),
    "show_profile": when_authenticated("show_profile.js", True),
    "service_notify": when_authenticated("service_notify.js", True),
}

MIMETYPES = {
    "js": "text/javascript",
    "css": "text/css",
    "html": "text/html",
    "ico": "image/x-icon",
    "svg": "image/svg+xml"
}

DEFAULT_RANK = "default"
UPGRADED_RANK = "upgraded"

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
