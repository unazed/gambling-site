from collections import defaultdict
from html import escape
from secrets import token_urlsafe
import asyncio
import base64
import hashlib
import time
import inspect
import ipaddress
import multiprocessing
import os
import json
import string
import types
import pprint

import pyrebase
pyrebase.pyrebase.raise_detailed_error = lambda *args, **kwargs: None
# annoying

import server_constants
import server_utils
import server_api.websocket_interface
from server_api.https_server import HttpsServer
from server_api.websocket_interface import WebsocketPacket, CompressorSession


class GamblingSiteWebsocketClient:
    def __init__(self, headers, extensions, server, trans, addr):
        server_api.websocket_interface.EXTENSIONS.update(extensions)
        self.trans = trans
        self.addr = addr
        self.server = server
        self.headers = headers

        comp = None
        self.comp = None
        if (params := extensions.get("permessage-deflate")) is not None:
            if (wbits := params.get("server_max_window_bits")) is None:
                self.comp = CompressorSession()
            else:
                self.comp = CompressorSession(int(wbits))
            print("creating compression object, wbits =", wbits)
        self.packet_ctor = WebsocketPacket(None, self.comp)

        self.authentication = server.authentication = {}
        self.chat_initialized = False

        self.last_pinged = {}

        self.__is_final = True
        self.__data_buffer = ""

    def get_user_by_firebase(self, username=None):
        if not self.authentication:
            return
        return [*server.firebase_db                         \
                .child("users")                             \
                .order_by_child("username")                 \
                .equal_to(username or                       \
                    self.authentication['username'])        \
                .get().val().values()][0]

    def broadcast_message(self, message_obj):
        if not self.chat_initialized:
            return
        for ws_client in self.server.clients.values():
            if not ws_client.chat_initialized:
                continue
            ws_client.trans.write(ws_client.packet_ctor.construct_response({
                "action": "on_message",
                "message": message_obj
            }))

    def __call__(self, prot, addr, data):
        # checking account still exists & is active
        if self.authentication and self.authentication['username'] not in self.server.logins:
            self.authentication = {}
            self.trans.write(self.packet_ctor.construct_response({
                "error": "username doesn't exist anymore"
            }))
        elif self.authentication and self.authentication['token'] != \
                self.server.logins[self.authentication['username']]['active_token']:
            self.authentication = {}
            self.trans.write(self.packet_ctor.construct_response({
                "error": "expired/invalid token"
            }))

        # collate ws data fragments if necessary
        if self.__data_buffer:
            data = self.__data_buffer
        data = self.packet_ctor.parse_packet(data)
        if data['extra']:
            self.__call__(prot, addr, data['extra'])
        self.__is_final = data['is_final']
        if not self.__is_final:
            print("receiving data fragments")
            self.__data_buffer += data['data']
            return
        elif self.__data_buffer:
            data = self.packet_ctor.parse_packet(self.__data_buffer + data['data'])
            self.__data_buffer = ""
            print("finished receiving, length =", len(data['data']))

        if data['opcode'] == 0x08:
            print("received close frame")
            self.trans.close()
            return
        elif data['opcode'] == 0x01:
            try:
                content = json.loads(data['data'])
            except json.JSONDecodeError as exc:
                self.trans.write(self.packet_ctor.construct_response({
                    "error": "client sent invalid JSON"
                }))
                print("received invalid JSON:", data['data'])
                return

            if (action := content.get("action")) is None:
                self.trans.write(self.packet_ctor.construct_response({
                    "error": "no 'action' passed"
                }))
                return
            elif action not in server_constants.SUPPORTED_WS_ACTIONS:
                self.trans.write(self.packet_ctor.construct_response({
                    "error": f"action {escape(action)!r} doesn't exist"
                }))
                return
            if action == "event_handler":
                if not (event_name := server_utils.ensure_contains(
                        self, content, ("name",)
                        )):
                    return
                event_name = event_name[0]
                if len(subpath := event_name.split("/", 2)) == 2:
                    subpath, event_name = subpath
                    if (event := server_constants.SUPPORTED_WS_EVENTS.get(
                                f"{subpath}/*"
                            )) is None and\
                            (event := server_constants.SUPPORTED_WS_EVENTS.get(
                                f"{subpath}/{event_name}"
                            )) is None:
                        self.trans.write(self.packet_ctor.construct_response({
                            "error": f"event {escape(event_name)!r} not registered"
                        }))
                        return
                    event = event(self, event_name)
                elif (event := server_constants.SUPPORTED_WS_EVENTS.get(event_name)) is None:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": f"event {escape(event_name)!r} not registered"
                    }))
                    return
                elif isinstance(event, types.FunctionType):
                    event = event(self.authentication)
                format = {}
                if isinstance(event, (tuple, list)):
                    event, format = event
                data = self.server.read_file(event, format={
                    "$$username": '"' + self.authentication.get("username", "") + '"',
                    "$$auth_token": '"' + self.authentication.get("token", "") + '"',
                    **format
                })
                if not data:
                    self.trans.write(self.packet_ctor.construct_response({
                        "warning": f"{event_name!r} unimplemented"
                    }))
                    return
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "do_load",
                    "data": data
                }))
            elif action == "userlist_update":
                users = server.firebase_db.child("users").order_by_child("username").get().val()
                if users is None:
                    userlist = []
                else:
                    userlist = list(map(
                        lambda user: user['username'],
                        users.values()
                        ))
                if self.authentication:
                    self.last_pinged[self.authentication['username']] = time.time()
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "userlist",
                    "userlist": userlist,
                    "last_pinged": self.last_pinged
                    }))
            elif action == "register":
                if self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "you're already logged in"
                    }))
                    return
                elif not (res := server_utils.ensure_contains(
                        self.trans, content, ("email", "username", "password")
                        )):
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "either 'username', 'email' or 'password' wasn't passed"
                    }))
                    return
                email, username, password = res
                if username in server.logins:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['register_fail'],
                            format={
                                "$$object": "username",
                                "$$reason": '"username exists"'
                            }
                        )
                    }))
                    return
                elif not (2 <= len(password) <= 64):
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['register_fail'],
                            format={
                                "$$object": "password",
                                "$$reason": '"password must be between 2 and 64 characters"'
                            }
                        )
                    }))
                    return

                auth_result = server.firebase_auth.create_user_with_email_and_password(email, password)
                if (error_type := auth_result.get("error", {}).get("message", None)) is not None:
                    response = "Error occurred during registration"
                    if error_type == "INVALID_EMAIL":
                        response = "Email field has invalid format"
                    elif error_type == "EMAIL_EXISTS":
                        response = "Email is already registered"
                    else:
                        print(error_type)
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['register_fail'],
                            format={
                                "$$object": "email",
                                "$$reason": f'"{response}"'
                            }
                        )
                    }))
                    return
                elif 'email' not in auth_result:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "Internal error"
                    }))
                    return

                server.logins[username] = {
                    "registration_timestamp": time.strftime("%D %H:%M:%S"),
                    "active_token": (tok := auth_result['idToken']),
                    "rank": server_constants.DEFAULT_RANK,
                    "email": email
                }

                db_ref = server.firebase_db.child("users").push({
                    "username": username,
                    "email": email,
                    "xp": 0,
                    "deposits": {0: 0},
                    "withdrawals": {0: 0}
                })

                self.authentication = {
                    "username": username,
                    "email": email,
                    "token": tok,
                    "rank": server_constants.DEFAULT_RANK
                }
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "registered",
                    "data": {
                        "username": username,
                        "token": tok
                    }
                }))
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "do_load",
                    "data": server.read_file(
                        server_constants.SUPPORTED_WS_EVENTS['home'],
                        format={
                            "$$username": f'"{username}"',
                            "$$auth_token": f'"{tok}"'
                            }
                        )
                }))
                self.broadcast_message({
                    "content": f"{username} registered a new account",
                    "properties": {
                        "font-weight": "600"
                    }
                })
                server_utils.commit_logins(self.server)
            elif action == "login":
                if self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                            format={
                                "$$object": "null",
                                "$$reason": '"already logged in"'
                            }
                        )
                    }))
                    return
                elif (tok := content.get("token")):
                    acc_info = server.firebase_auth.get_account_info(tok)
                    
                    if (error_type := acc_info.get("error", {}).get("message", None)) is not None:
                        response = "Failed to login"
                        if error_type == "USER_DISABLED":
                            response = "Your account has been disabled"
                        elif error_type == "INVALID_ID_TOKEN":
                            response = "Your token has expired, relogin"
                        else:
                            print(error_type)
                        self.trans.write(self.packet_ctor.construct_response({
                            "action": "do_load",
                            "data": self.server.read_file(
                                server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                                format={
                                    "$$object": "null",
                                    "$$reason": f'"{response}"'
                                }
                            )
                        }))
                        return
                    elif (user := acc_info.get("users", (None,))[0]) is None:
                        self.trans.write(self.packet_ctor.construct_response({
                            "action": "do_load",
                            "data": self.server.read_file(
                                server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                                format={
                                    "$$object": "null",
                                    "$$reason": '"Internal error with logging in"'
                                }
                            )
                        }))
                        return

                    for username, userinfo in server.logins.items():
                        if userinfo['email'] == user['email']:
                            break
                    else:
                        self.trans.write(self.packet_ctor.construct_response({
                            "action": "do_load",
                            "data": self.server.read_file(
                                server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                                format={
                                    "$$object": "null",
                                    "$$reason": f'"Internal error with logging in"'
                                }
                            )
                        }))
                        return

                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "login",
                        "data": {
                            "username": username
                        }
                    }))
                    self.authentication = {
                        "username": username,
                        "token": tok,
                        "rank": userinfo['rank']
                    }
                    print(f"{username!r} logged in via token")
                    self.broadcast_message({
                        "content": f"{username} has signed in (token)",
                        "properties": {
                            "font-weight": "600"
                        }
                    })
                    return
                if not (res := server_utils.ensure_contains(
                        self.trans, content, ("email", "password")
                        )):
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                            format={
                                "$$object": "null",
                                "$$reason": '"either \'email\' or \'password\' wasn\'t passed"'
                            }
                        )
                    }))
                    return
                email, password = res

                login_info = server.firebase_auth.sign_in_with_email_and_password(email, password)
                if (error_type := login_info.get("error", {}).get("message", None)) is not None:
                    response = "Failed to login"
                    object_ = "null"

                    if error_type == "INVALID_PASSWORD":
                        response = "Invalid password"
                        object_ = "password"
                    elif error_type == "EMAIL_NOT_FOUND":
                        response = "Email not found"
                        object_ = "email"
                    elif error_type == "INVALID_EMAIL":
                        response = "Invalid email format"
                        object_ = "email"
                    else:
                        print(error_type)

                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                            format={
                                "$$object": object_,
                                "$$reason": f'"{response}"'
                            }
                        )
                    }))
                    return
                tok = login_info['idToken']
                for username, userinfo in server.logins.items():
                    if userinfo['email'] == email:
                        break
                else:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['login_fail'],
                            format={
                                "$$object": "null",
                                "$$reason": f'"Internal error while logging in"'
                            }
                        )
                    }))
                    return
                print(f"{username!r} logged in manually")
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "login",
                    "data": {
                        "username": username,
                        "token": tok
                    }
                }))
                self.authentication = {
                    "username": username,
                    "token": tok,
                    "rank": userinfo['rank']
                }
                self.server.logins[username].update({
                    "active_token": tok
                })
                self.broadcast_message({
                    "content": f"{username} has signed in",
                    "properties": {
                        "font-weight": "600"
                    }
                })
                server_utils.commit_logins(self.server)
            elif action == "logout":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "tried to logout when not logged in"
                    }))
                    return
                self.server.logins[self.authentication['username']]['active_token'] = ""
                print(f"{self.authentication['username']!r} logged out")
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "do_load",
                    "data": self.server.read_file(
                        server_constants.SUPPORTED_WS_EVENTS['logout']
                        )
                }))
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "do_load",
                    "data": self.server.read_file(
                        server_constants.SUPPORTED_WS_EVENTS['home'],
                        format={
                            "$$username": '""',
                        }
                    )
                }))
                self.broadcast_message({
                    "content": f"{self.authentication['username']} is away",
                    "properties": {
                        "font-weight": "600"
                    }
                })
                self.authentication = {}
            elif action == "initialize_chat":
                if self.chat_initialized:
                    return
                self.chat_initialized = True
                for message in self.server.message_cache:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "on_message",
                        "message": message
                    }))
            elif action == "send_message":
                if not (message := server_utils.ensure_contains(
                        self, content, ("message",)
                        )):
                    return
                message = message[0]
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "on_message",
                        "message": {
                            "content": "register or login to post a message",
                            "properties": {
                                "font-weight": "600"
                            }
                        }
                    }))
                    return
                elif len(message) > 255:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "on_message",
                        "message": {
                            "username": "SYSTEM",
                            "content": "message must be less than 256 characters",
                            "properties": {
                                "font-weight": "600"
                            }
                        }
                    }))
                    return
                elif server_utils.is_filtered(message):
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "on_message",
                        "message": {
                            "username": "SYSTEM",
                            "content": "filtered message",
                            "properties": {
                                "font-weight": "600"
                            }
                        }
                    }))
                    return
                print(f"{self.authentication['username']}: {message!r}")
                user_obj = self.get_user_by_firebase()
                self.broadcast_message(obj := {
                    "username": self.authentication['username'],
                    "level": server_utils.get_level(server_constants.LEVEL_INDICES, user_obj['xp']),
                    "xp_count": user_obj['xp'],
                    "content": message
                })
                self.server.message_cache.append(obj)
            elif action == "profile_info":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.send_file(
                            server_constants.SUPPORTED_WS_EVENTS['forbidden']
                        )
                    }))
                    return
                elif not (username := server_utils.ensure_contains(
                        self, content, ("username",)
                        )):
                    return
                user_info = self.get_user_by_firebase(username[0])
                if user_info['username'] != self.authentication['username']:
                    for sensitive_key in server_constants.SENSITIVE_USER_KEYS:
                        del user_info[sensitive_key]
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "profile_info",
                    "data": {
                        "level": server_utils.get_level(server_constants.LEVEL_INDICES, user_info['xp']),
                        **user_info
                        }
                }))
        else:
            print("received weird opcode, closing for inspection",
                    hex(data['opcode']))
            self.trans.close()

    def on_close(self, prot, addr, reason):
        ip = self.headers.get("cf-connecting-ip", addr[0])
        print(f"closed websocket with {ip!r}, reason={reason!r}")


