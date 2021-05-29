import base64
import json
import os, json
import inspect
import select, socket
import time

import hkdf
from Crypto.Cipher import AES

import dfhe


_print = print
def print(*args, **kwargs):  # pylint: disable=redefined-builtin
    prev_fn = inspect.currentframe().f_back.f_code.co_name
    _print(f"[{time.strftime('%H:%M:%S')}] [ServiceClient] [{prev_fn}]",
           *args, **kwargs)


def send_json(sock, data, encryption=None, pad=None):
    data = json.dumps(data).encode()
    if encryption is not None:
        data = encryption(data if pad is None else pad(data))
    sock.send(data)


def pad(data, boundary=16, padding=b'\0'):
    return data + padding * (boundary - (len(data) % boundary))


def start_client(address, port):
    sock = socket.socket()
    
    expect_aes = False

    poll = select.poll()
    poll.register(sock, select.POLLIN | select.POLLPRI | select.POLLOUT | select.POLLERR)

    print(f"connecting to '{address}:{port}'")
    sock.connect((address, port))
    print("connected, waiting for domain parameters")
    sock.setblocking(False)

    while (client_event := poll.poll()):
        client_event = client_event[0]
        if client_event[1] & select.POLLIN or client_event[1] & select.POLLPRI:
            try:
                recv = sock.recv(2048)
                if not recv:
                    print("server sent EOF, closing")
                    return
                elif not expect_aes:
                    data = json.loads(recv)
                else:
                    data = json.loads(aes_dec.decrypt(recv).rstrip(b'\0'))
            except json.JSONDecodeError:
                print("server sent invalid JSON data, probably an internal error")
                return

            if data['action'] == 'authenticate':
                print("processing DFHE key-exchange information")
                domain_params = data['data']['domain_parameters']
                privkey = dfhe.generate_privkey(domain_params)
                server_pubkey = int.from_bytes(base64.b64decode(data['data']['pubkey']), 'big')
                send_json(sock, {
                    "action": "authenticate",
                    "data": {
                        'pubkey': base64.b64encode(
                            dfhe.dfhe_create_pubkey(domain_params, privkey).to_bytes(512//8, 'big')
                            ).decode()
                        }
                    })
                sharedkey = dfhe.dfhe_create_sharedkey(domain_params, server_pubkey, privkey)
            elif data['action'] == 'init_aes':
                print("initializing HKDF-AES ciphers")
                sharedkey_bytes = sharedkey.to_bytes(512//8, 'big')
                prk = hkdf.hkdf_extract(base64.b64decode(data['data']['hkdf_salt']), sharedkey_bytes)

                dec_iv = base64.b64decode(data['data']['dec_iv'])
                enc_iv = base64.b64decode(data['data']['enc_iv'])
                
                aes_enc = AES.new(hkdf.hkdf_expand(prk, sharedkey_bytes, 32), AES.MODE_CBC, iv=dec_iv)
                aes_dec = AES.new(hkdf.hkdf_expand(prk, sharedkey_bytes, 32), AES.MODE_CBC, iv=enc_iv)
                
                send_json(sock, {
                    "action": "verify"
                    }, encryption=aes_enc.encrypt, pad=pad)
                print("verifying encryption integrity with server")
                expect_aes = True
            elif data['action'] == 'verify':
                print(f"AES integrity ensured for server")
            elif data['action'] == "ping":
                print("pinged")
                send_json(sock, {"action": "pong"}, encryption=aes_enc.encrypt, pad=pad)
            else:
                print(f"got unexpected data: {data!r}")

if __name__ == "__main__":
    if not os.path.isfile("connection.cfg"):
        raise IOError("'connection.cfg' must exist")
    with open("connection.cfg") as con_info:
        try:
            con_info = json.load(con_info)
        except json.JSONDecodeError:
            raise ValueError("improperly formatted connection configuration")

    for key in ("address", "port"):
        if key not in con_info:
            raise KeyError(f"{key!r} missing from connection configuration")

    start_client(con_info['address'], int(con_info['port']))

