#!/usr/bin/python3
from asyncio.windows_events import NULL
from email.policy import default
from http import cookies
import json
from datetime import datetime, timedelta, timezone
from lib2to3.pgen2 import token
from urllib import response
from dateutil.parser import parse
import requests, configparser, asyncio, aiohttp, tqdm, itertools, time, os

limit = 20  # Number of messages to scan in the channel. MAX: 100
baseurl = "https://discord.com/api/v9"
UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0"
)
XSuper = "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRmlyZWZveCIsImRldmljZSI6IiIsInN5c3RlbV9sb2NhbGUiOiJlbi1VUyIsImJyb3dzZXJfdXNlcl9hZ2VudCI6Ik1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQ7IHJ2Ojk4LjApIEdlY2tvLzIwMTAwMTAxIEZpcmVmb3gvOTguMCIsImJyb3dzZXJfdmVyc2lvbiI6Ijk4LjAiLCJvc192ZXJzaW9uIjoiMTAiLCJyZWZlcnJlciI6IiIsInJlZmVycmluZ19kb21haW4iOiIiLCJyZWZlcnJlcl9jdXJyZW50IjoiIiwicmVmZXJyaW5nX2RvbWFpbl9jdXJyZW50IjoiIiwicmVsZWFzZV9jaGFubmVsIjoic3RhYmxlIiwiY2xpZW50X2J1aWxkX251bWJlciI6MTIxNzE5LCJjbGllbnRfZXZlbnRfc291cmNlIjpudWxsfQ=="
dc_token = "OTYxMjUxNDI1Mzk5MjE0MTMw.Yk2RJw.zmOCa8_fhBAVH_H-sP11LZBetPA"  # fixed

cf = configparser.ConfigParser()
cf.read("config.ini")
# taboo = json.loads(cf["DEFAULT"]["taboo"])
# ended = json.loads(cf["DEFAULT"]["ended"])
taboo = ["bot", "機", "机", "自動", "自动", "測試", "测试", "不要", "不是"]
ended = ["congratulations", "winner", "won"]
sleep_min = float(cf["DEFAULT"]["interval_minutes"])
sleep_time = 60 * sleep_min


def snowflake():
    nonce = int(
        bin(int(time.time_ns() / 1000000) - 1420070400000) + "0000000000000000000000",
        base=2,
    )
    return nonce


def time_now():
    return datetime.now().strftime("%m/%d/%Y, %H:%M:%S")


def chunky_context(ctx):
    chunks, chunk_size = len(ctx), 2000
    return [ctx[i : i + chunk_size] for i in range(0, chunks, chunk_size)]


def generate_context(s_c_pairs, arr, base_string):
    for x in arr:
        emb = x["messages"]["embeds"][0]
        s_c_pair = next(
            item for item in s_c_pairs if item["channel"] == x["channel_id"]
        )
        title = emb["title"] if "title" in emb else "-"
        desc = emb["description"] if "description" in emb else "-"
        desc = desc.replace("\n", "·")
        c_id = s_c_pair["channel"]
        s_id = s_c_pair["server"]
        m_id = x["messages"]["id"]
        uri = f"https://discord.com/channels/{s_id}/{c_id}/{m_id}"

        msg = f"<#{c_id}> : {title} {desc}\n{uri}\n"
        base_string = base_string + msg
    return base_string


async def collect_cookies():
    with requests.get("https://discord.com") as response:
        if response.status_code != 200:
            print("Failed to collect cookies. Restarting.")
            return ""
        else:
            cookies = ""
            # print("Cookies collected: ", response.cookies.get_dict())
            for key, val in response.cookies.get_dict().items():
                cookies = cookies + f"{key}={val}; "
            cookies = cookies + "locale=en-US"


async def owner_id(token):
    response = requests.get(baseurl + "/users/@me", headers={"Authorization": token})
    return response.json()["id"]


async def bot_direct_message(endpoint, data):
    url = f"https://discord.com/api/{endpoint}"
    headers = {
        "Authorization": f"Bot {dc_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    with requests.post(
        url,
        headers=headers,
        json=data,
    ) as res:
        response = res.json()
        if "id" not in response:
            err = (
                response["message"]
                if "message" in response
                else "Unknown Error Occured."
            )
            print(f"[{time_now()}]Error: {err}")
            print(
                "Due to Discord's terms of use, please make sure to avoid the followings:"
            )
            print("- not sharing the same server with the bot.")
            # print("- turned off DM from server members.")
            print("- block the bot.")
            if "retry_after" in response:
                print("retry after: ", response["retry_after"])
            exit(1)
        return response