_print = print


def print(*args, **kwargs):  # pylint: disable=redefined-builtin
    curframe = inspect.currentframe().f_back
    prev_fn = curframe.f_code.co_name
    line_no = curframe.f_lineno
    class_name = ""
    if (inst := curframe.f_locals.get("self")) is not None:
        class_name = f" [{inst.__class__.__name__}]"
    _print(f"[{time.strftime('%H:%M:%S')}] :{line_no} [ServerHandler]{class_name} [{prev_fn}]",
           *args, **kwargs)


async def main_loop(server):
    await server.handle_requests()


def preinit_whitelist(server, addr):
    ip = ipaddress.ip_address(addr[0])
    if not any(ip in net for net in server_constants.WHITELISTED_RANGES):
        print(f"prevented {addr[0]} from connecting due to whitelist")
        server.trans.close()
        return


server = HttpsServer(
    root_directory="html/",
    host="0.0.0.0", port=8443,
    cert_chain=".ssl/gambling-site.crt",
    priv_key=".ssl/gambling-site.key",
    callbacks={
        "on_connection_made": preinit_whitelist
        },
    subdomain_map=server_constants.SUBDOMAIN_MAP
    )


@server.route("GET", "/", subdomain=["www"])
def index_handler(metadata):
    server.send_file(metadata, "index.html")

