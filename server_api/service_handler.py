import base64
import inspect
import json
import secrets
import select, socket
import time

import hkdf
from Crypto.Cipher import AES
from . import dfhe


_print = print
def print(*args, **kwargs):  # pylint: disable=redefined-builtin
    prev_fn = inspect.currentframe().f_back.f_code.co_name
    _print(f"[{time.strftime('%H:%M:%S')}] [ServiceClientHandler] [{prev_fn}]",
           *args, **kwargs)


def pad(data, boundary=16, padding=b'\0'):
    return data + padding * (boundary - (len(data) % boundary))


class Client:
    def __init__(self, sock, info, pipe, delay=100, bitlength=512):
        print(f"new connection from {info!r}")
        self.authenticated = False
        self.aes_integrity = False
        self.attempts = 0

        self.sock = sock
        self.info = info
        self.delay = delay
        self.pipe = pipe
        self._bitlength = bitlength

        self.poll = select.poll()
        self.sock.setblocking(False)
        self.poll.register(self.sock, select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLOUT)

        self.domain_params = dfhe.generate_domain_parameters(bitlength)
        print(f"generating cryptographic information, group order is {bitlength} bits")
        self.privkey = dfhe.generate_privkey(self.domain_params)
        self.pubkey = dfhe.dfhe_create_pubkey(self.domain_params, self.privkey)
        self.sharedkey = None

        self.aes_enc = None
        self.aes_dec = None

    def aes_initialize(self):
        if self.sharedkey is None:
            raise ValueError("can't initialize AES ciphers with no sharedkey")
        print("initializing HKDF-AES dec./enc. ciphers with sharedkey")
        sharedkey_bytes = self.sharedkey.to_bytes(self._bitlength//8, 'big')
        prk = hkdf.hkdf_extract(
                (salt := secrets.randbits(16 * 8).to_bytes(16, 'big')),
                sharedkey_bytes
                )
        self.aes_enc = AES.new(hkdf.hkdf_expand(prk, sharedkey_bytes, 32), AES.MODE_CBC)
        self.aes_dec = AES.new(hkdf.hkdf_expand(prk, sharedkey_bytes, 32), AES.MODE_CBC)
        return (
                base64.b64encode(salt).decode(),
                base64.b64encode(self.aes_dec.iv).decode(),
                base64.b64encode(self.aes_enc.iv).decode()
                )

    def aes_decrypt(self, data):
        return self.aes_dec.decrypt(data)

    def is_writeable(self):
        ev = self.poll.poll(self.delay)
        if ev[0][1] & select.POLLOUT:
            return True
        return False

    def is_readable(self):
        ev = self.poll.poll(self.delay)
        if ev[0][1] & select.POLLIN:
            return True
        return False

    def is_error(self):
        ev = self.poll.poll(self.delay)
        if ev[0][1] & select.POLLERR:
            return True
        return False

    def send_json(self, data, do_encrypt=False):
        if self.is_writeable():
            data = json.dumps(data).encode()
            if do_encrypt:
                data = self.aes_enc.encrypt(pad(data))
            self.sock.send(data)

    def authenticate(self):
        if not self.is_writeable():
            print('client not writeable')
            return
        elif self.is_readable():
            try:
                data = json.loads(read_all(self.sock, poll_obj=self.poll))
            except (json.JSONDecodeError, TypeError):
                print(f"client '{self.info}' sent invalid json, closing...")
                return False
            
            for key in ("action", "data"):
                if key not in data:
                    self.send_json({
                        "action": "error",
                        "data": f"missing {key!r} key"
                        })
                    return False
            
            if data['action'] != "authenticate":
                self.send_json({
                    "action": "error",
                    "data": f"expected authentication procedure"
                    })
                return False
            elif 'pubkey' not in data['data']:
                self.send_json({
                    "action": "error",
                    "data": f"expected data['pubkey']"
                    })
                return False

            client_pubkey = int.from_bytes(base64.b64decode(data['data']['pubkey']), 'big')
            self.sharedkey = dfhe.dfhe_create_sharedkey(self.domain_params, client_pubkey, self.privkey)
            salt, dec_iv, enc_iv = self.aes_initialize()
            self.send_json({
                "action": "init_aes",
                "data": {
                    "hkdf_salt": salt,
                    "dec_iv": dec_iv,
                    "enc_iv": enc_iv
                    }
                })
            self.authenticated = True
        else:
            self.send_json({
                "action": "authenticate",
                "data": {
                    "domain_parameters": self.domain_params,
                    "pubkey": base64.b64encode(self.pubkey.to_bytes(self._bitlength//8, 'big')).decode()
                    }
                })
            self.attempts += 1
        return self.attempts != 3

    def data_received(self, data):
        try:
            data = json.loads(self.aes_decrypt(data).rstrip(b'\0'))
        except json.JSONDecodeError:
            print(f"{self.info!r} sent invalid JSON, likely AES wasn't established")
            return False

        if not (action := data.get("action", "")):
            self.send_json({
                "action": "error",
                "data": "no 'action' sent"
                }, do_encrypt=True)
        elif not self.aes_integrity and action != "verify":
            self.send_json({
                "action": "error",
                "data": "must send 'verify' action"
                }, do_encrypt=True)
        elif not self.aes_integrity:
            print(f"AES integrity for {self.info!r} ensured")
            self.send_json({
                "action": "verify"
                }, do_encrypt=True)
            self.aes_integrity = True

        if action == "pong":
            self.pipe.send({
                "action": "pong",
                "data": {
                    "time": time.time(),
                    "address": self.info[0]
                    }
                })


def on_data_received(sock, data):
    print(f"got data {data!r} from {sock.getpeername()}")


def read_all(sock, chunk_size=1, timeout=100, poll_obj=None):
    data = sock.recv(chunk_size)
    if poll_obj is not None:
        poll = poll_obj
    else:
        poll = select.poll()
        poll.register(sock, select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP)
    while (ev := poll.poll(timeout)):
        ev = ev[0]
        if ev[1] & select.POLLERR or ev[1] & select.POLLHUP:
            return
        elif ev[1] & select.POLLIN or ev[1] & select.POLLPRI:
            data += (recv := sock.recv(chunk_size))
            if not recv:
                return
        else:
            break
    return data
    

def start_client_listener(addr, port, pipe, backlog=5, delay=100):
    print(f"starting client listener on '{addr}:{port}'")

    server = socket.socket()
    
    poll = select.poll()
    poll.register(server, select.POLLIN | select.POLLPRI | select.POLLERR)

    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(False)
    server.bind((addr, port))
    server.listen(backlog)

    clients = []
    whitelist = {}

    while (server_event := poll.poll(delay), True)[1]:
        if server_event:
            server_event = server_event[0]
            if server_event[1] & select.POLLERR:
                print("server encountered error, closing...")
                for client in clients:
                    client.sock.close()
                return server.shutdown(socket.RDWR)
            elif server_event[1] & select.POLLIN or server_event[1] & select.POLLPRI:
                conn, addr = server.accept()
                if addr[0] not in whitelist:
                    print(f"non-whitelisted address {addr[0]!r} tried to connect")
                    conn.close()
                else:
#                    pipe.send({
#                        "action": "successful",
#                        "data": {
#                            "address": addr[0],
#                            "name": whitelist[addr[0]]
#                            }
#                        })
                    print(f"whitelisted client {addr[0]!r} connected")
                    clients.append(Client(conn, addr, pipe))

        if pipe.poll():  # check for server <-> client-listener comms.
            data = pipe.recv()
            if data['action'] == "init_whitelist":
                print("client whitelist loaded, IPC is working")
                whitelist = data['data']
            elif data['action'] == "whitelist":
                whitelist[data['data']['address']] = data['data']['name']
            elif data['action'] == "remove":
                if data['data'] not in whitelist:
                    pipe.send({
                        "action": "notify",
                        "data": "server address doesn't exist"
                        })
                else:
                    del whitelist[data['data']]
                    pipe.send({
                        "action": "notify",
                        "data": f"server was removed successfully"
                        })
            elif data['action'] == "ping":
                if (addr := data['data']) not in whitelist:
                    pipe.send({
                        "action": "notify",
                        "data": "server address doesn't exist"
                        })
                else:
                    for client in clients:
                        if client.info[0] == addr:
                            if not client.authenticated or not client.aes_integrity:
                                pipe.send({
                                    "action": "notify",
                                    "data": "client isn't yet authenticated or their communication isn't yet secured"
                                    })
                            else:
                                client.send_json({
                                    "action": "ping"
                                    }, do_encrypt=True)
                            break
                    else:
                        pipe.send({
                            "action": "notify",
                            "data": "no connected clients with such address"
                            })
        for client in clients:
            if client.is_error():
                print(f"closing {client.info!r}")
                client.sock.close()
                clients.remove(client)
                continue
            elif not client.authenticated:
                if not client.authenticate():
                    print(f"failed to authenticate with {client.info!r}, closing")
                    clients.remove(client)
                    client.sock.close()
                continue
            elif client.is_readable():
                data = read_all(client.sock, poll_obj=client.poll)
                if data is None:
                    print(f"received EOF, closing {client.info!r}")
                    client.sock.close()
                    clients.remove(client)
                else:
                    if client.data_received(data) is False:
                        print(f"client handler closing connection with {client.info!r}")
                        client.sock.close()
                        clients.remove(client)

