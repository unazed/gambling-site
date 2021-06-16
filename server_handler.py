from collections import defaultdict, Counter
from html import escape
from secrets import token_urlsafe
import asyncio
import base64
import datetime
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

from coinbase_commerce.client import Client as CoinbaseClient
import pyrebase
pyrebase.pyrebase.raise_detailed_error = lambda *args, **kwargs: None

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
        self.is_recaptcha_verified = False

        self.__is_final = True
        self.__data_buffer = ""

    def add_user_withdrawal(self, charge):
        _, currency, address, amount = charge
        print(f"creating withdrawal for '{amount} {currency}' {type(amount)}")
        server.firebase_db.child("withdrawals").child(self.authentication['username']) \
                          .push({
                            "address": address,
                            "currency": currency,
                            "local_amount": round(server_utils.crypto_to_usd(float(amount), currency), 2),
                            "created_at": datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                            })

    def add_user_deposit(self, charge):
        server.firebase_db.child("deposits").child(self.authentication['username']) \
                          .child(charge['id']).set({
                              "pricing": charge['pricing'],
                              "addresses": charge['addresses'],
                              "expires_at": charge['expires_at'],
                              "created_at": datetime.datetime.fromtimestamp(
                                  datetime.datetime.strptime(charge['created_at'], "%Y-%m-%dT%H:%M:%SZ").timestamp()
                                  ).strftime('%Y-%m-%d %H:%M:%S'),
                              "requested_currency": charge['requested_currency'],
                              "validated": False
                            })

    def validate_deposit(self, id_, username=None):
        server.firebase_db.child("deposits").child(username \
                or self.authentication['username']).child(id_).update({
                    "validated": True
                    })

    def get_deposit(self, id_, username=None):
        return server.firebase_db.child("deposits").child(username  \
                or self.authentication['username']).child(id_).get().val()

    def get_deposits(self, username=None):
        return server.firebase_db.child("deposits").child(username  \
                or self.authentication['username']).get().val()

    def get_withdrawals(self, username=None):
        return server.firebase_db.child("withdrawals").child(username  \
                or self.authentication['username']).get().val()

    def update_user_by_firebase(self, data, username=None):
        userkey = [*server.firebase_db.child("users").order_by_child("username")              \
                                      .equal_to(username or self.authentication['username'])  \
                                      .get().val().keys()][0]
        print("user key", userkey)
        server.firebase_db.child("users").child(userkey).update(data)

    def get_user_by_firebase(self, username=None):
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
            self.trans.write(self.packet_ctor.construct_response(data=b"", opcode=0x08))
            return self.trans.close()
        elif data['opcode'] == 0x0A:
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
            elif action == "ping":
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "pong"
                    }))
                return self.trans.write(self.packet_ctor.construct_response(data=b"", opcode=0x09))
            elif action == "load_lotteries":
                if not self.authentication:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "must be logged in to load lotteries"
                        }))
                self.trans.write(self.packet_ctor.construct_response({
                    "action": action,
                    "data": {
                        "list": server.lotteries,
                        "active": server.active_lotteries
                        }
                    }))
            elif action == "view_lottery":
                if not self.authentication:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "must be logged in to participate in lottery"
                        }))
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "do_load",
                    "data": self.server.read_file(
                        server_constants.SUPPORTED_WS_EVENTS['lottery']
                    )
                }))
            elif action == "verify_recaptcha":
                if not (token := server_utils.ensure_contains(
                        self, content, ("token",)
                        )):
                    return
                token = token[0]
                score = server_utils.get_recaptcha_response(server.recaptcha_privkey, token)['score']
                if score < server_constants.RECAPTCHA_MIN_SCORE:
                    return self.trans.write(self.packet_ctor.construct_response({
                            "error": "failed reCAPTCHA v3 verification"
                        }))
                self.is_recaptcha_verified = True
            elif action == "load_transactions":
                if not self.authentication:
                    return self.trans.write(self.packet_ctor.construct_response({
                            "error": "must be authenticated to load transactions"
                        }))
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "load_transactions",
                    "data": {
                        "deposits": self.get_deposits(),
                        "withdrawals": self.get_withdrawals()
                        }
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
                    server.last_pinged[self.authentication['username']] = time.time()
                self.trans.write(self.packet_ctor.construct_response({
                    "action": "userlist",
                    "userlist": userlist,
                    "last_pinged": server.last_pinged
                    }))
            elif action == "load_wallet":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "you must be logged in to access your wallet"
                    }))
                    return
                elif not (markets := server_utils.ensure_contains(
                        self, content, ("markets",)
                        )):
                    return
                markets = markets[0]

                deposits = self.get_deposits() or {}
                withdrawals = self.get_withdrawals() or {}

                deposit_volume = 0
                per_market_deposit_sum = Counter()
                per_market_deposits = defaultdict(list)

                withdraw_volume = 0
                per_market_withdrawal_sum = Counter()
                per_market_withdrawals = defaultdict(list)

                market_prices = server_utils.get_crypto_prices(markets.copy())

                user_obj = self.get_user_by_firebase()

                for market in markets:
                    per_market_withdrawal_sum[market] = 0
                    per_market_deposit_sum[market] = 0

                for deposit in deposits.values():
                    if not deposit['validated']:
                        continue
                    market = deposit['requested_currency']
                    if market not in markets:
                        continue
                    amount = float(deposit['pricing'][market]['amount'])
                    per_market_deposit_sum[market] += amount
                    deposit_volume += amount
                    per_market_deposits[market].append({
                        "timestamp": deposit['created_at'],
                        "amount": amount
                        })

                for withdrawal in withdrawals.values():
                    market = withdrawal['requested_currency']
                    if market not in markets:
                        continue
                    amount = float(withdrawal['pricing'][market]['amount'])
                    per_market_withdrawal_sum[market] += amount
                    withdraw_volume += amount
                    per_market_withdrawals[market].append({
                        "timestamp": withdrawal['created_at'],
                        "amount": amount
                        })

                self.trans.write(self.packet_ctor.construct_response({
                    "action": "load_wallet",
                    "data": {
                        "cleared": user_obj['cleared'],
                        "market_prices": market_prices,
                        "withdraw": {
                            "net-volume": withdraw_volume,
                            "per-market-volume": dict(per_market_withdrawal_sum),
                            "transactions": dict(per_market_withdrawals)
                            },
                        "deposit": {
                            "net-volume": deposit_volume,
                            "per-market-volume": dict(per_market_deposit_sum),
                            "transactions": dict(per_market_deposits)
                            }
                        }
                    }))
            elif action == "register":
                if self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "you're already logged in"
                    }))
                    return
                elif not (res := server_utils.ensure_contains(
                        self, content, ("email", "username", "password")
                        )):
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "either 'username', 'email' or 'password' wasn't passed"
                    }))
                elif not self.is_recaptcha_verified:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "reCAPTCHA v3 failed for register"
                    }))
                self.is_recaptcha_verified = False
                email, username, password = res
                if username in server.logins:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['register_fail'],
                            format={
                                "$$object": "username",
                                "$$reason": '"username exists"'
                            }
                        )
                    }))
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
                elif not username.strip():
                    return self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['register_fail'],
                            format={
                                "$$object": "username",
                                "$$reason": '"username can\'t be empty"'
                            }
                        )
                    }))

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
#                   "transactions": [],
#                   "deposits": [],
                    "cleared": 0,
                    "xp": 0,
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
                elif not self.is_recaptcha_verified:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "reCAPTCHA v3 failed for login"
                    }))
                self.is_recaptcha_verified = False

                if (tok := content.get("token")):
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
                        "content": f"{username} has come online",
                        "properties": {
                            "font-weight": "600"
                        }
                    })
                    return
                if not (res := server_utils.ensure_contains(
                        self, content, ("email", "password")
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
            elif action == "create_transaction":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['forbidden']
                        )
                    }))
                    return
                elif not (content := server_utils.ensure_contains(
                        self, content, ("type", "currency", "receive_address", "amount")
                        )):
                    pass
                elif not self.is_recaptcha_verified:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "error": "reCAPTCHA v3 not succeeded"
                        }))
                self.is_recaptcha_verified = False
                type_, currency, recv_addr, amount = content

                try:
                    amount = float(amount)
                except ValueError:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['notify'],
                            format={
                                "$$reason": "deposit/withdrawal amount must be decimal",
                                "$$type": "error"
                            }
                        )
                    }))
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": server.read_file(server_constants.SUPPORTED_WS_EVENTS['wallet'])
                    }))
                    return

                if currency not in server_constants.SUPPORTED_CURRENCIES:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['notify'],
                            format={
                                "$$reason": "only BTC/ETH is supported",
                                "$$type": "error"
                            }
                        )
                    }))
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": server.read_file(server_constants.SUPPORTED_WS_EVENTS['wallet'])
                    }))
                    return

                if type_ == "withdrawal":
                    cleared_amount = self.get_user_by_firebase()['cleared']
                    if amount > cleared_amount:
                        return self.trans.write(self.packet_ctor.construct_response({
                            "error": "not enough cleared funds to withdraw this amount"
                            }))
                    self.add_user_withdrawal(content)
                    self.trans.write(self.packet_ctor.construct_response({
                        "success": "server confirmed withdrawal request, check profile for status"
                    }))
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": server.read_file(server_constants.SUPPORTED_WS_EVENTS['wallet'])
                    }))
                elif type_ == "deposit":
                    try:
                        charge = server.coinbase_client.charge.create(name=f'{currency} deposit',
                            description=f'Deposit of {amount!r} {currency}',
                            pricing_type='fixed_price',
                            local_price={
                                "amount": server_utils.crypto_to_usd(amount, currency),
                                "currency": "USD"
                                })
                    except coinbase_commerce.error.InvalidRequestError:
                        return self.trans.write(self.packet_ctor.construct_response({
                                "error": "value must be worth more than $0 USD"
                            }))
                    charge.update({"requested_currency": currency})
                    self.add_user_deposit(charge)
                    print("creating charge for $", server_utils.crypto_to_usd(amount, currency))
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
                            server_constants.SUPPORTED_WS_EVENTS['notify'],
                            format={
                                "$$reason": "server created deposit charge",
                                "$$type": "success"
                            }
                        )
                    }))
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "create_transaction",
                        "data": {
                            "id": charge['id'],
                            "address": charge['addresses'][currency],
                            "amount": charge['pricing'][currency]
                            }
                        }))
            elif action == "check_transaction":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "error": "login to check a transaction" 
                    }))
                    return
                elif not (tx_id := server_utils.ensure_contains(
                        self, content, ("id",)
                        )):
                    return
                tx_id = tx_id[0]

                local_charge = self.get_deposit(tx_id)
                
                if local_charge is not None and local_charge['validated']:
                    return self.trans.write(self.packet_ctor.construct_response({
                        "action": "check_transaction",
                        "data": {
                            "id": tx_id,
                            "pricing": local_charge['pricing'][local_charge['requested_currency']],
                            "state": "completed"
                            }
                        }))

                charge = server.coinbase_client.charge.retrieve(tx_id)

                state = 0   # 0: WAITING, 1: PENDING, 2: COMPLETED
                for event in charge['timeline']:
                    if event['status'] == "UNRESOLVED":
                        if event['context'] == "OVERPAID":
                            return self.trans.write(self.packet_ctor.construct_response({
                                "action": "check_transaction",
                                "data": {
                                    "id": tx_id,
                                    "pricing": charge['pricing'][charge['description'].split()[-1]],
                                    "state": "overpaid"
                                    }
                                }))
                    elif event['status'] == "PENDING":
                        state = max(1, state)
                    elif event['status'] == "COMPLETED":
                        if event['status'] == "OVERPAID":
                            self.trans.write(self.packet_ctor.construct_response({
                                    "warning": "deposit id: {tx_id[:5]}... overpaid"
                                }))
                        state = max(2, state)
                
                if state == 2:
                    self.trans.write(self.packet_ctor.construct_response({
                        "success": f"deposit id: {tx_id[:5]}... has been accredited to your account"
                        }))
                    amount_deposited = float(charge['pricing']['local']['amount'])
                    xp_gained = server_constants.XP_MULTIPLIER * amount_deposited
                    user_obj = self.get_user_by_firebase()
                    self.update_user_by_firebase({
                            "xp": user_obj['xp'] + xp_gained
                        })
                    self.validate_deposit(tx_id)

                self.trans.write(self.packet_ctor.construct_response({
                    "action": "check_transaction",
                    "data": {
                        "id": tx_id,
                        "pricing": charge['pricing'][charge['description'].split()[-1]],
                        "state": ("waiting", "pending confirmations", "completed")[state]
                        }
                    }))
            elif action == "profile_info":
                if not self.authentication:
                    self.trans.write(self.packet_ctor.construct_response({
                        "action": "do_load",
                        "data": self.server.read_file(
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


if __name__ != "__main__":
    raise RuntimeError("this file cannot be imported, it must be run at the top level")

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

if not os.path.isfile("keys/coinbase-commerce.key"):
    raise IOError("Coinbase Commerce key doesn't exist")

with open("keys/coinbase-commerce.key") as cb_key:
    server.coinbase_client = CoinbaseClient(api_key=cb_key.read().strip())
    print("initialized Coinbase Commerce client")

if not os.path.isfile("keys/recaptcha-v3.key"):
    raise IOError("reCAPTCHA v3 key doesn't exist")

with open("keys/recaptcha-v3.key") as captcha_key:
    server.recaptcha_privkey = captcha_key.read().strip()
    print("loaded reCAPTCHA v3 key")

if not os.path.isfile("lotteries.json"):
    raise IOError("`lotteries.json` doesn't exist")

server.active_lotteries = {}
with open("lotteries.json") as lotteries:
    server.lotteries = json.load(lotteries)
    print("loaded lotteries")

for lottery in server.lotteries:
    server.active_lotteries[lottery['name']] = {
            "is_active": False,
            "enrolled_users": [],
            "game_info": {}
            }

server.clients = {}
server.last_pinged = {}
server.message_cache = []
server.pseudo_files = {}

server.firebase = pyrebase.initialize_app({
  "apiKey": "AIzaSyDFl6ewwUVBiG-tyU5nTPGQhYXupdTUd5I",
  "authDomain": "gambling-site-c11d0.firebaseapp.com",
  "storageBucket": "gambling-site-c11d0.appspot.com",
  "databaseURL": "https://gambling-site-c11d0-default-rtdb.firebaseio.com/",
  "serviceAccount": "keys/firebase_key.json"
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
    for client in server.clients.values():
        client.trans.write(client.packet_ctor.construct_response(
            data=b"", opcode=0x8
            ))
    print("exiting gracefully...")