@server.route("GET", "/unsupported", get_params=["code"], subdomain="*")
def unsupported_handler(metadata, code=None):
    server.send_file(metadata, "unsupported.html", format={
        "{error}": server_constants.ERROR_CODES.get(code,
            "The server hasn't specified a reason."
            )
        })

@server.route("GET", "/pseudo-file", get_params=["fid"], subdomain=["www"],
        enforce_params=True)
def pseudo_file(metadata, fid):
    server.send_file(metadata, "pseudo-file.html", format={
        "{data}": str(server.pseudo_files[fid])
        }, headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'filename="{fid}"'
            })

@server.route("websocket", "/ws-gambling", subdomain=["www"])
def gambling_site_websocket_handler(headers, idx, extensions, prot, addr, data):
    print("registering new Gambling Site websocket transport")
    if idx not in server.clients:
        server.clients[idx] = GamblingSiteWebsocketClient(
            headers, extensions, server, prot.trans, addr
        )
    prot.on_data_received = server.clients[idx]
    prot.on_connection_lost = server.clients[idx].on_close
    prot.on_data_received(prot.trans, addr, data)

@server.route("GET", "/*", subdomain="*")
def wildcard_handler(metadata):
    trans = metadata['transport']
    path = metadata['method']['path'][1:].split("/")
    if len(path) >= 2:
        folder, file = '/'.join(path[:-1]), path[-1]
        if folder not in server_constants.ALLOWED_FOLDERS:
            trans.write(server.construct_response("Forbidden",
                error_body=f"<p>Folder {escape(folder)!r} isn't whitelisted</p>"
                ))
            return
        headers = {}
        if isinstance((hdrs := server_constants.ALLOWED_FOLDERS[folder]), dict):
            headers = dict(filter(lambda i: not i[0].startswith("__"), hdrs.items()))
        files = os.listdir(folder)
        if file not in files:
            trans.write(server.construct_response("Not Found",
                error_body=f"<p>File {escape(folder) + '/' + escape(file)!r} "
                           "doesn't exist</p>"
                ))
            return
        server.send_file(metadata, f"../{'/'.join(path)}", headers={
            "content-type": server_constants.get_mimetype(file),
            **headers
        }, do_minify=False,
        read_kwargs=server_constants.ALLOWED_FOLDERS[folder].get(
            "__read_params", {}
        ) if server_constants.ALLOWED_FOLDERS[folder] is not None else {
            "mode": "r"
        })
        return
    elif len(path) == 1:
        file = path[0]
        if (path := server_constants.ALLOWED_FILES.get(file)) is None:
            trans.write(server.construct_response("Forbidden",
                error_body=f"<p>File {escape(file)!r} isn't whitelisted</p>"
                ))
            return
        elif (redir := server_constants.ALLOWED_FILES[file].get("__redirect")) is not None:
            path = redir
        headers = {}
        if isinstance((hdrs := server_constants.ALLOWED_FILES[file]), dict):
            headers = dict(filter(lambda i: not i[0].startswith("__"), hdrs.items()))
        server.send_file(metadata, f"../{path}", headers={
            "content-type": server_constants.get_mimetype(file),
            **headers
        }, do_minify=False,
        read_kwargs=server_constants.ALLOWED_FILES[file].get(
            "__read_params", {}
        ) if server_constants.ALLOWED_FILES[file] is not None else {
            "mode": "r"
        })
    trans.write(server.construct_response("Not Found",
        error_body=f"<p>File {escape(metadata['method']['path'])!r} "
                    "doesn't exist</p>"
        ))


