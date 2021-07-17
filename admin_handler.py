import json
import time
import inspect
import server_api
from server_api.websocket_interface import WebsocketPacket, CompressorSession
from server_utils import get_level
from server_constants import LEVEL_INDICES

_print = print


def print(*args, **kwargs):  # pylint: disable=redefined-builtin
    curframe = inspect.currentframe().f_back
    prev_fn = curframe.f_code.co_name
    line_no = curframe.f_lineno
    class_name = ""
    if (inst := curframe.f_locals.get("self")) is not None:
        class_name = f" [{inst.__class__.__name__}]"
    _print(f"[{time.strftime('%H:%M:%S')}] :{line_no} [AdminHandler]{class_name} [{prev_fn}]",
           *args, **kwargs)


def identified(fn):
    def inner(self, *args, **kwargs):
        if not self.authentication['identified']:
            return self.error("You must be identified to perform this action")
        return fn(self, *args, **kwargs)
    return inner


def chain(fn):
    def inner(self, *args, **kwargs):
        fn(self, *args, **kwargs)
        return self
    return inner


def authenticated(fn):
    def inner(self, *args, **kwargs):
        if not self.authentication['logged_in']:
            return self.error("You must be logged in to perform this action")
        return fn(self, *args, **kwargs)
    return inner


def when_authenticated(event_name):
    def inner(self):
        if self.authentication['logged_in']:
            return event_name
        return False
    return inner


