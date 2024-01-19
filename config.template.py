mastodon_config = {
    "access_token": "",
    "api_base_url": "https://mastodon.social/",
    "username": "",
    "max_mentions": 50,
    "visibility": "public",
    "textcharlimit": 500,
}

misp_config = {
    "url": "",
    "verifycert": False,
    "key": "",
    "to_ids": None,
    "tags": ["tlp:white"],
    "published": True,
    "limit": 20,
    "warninglist": False,
    "info_max_length": 30,
}

log_file = "/var/log/misp/mispbot.log"

bot_command = {
    "query": "query",
    "sighting": "sighting",
    "help": "help"
}
