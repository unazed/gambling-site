from html import escape
import cryptocompare
import json
import requests
from server_api.websocket_interface import WebsocketPacket


with open("filtered-words.txt") as filtered:
    filtered = [*map(str.strip, filtered)]


def get_crypto_prices(markets):
    for idx, market in enumerate(markets):
        if market == "bitcoin":
            markets[idx] = "btc"
        elif market == "ethereum":
            markets[idx] = "eth"
    return cryptocompare.get_price(markets, currency='USD')


def get_recaptcha_response(recaptcha_privkey, token):
    return requests.post("https://www.google.com/recaptcha/api/siteverify", data={
        "secret": recaptcha_privkey,
        "response": token
        }).json()


def crypto_to_usd(amount, crypto):
    if crypto == "bitcoin":
        crypto = "BTC"
    elif crypto == "ethereum":
        crypto = "ETH"
    return amount * get_crypto_prices([crypto])[crypto]['USD']


def usd_to_crypto(amount, crypto):
    if crypto == "bitcoin":
        crypto = "BTC"
    elif crypto == "ethereum":
        crypto = "ETH"
    return amount / get_crypto_prices(crypto)[crypto]["USD"]


def ensure_contains(self, data, keys):
    ret = []
    for key in keys:
        if key not in data:
            self.trans.write(self.packet_ctor.construct_response({
                "error": f"no {escape(key)!r} passed"
            }))
            return False
        ret.append(data[key])
    return ret


def commit_logins(server):
    with open("logins.db", "w") as logins:
        json.dump(server.logins, logins, indent=4)


def commit_clients(server):
    with open("registrar-servers.db", "w") as clients:
        json.dump(server.registrar_servers, clients)


def is_filtered(message):
    if message in filtered:
        return True
    for word in message.split():
        if word in filtered:
            return True
    return False

def get_level(xp_ranges, amount_xp):
    for idx, xp_range in enumerate(xp_ranges):
        if amount_xp < xp_range:
            return idx
    return idx
