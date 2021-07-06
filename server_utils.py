from html import escape
import hashlib
import json
import random
import copy
import requests
from server_api.websocket_interface import WebsocketPacket


COINMARKETCAP_KEY = None
COINMARKETCAP_BASE_URL = "https://pro-api.coinmarketcap.com"


with open("filtered-words.txt") as filtered:
    filtered = [*map(str.strip, filtered)]


def get_coinmarketcap_result(path, *args, **kwargs):
    return requests.get(COINMARKETCAP_BASE_URL + path, *args, **kwargs, headers={
        "X-CMC_PRO_API_KEY": COINMARKETCAP_KEY
        }).json()


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


def is_sufficient_funds(client, amount):
    btc_amount = usd_to_crypto(amount, "bitcoin")
    eth_amount = usd_to_crypto(amount, "ethereum")

    btc_balance = client.get_balance("bitcoin")
    eth_balance = client.get_balance("ethereum")
    
    if btc_balance < btc_amount:
        eth_amount = usd_to_crypto(crypto_to_usd(btc_amount - btc_balance, "BTC"), "ethereum")
    else:
        return {"btc": btc_amount, "eth": 0}

    if eth_balance < eth_amount:
        return False

    return {"btc": btc_balance, "eth": eth_amount}


def generate_jackpot_uid(seed, name):
    random.seed(seed)
    return ''.join(chr(random.randint(97, 122)) for _ in range(16))


def generate_jackpot_winner(jackpot, jackpot_templ):
    random.seed(jackpot['server_seed'])
    jackpot = copy.deepcopy(jackpot)
    jackpot['enrolled_users'] = sorted((user, amount) for user, amount in jackpot['enrolled_users'].items())
    proportion = []
    for user, amount in jackpot['enrolled_users']:
        if amount is None:
            continue
        proportion.extend([user] * (int(amount) - int(jackpot_templ['min']) + 1))
    result = random.choice(proportion)
    return result


def get_crypto_prices(markets):
    result = {}
    if isinstance(markets, str):
        markets = [markets]
    for idx, market in enumerate(markets):
        if market == "bitcoin":
            markets[idx] = "BTC"
            market = "BTC"
        elif market == "ethereum":
            markets[idx] = "ETH"
            market = "ETH"
        try:
            response = get_coinmarketcap_result("/v1/tools/price-conversion", params={
                "amount": 1,
                "symbol": market,
                "convert": "USD"
                })
            result[market] = response['data']['quote']
            result[market]['USD'] = result[market]['USD']['price']
        except KeyError:
            print(response)
    return result

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


CRYPTO_PRICE_CACHE = {}


def usd_to_crypto(amount, crypto, timestamp=None):
    if crypto == "bitcoin":
        crypto = "BTC"
    elif crypto == "ethereum":
        crypto = "ETH"
    price = get_crypto_prices(crypto)
    if price is not None:
        CRYPTO_PRICE_CACHE[crypto] = price
    else:
        if crypto not in CRYPTO_PRICE_CACHE:
            raise ValueError("failed to retrieve cryptocurrency prices")
        return amount / CRYPTO_PRICE_CACHE[crypto][crypto]["USD"]
    return amount / price[crypto]["USD"]


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