class AdminWebsocketClient:
    event_map = {
        "login": "login.js",
        "home": when_authenticated("home.js")
        }

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
        self.send = lambda *args, **kwargs: (True, self.trans.write(self.packet_ctor.construct_response(*args, **kwargs)))[0]

        self.__is_final = True
        self.__data_buffer = ""

        self.authentication = {
                "ip_address": None,
                "identified": False,
                "logged_in": False
                }

    @chain
    def error(self, reason):
        return self.send({
            "action": "notify",
            "type": "error",
            "reason": reason
            })

    @chain
    def info(self, reason):
        return self.send({
            "action": "notify",
            "type": "info",
            "reason": reason
            })

    @chain
    def success(self, reason):
        return self.send({
            "action": "notify",
            "type": "success",
            "reason": reason
            })

    @chain
    def add_log_message(self, message):
        return self.server.firebase_db.child("logs").push({
            "logged_at": time.time(),
            "authentication": self.authentication,
            "message": message
            })

    def is_admin(self, username, password):
        login = self.server.firebase_db.child("admin").get().val()
        return login['username'] == username and login['password'] == password

    def get_user_by_firebase(self, username):
        return [*self.server.firebase_db                    \
                .child("users")                             \
                .order_by_child("username")                 \
                .equal_to(username)                         \
                .get().val().values()][0]

    def get_user_deposits(self, username):
        return self.server.firebase_db.child("deposits").child(username).get().val()

    def get_withdrawals(self):
        return self.server.firebase_db.child("withdrawals").get().val()

    def get_user_withdrawals(self, username):
        return self.server.firebase_db.child("withdrawals").child(username).get().val()

    @chain
    def load_event(self, event_name):
        if (path := self.event_map.get(event_name)) is None:
            return self.error("No such event exists")
        elif callable(path) and not (path := path(self)):
            return self.error("You must be logged in to perform this action")
        return self.add_log_message(f"Loading event {event_name!r}") \
                   .send({
                       "action": "load",
                       "data": self.server.read_file(f"admin/events/{path}")
                   })

    @chain
    def load_callback(self, callback, data):
        return self.send({
            "action": "callback",
            "name": callback,
            "data": data
            })

    @authenticated
    def action_remove_deposit(self, username, uid):
        self.add_log_message(f"Removing deposit {uid!r} from {username!r}")
        return self.server.firebase_db.child("deposits").child(username).child(uid).remove()

    @authenticated
    def action_validate_deposit(self, username, uid):
        deposit = self.server.firebase_db.child("deposits").child(username).child(uid).get().val()
        self.add_log_message( ("Invalidating" if deposit['validated'] else "Validating") + f" {uid!r} from {username!r}")
        return self.server.firebase_db.child("deposits").child(username).child(uid).update({
            "validated": not deposit['validated']
            })

    @authenticated
    def action_remove_withdrawal(self, username, uid):
        self.add_log_message(f"Removing withdrawal {uid!r} from {username!r}")
        return self.server.firebase_db.child("withdrawals").child(username).child(uid).remove()

    @authenticated
    def action_validate_withdrawal(self, username, uid):
        withdrawal = self.server.firebase_db.child("withdrawals").child(username).child(uid).get().val()
        self.add_log_message( ("Invalidating" if withdrawal['validated'] else "Validating") + f" {uid!r} from {username!r}")
        return self.server.firebase_db.child("withdrawals").child(username).child(uid).update({
            "validated": not withdrawal['validated']
            })

    @authenticated
    def action_load_userlist(self):
        return self.load_callback("load_userlist",
            list(self.server.firebase_db.child("users").get().val().values())
            )

    @authenticated
    def action_load_action(self, name, username=None):
        if username is None:
            user_data, user_deposits = None, None
            user_withdrawals = self.get_withdrawals()
        else:
            user_data = self.get_user_by_firebase(username)
            user_data['level'] = get_level(LEVEL_INDICES, user_data['xp'])
            user_deposits = self.get_user_deposits(username)
            user_withdrawals = self.get_user_withdrawals(username)

        self.add_log_message(f"{name!r} on {username!r}")
        return self.load_callback({
            "view-profile": "on_view_profile",
            "view-withdrawals": "on_view_withdrawals",
            "view-deposits": "on_view_deposits",
            "view-lotteries": "on_view_lotteries",
            "view-jackpots": "on_view_jackpots",
            "pending-withdrawals": "on_withdrawal_load",
            "disable": "on_user_toggle_disable"
            }[name], {
                "profile": user_data,
                "deposits": user_deposits,
                "withdrawals": user_withdrawals
                })
        
    @identified
    def action_login(self, username, password):
        if not self.is_admin(username, password):
            return self.add_log_message("Failed to log-in")     \
                       .error("Failed to log-in")
        self.authentication['logged_in'] = True
        return self.add_log_message("Logged in successfully")   \
                   .success("Logged in successfully")           \
                   .load_event("home")

    @authenticated
    def action_toggle_user_disable(self, username):
        userkey = [*self.server.firebase_db.child("users").order_by_child("username")              \
                                      .equal_to(username)  \
                                      .get().val().keys()][0]
        user = self.get_user_by_firebase(username=username)
        return self.server.firebase_db.child("users").child(userkey).update({
            "disabled": not user.get("disabled", False)
            })

    def action_ping(self):
        self.send(data=b"", opcode=0x09)
        return self.send({"action": "pong"})

    def action_identify(self):
        if (ip := self.headers.get("x-forwarded-for")) is None:
            return self.error("Your IP address wasn't forwarded")
        self.authentication.update({
            "ip_address": ip,
            "identified": True
            })
        return self.add_log_message(f"Identified connection {ip!r}")\
                   .send({
                       "action": "identify",
                       **self.authentication
                   })

    @identified
    def action_load(self, name):
        return self.load_event(name)

    def __call__(self, prot, addr, data):
        if self.__data_buffer:
            data = self.__data_buffer
        data = self.packet_ctor.parse_packet(data)
        if data['extra']:
            self.__call__(prot, addr, data['extra'])
        self.__is_final = data['is_final']
        if not self.__is_final:
            self.__data_buffer += data['data']
            return
        elif self.__data_buffer:
            data = self.packet_ctor.parse_packet(self.__data_buffer + data['data'])
            self.__data_buffer = ""

        if data['opcode'] == 0x08:
            self.send(data=b"", opcode=0x08)
            return self.trans.close()
        elif data['opcode'] == 0x0A:
            return
        elif data['opcode'] == 0x01:
            try:
                client_data = json.loads(data['data'])
            except json.JSONDecodeError:
                return self.error("Invalid JSON received")
            actions = {fn: getattr(self, fn) for fn in dir(self) if fn.startswith("action_")}
            if (action := client_data.get("action")) is None:
                return self.error("Packet must contain 'action' parameter")
            elif (fn := actions.get(f"action_{action}")) is None:
                return self.error("No such action exists")
            del client_data['action']
            try:
                return fn(**client_data)
            except TypeError:
                return self.error("Missing parameters for action")

    def on_close(self, prot, addr, reason):
        ip = self.headers.get("cf-connecting-ip", addr[0])
        print(f"closed websocket with {ip!r}, reason={reason!r}")

