# MISPbot

## What is MISPbot?

The MISPbot is a simple tool to allow users to interact with MISP via Mastodon or Twitter.

There are multiple ways to interact with MISP but one approach that was missing is via a *bot*. The [MISPbot](https://github.com/cudeso/mispbot) does just that. It allows users to query MISP or report sightings via a chat bot. Currently is implemented for Mastodon (and template code for Twitter is include), but it can easily be extended to Teams, Slack, Mastodon or other platforms.

To avoid any confusion, there's no AI or LLM involved. You can send basic instructions to the bot (currently **query** : lookup an indicator in MISP and reply with the events and context details and **sighting** : report a sighting) and it will reply back. Obviously you can extend it with your needs.

## Demo bot

A demo of the MISPbot is available via [BOT](BOT). This bot uses a MISP server using a large set of [MISP OSINT feeds](https://www.misp-project.org/feeds/). The bot is configured to
- Only reply to **query**, the **sightings** are ignored
- Query the pending notifications every 15 minutes
- A maximum of **50 requests** per 15 minutes (for all accounts)
- A maximum of **20 hits** per reply

Please be gentle with your requests. If abuse is spotted the demo bot will be stopped.

## Twitter

The bot contains template code for Twitter. Unfortunately for Twitter you need a paid account to get the notifications for your account. If anyone wants to sponsor the demo bot account I'm happy to enable the functionality.

# Setup

## Requirements

- A MISP URL and MISP API key with read permissions
- A Python virtual environment with Python libraries
- A Mastodon (or Twitter) account
- The mispbot code

## Install

1. Install the **Python virtual environment** and requirements

```
python -m venv venv
source venv/bin/activate
pip install Mastodon.py tweepy pymisp
```

2. Get the Mastodon access token.

- Go to Account preferences
- **Development** (most often in the left menu, one of the last options)
- Add a **New application**
- Get the **Access Token**

3. Clone the repository and finish the configuration

```
git clone https://github.com/cudeso/mispbot
cp config.template.py config.py
vi config.py
```

Edit `config.py`

```
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
    "sighting": "sighting"
}
```

Add the bot to a cron job to query for notifications every 15 minutes.

```
CODE
```

## Configuration

The configuration is fairly straightforward in `config.py`. Things to consider are

- Mastodon
  - `visibility`: the visibility status of replies
  - `textcharlimit`: the maximum length of a post, depends on your Mastodon server
- MISP
  - `to_ids`: Only consider attributes that have to_ids to True
  - `tags`: Required tags for a query
  - `info_max_length`: Trim the event title