if not os.path.isfile("logins.db"):
    with open("logins.db", "w") as logins:
        logins.write("{}")

with open("logins.db") as logins:
    try:
        server.logins = json.load(logins)
    except json.JSONDecodeError:
        print("failed to load 'logins.db'")
        server.logins = {}

server.clients = {}
server.message_cache = []
server.pseudo_files = {}

server.firebase = pyrebase.initialize_app({
  "apiKey": "AIzaSyDFl6ewwUVBiG-tyU5nTPGQhYXupdTUd5I",
  "authDomain": "gambling-site-c11d0.firebaseapp.com",
  "storageBucket": "gambling-site-c11d0.appspot.com",
  "databaseURL": "https://gambling-site-c11d0-default-rtdb.firebaseio.com/",
  "serviceAccount": "firebase_key.json"
})
server.firebase_auth = server.firebase.auth()
server.firebase_db = server.firebase.database()

userlist = server.firebase_db.child("users").get().each()
print("userlist from Firebase:")
if userlist is not None:
    for user in userlist:
        user = user.val()
        if user['username'] not in server.logins:
            print(f"{user['username']!r} doesn't appear in local database, synchronization may be required")
        print('--- ' + ', '.join(f"{attr}: {val!r}" for attr, val in user.items()))
else:
    print("-- empty")

print("initialized Google Firebase Authentication & Database")

try:
    server.loop.run_until_complete(main_loop(server))
except KeyboardInterrupt:
    print("exiting gracefully...")
