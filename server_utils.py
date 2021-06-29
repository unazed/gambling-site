from html import escape
import cryptocompare
import hashlib
import json
import random
import requests
from server_api.websocket_interface import WebsocketPacket


with open("filtered-words.txt") as filtered:
    filtered = [*map(str.strip, filtered)]


def generate_server_seed():
    random.seed()
    return int(1e10 * random.random())


def hash_server_seed(seed):
    return hashlib.sha256(seed.to_bytes(seed.bit_length() // 8 + 1, 'little')).hexdigest()


def generate_n_numbers(n, seed):
    random.seed(seed or (seed := random.randint(1, 1e15)))
    _ = (tuple(random.randint(1, 10) for _ in range(n)), seed)  # ??? FIXME
    random.seed()
    return _


def generate_jackpot_winner(jackpot, jackpot_templ):
    random.seed(jackpot['server_seed'])
    proportion = []
    for user, amount in jackpot['enrolled_users'].items():
        if amount is None:
            continue
        proportion.extend([user] * (amount - jackpot_templ['min']))
    result = random.choice(proportion)
    random.seed()
    return result


def get_crypto_prices(markets, timestamp=None):
    for idx, market in enumerate(markets):
        if market == "bitcoin":
            markets[idx] = "BTC"
        elif market == "ethereum":
            markets[idx] = "ETH"
    if timestamp is None:
        return cryptocompare.get_price(markets, currency='USD')
    elif isinstance(markets, list):
        return {market: cryptocompare.get_historical_price(market, currency='USD', timestamp=timestamp) for market in markets}
    return cryptocompare.get_historical_price(markets, currency='USD', timestamp=timestamp)


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


def usd_to_crypto(amount, crypto, timestamp=None):
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