async def get_server_ids(session, auth_token):
    async with session.get(
        f"{baseurl}/users/@me/guilds",
        headers={"Authorization": auth_token},
    ) as response:
        response = await response.json()
    server_ids = []
    for server in response:
        server_ids.append(server["id"])
    return server_ids


async def get_channel_ids(session, auth_token, server_id):
    async with session.get(
        f"{baseurl}/guilds/{server_id}/channels",
        headers={"Authorization": auth_token},
    ) as response:
        response = await response.json()

    channel_ids = []
    for channel in response:
        if type(channel) != dict:
            continue
        if all(x not in channel["name"].lower() for x in ["giveaway", "獎", "奖"]):
            continue
        if channel["type"] == 0 or channel["type"] == 4 or channel["type"] == 5:
            channel_ids.append({"server": server_id, "channel": channel["id"]})
    return channel_ids


async def get_messages(session, auth_token, channel_id):
    while True:
        async with session.get(
            f"{baseurl}/channels/{channel_id}/messages?limit={limit}",
            headers={"Authorization": auth_token},
        ) as response:
            response = response
            headers = response.headers
            messages = await response.json()
        if "Retry-After" in headers:
            # retry_after = int(response.headers["Retry-After"])
            # print(f"Too many requests! Retrying after {retry_after}s.")
            await asyncio.sleep(5)
            continue
        else:
            break
    return {"messages": messages, "channel_id": channel_id}


### -1: invalid, 0: bot, 1: jackpot, 2: giveaway
def evaluate_message(message, user_id):
    if message == []:
        print("No message")
        return -1

    if "bot" in message["author"] and "reactions" in message:
        if "timestamp" in message:
            msg_time = parse(message["timestamp"])
            time_delta = datetime.now(timezone.utc) - msg_time
            if time_delta > timedelta(days=7):
                return -1
        if "content" in message:
            if any(x in message["content"] for x in taboo):
                return 0
            if any(x in message["content"] for x in ended):
                if user_id in message["content"]:  # jackpot
                    return 1
                return -1
        if "embeds" in message:
            if len(message["embeds"]) == 0:  # not giveaway
                return -1
            # print("check embed")
            emb = message["embeds"][0]
            if "description" in emb:
                # print("check description")
                if any(x in emb["description"].lower() for x in taboo):
                    if "/bot/" not in emb["description"]:
                        return 0
                if any(x in emb["description"].lower() for x in ended):
                    if user_id in message["content"]:  # jackpot
                        return 1
                    return -1
            if "title" in emb:
                if any(x in emb["title"].lower() for x in taboo):
                    return 0
                if any(x in emb["title"].lower() for x in ended):
                    return -1
        for reaction in message["reactions"]:
            if reaction["emoji"]["name"] == "🎉" and reaction["me"] == False:
                return 2

    return -1


async def react_messages(session, auth_token, channel_id, message_id):
    while True:
        async with session.put(
            f"{baseurl}/channels/{channel_id}/messages/{message_id}/reactions/🎉/@me",
            headers={"Authorization": auth_token},
        ) as response:
            headers = response.headers

        if "Retry-After" in headers:
            retry_after = int(response.headers["Retry-After"])
            # print(f"Too many requests! Retrying after {retry_after}s.")
            await asyncio.sleep(10)
            continue
        else:
            break
    return


