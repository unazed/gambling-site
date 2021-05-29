import asyncio
import aiohttp
import string
import sys
import inspect, time
import server_constants


GLOBAL_SC_CACHE = {}
GLOBAL_TT_CACHE = {}
_print = print


def print(*args, **kwargs):  # pylint: disable=redefined-builtin
    curframe = inspect.currentframe().f_back
    prev_fn = curframe.f_code.co_name
    class_name = ""
    if (inst := curframe.f_locals.get("self")) is not None:
        class_name = f" [{inst.__class__.__name__}]"
    _print(f"[{time.strftime('%H:%M:%S')}] [Services]{class_name} [{prev_fn}]",
           *args, **kwargs)


def service_notify(client, message):
    client.trans.write(client.packet_ctor.construct_response({
        "action": "do_load",
        "data": client.server.read_file(
            server_constants.SUPPORTED_WS_EVENTS['service_notify'],
            format={
                "$$message": f'"{message}"'
            }
        )
    }))


async def twitchtv(client, usernames, callback, id):
    current = 0
    total = len(usernames)
    results = {}

    # sorting any quick matches
    for username in usernames.copy():
        print(username)
        if len(username) <= 4:
            service_notify(client, f"[twitchtv#{id}] removing {username} because it's too short")
            results[username] = True
            usernames.remove(username)
        elif (res := GLOBAL_TT_CACHE.get(username, False)):
            when, is_taken = res
            if time.time() - when <= 3600:
                service_notify(client, f"[twitchtv#{id}] retrieving cached result for {username}")
                results[username] = is_taken
                usernames.remove(username)
                continue
    if not usernames:
        callback(id)
        return results

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
            use_dns_cache=False, verify_ssl=False
            )) as session:
        async with session.get("https://twitchusernames.com/login") as res:
            token = (await res.text()).split("name=\"_token\" value=\"")[1].split("\"")[0]
        async with session.post("https://twitchusernames.com/login", data={
                "_token": token,
                "email": "unazedv4@protonmail.com",
                "password": "likliklik123"
                }) as _:
            pass
        while usernames:
            current += 1
            username = usernames.pop(0)
            service_notify(client, f"[twitchtv#{id}] [{current}/{total}] checking {username}")
            async with session.get(f"https://twitchusernames.com/usernames/search?search={username}", headers={
                    "x-requested-with": "XMLHttpRequest"
                    }) as res:
                print(res.status)
                results[username] = (is_taken := res.status != 200)
                GLOBAL_TT_CACHE[username] = (time.time(), is_taken)
    callback(id)
    return results

async def snapchat(client, usernames, callback, id):
    results = {}
    retry = current = 0
    total = len(usernames)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
                use_dns_cache=False, verify_ssl=False
            )) as session:
        while usernames:
            if not retry:
                username = usernames.pop(0)
                current += 1
                service_notify(client, f"[snapchat#{id}] [{current}/{total}] checking {username}")
            if username in results:
                continue
            elif username in GLOBAL_SC_CACHE:
                when, is_taken = GLOBAL_SC_CACHE[username]
                if time.time() - when <= 3600:
                    results[username] = is_taken
                    continue
            async with session.get(
                    "https://accounts.snapchat.com/accounts/signup",
                    headers={
                        "User-Agent": "python-requests/2.23.0",
                        "Accept-Encoding": "gzip, deflate",
                        "Accept": "*/*",
                        "Connection": "keep-alive"
                    }) as res:
                xsrf = (await res.text()).split("data-xsrf=\"")[1].split("\"")[0]
            async with session.post(
                    "https://accounts.snapchat.com/accounts/get_username_suggestions",
                    data={
                        "requested_username": username,
                        "xsrf_token": xsrf
                        },
                    cookies={
                        "xsrf_token": xsrf
                    }) as res:
                try:
                    results[username] = (await res.json())['reference']['status_code'] != "OK"
                    GLOBAL_SC_CACHE[username] = (time.time(), results[username])
                except Exception as exc:
                    service_notify(client, f"[snapchat#{id}] retrying {username}")
                    if not retry:
                        retry = server_constants.RETRY_ATTEMPTS
                    else:
                        retry -= 1
                    await asyncio.sleep(5)
                    continue
                else:
                    retry = 0
    callback(id)
    return results


async def tiktok(client, usernames, callback, id):
    return callback(id)


def schedule_service(client, loop, service_name, usernames, callback, id):
    print("scheduling service", service_name)
    return loop.create_task(
        globals()[''.join(
            filter(lambda c: c in string.ascii_letters, service_name.lower())
        )](client, usernames, callback, id))