async def main(auth_token):
    print("Round started.")
    user_id = await owner_id(auth_token)
    user_snowflake = NULL

    newDM = await bot_direct_message(
        "users/@me/channels", {"recipient_id": str(user_id)}
    )

    if newDM == "":
        exit(1)

    user_snowflake = newDM["id"]
    dm_url = f"/channels/{user_snowflake}/messages"

    async with aiohttp.ClientSession() as session:  # create aiohttp session

        ### GET server IDs
        print("Fetching servers...")
        tasks = [get_server_ids(session, auth_token)]
        for t in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            server_ids = await t

        ### GET channel IDs
        print("Fetching channels...")
        tasks = [
            get_channel_ids(session, auth_token, server_id) for server_id in server_ids
        ]
        s_c_pairs = []
        channel_ids = []
        for t in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            s_c_pairs.append(await t)
        s_c_pairs = list(itertools.chain.from_iterable(s_c_pairs))
        channel_ids = [x["channel"] for x in s_c_pairs]

        ### GET messages
        print("Fetching messages...")
        tasks = [
            get_messages(session, auth_token, channel_id) for channel_id in channel_ids
        ]
        channels = []
        for t in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            channels.append(await t)

        bots = []
        jackpots = []
        giveaways = []
        for channel in channels:
            for message in channel["messages"]:
                if type(message) == dict:
                    # to do: change to switch: giveaway, won and bot
                    match evaluate_message(message, user_id):
                        case 0:  # bot
                            bots.append(
                                {
                                    "messages": message,
                                    "channel_id": channel["channel_id"],
                                }
                            )
                        case 1:  # jackpots
                            jackpots.append(
                                {
                                    "messages": message,
                                    "channel_id": channel["channel_id"],
                                }
                            )
                        case 2:  # giveaways
                            giveaways.append(
                                {
                                    "messages": message,
                                    "channel_id": channel["channel_id"],
                                }
                            )

        os.system("cls")
        print("--------------------------")
        context = f"{len(giveaways)} giveaways found!"
        print(context)
        print("--------------------------")
        print()

        if bots:
            ctx = generate_context(s_c_pairs, bots, "👀 Bots Detectors:\n")
            for content in chunky_context(ctx):
                res = await bot_direct_message(
                    dm_url,
                    {"content": content},
                )

        if jackpots:
            ctx = generate_context(s_c_pairs, jackpots, "🎉 Won Giveaways:\n")
            for content in chunky_context(ctx):
                res = await bot_direct_message(
                    dm_url,
                    {"content": content},
                )

        ### React to giveaways
        if giveaways:
            print("Joining...")
            giveaway_ids = []
            for item in giveaways:
                giveaway_ids.append(
                    {
                        "message_id": item["messages"]["id"],
                        "channel_id": item["channel_id"],
                    }
                )
            tasks = [
                react_messages(
                    session,
                    auth_token,
                    giveaway_id["channel_id"],
                    giveaway_id["message_id"],
                )
                for giveaway_id in giveaway_ids
            ]

            responses = []
            for t in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
                responses.append(await t)

            res = await bot_direct_message(dm_url, {"content": context})
            ctx = generate_context(s_c_pairs, giveaways, "✅ Joined Giveaway:\n")
            for content in chunky_context(ctx):
                res = await bot_direct_message(
                    dm_url,
                    {"content": content},
                )

        print(f"Restart after {sleep_min} minutes")
    await asyncio.sleep(sleep_time)


def init():
    config = configparser.ConfigParser()
    config.read("token.ini")
    try:
        token = config["DEFAULT"]["token"]
    except KeyError:
        config["DEFAULT"]["token"] = input(
            "Input authentification token here: "
        ).strip()
        with open("token.ini", "w") as configfile:
            config.write(configfile)
    auth_token = config["DEFAULT"]["token"]

    print()
    print("Read token from file: " + auth_token)
    print()

    with requests.get(
        baseurl + "/users/@me", headers={"Authorization": auth_token}
    ) as response:
        response = response

    if response.status_code == 200:
        id = response.json()["id"]
        user = response.json()["username"]

        print("----------------------")
        print("Logged in with user " + user)
        print("----------------------")
        while True:
            asyncio.get_event_loop().run_until_complete(main(auth_token))

    elif response.status_code == 401:
        open("token.ini", "w").close()  # clear config file
        print("Wrong token!")
        print()
        init()
    elif response.status_code == 429:
        retry_after = response.headers["Retry-After"]
        exit(
            f"Too many requests! \nPlease retry again in {retry_after} seconds ({round(int(retry_after) / 60)} minute(s)).\nAlternatively, change your IP."
        )
    else:
        exit(f"Unknown error! The server returned {response}.")


import warnings

if __name__ == "__main__":
    os.system("cls")
    print("=================================")
    print("Discord Giveaway Bot [ver.0.0.0]\nA project of CAMPERS.")
    print("=================================")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        init()
