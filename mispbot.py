import re
from mastodon import *
from pymisp import *
import sys
import logging
from config import *


class twitter_handler:
    def __init__(self, twitter_config, misp_config, logger):
        self.logger = logger
        self.mastodon_config = twitter_config
        self.misp_config = misp_config

        auth = tweepy.OAuthHandler(twitter_config["api_key"], twitter_config["api_key_secret"])
        auth.set_access_token(twitter_config["access_token"], twitter_config["access_token_secret"])

        self.client = tweepy.API(auth)
        self.username = twitter_config["username"]
        self.mentions = False
        self.replies = {}
        self.sightings = {}
        self.remaining_notifications = {}
        self.logger.info("Init bot {}".format(self.username))       

        if misp_config["verifycert"] is False:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.misp = ExpandedPyMISP(misp_config["url"], misp_config["key"], misp_config["verifycert"], debug=False)         

    def close(self):
        self.logger.info("Stop bot {}".format(self.username))

    def fetch_mentions(self):
        self.logger.info("Fetch mentions for {}".format(self.username))
        self.mentions = self.client.mentions_timeline()


class mastodon_handler:
    def __init__(self, mastodon_config, misp_config, logger):
        self.logger = logger
        self.mastodon_config = mastodon_config
        self.misp_config = misp_config

        self.client = Mastodon(
                        access_token=mastodon_config["access_token"],
                        api_base_url=mastodon_config["api_base_url"]
                        )
        self.username = mastodon_config["username"]
        self.account_id = False
        self.mentions = False
        self.replies = {}
        self.sightings = {}
        self.remaining_notifications = {}
        self.logger.info("Init bot {}".format(self.username))

        account_search = self.client.account_search(self.username)
        if len(account_search) > 0 and account_search[0].get("id", False):
            self.account_id = account_search[0]["id"]
            self.logger.debug("Found account ID {}".format(self.account_id))
        else:
            self.logger.error("Unable to find account ID for {}".format(self.username))
            sys.exit()

        if misp_config["verifycert"] is False:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.misp = ExpandedPyMISP(misp_config["url"], misp_config["key"], misp_config["verifycert"], debug=False)

    def close(self):
        self.logger.info("Stop bot {}".format(self.username))

    def fetch_mentions(self):
        self.logger.info("Fetch mentions for {}".format(self.username))
        try:
            if self.account_id:
                mentions = self.client.notifications(types=["mention"], limit=self.mastodon_config["max_mentions"])
                self.logger.info("Received {} mentions".format(len(mentions)))
                self.mentions = mentions
                return self.mentions
        except MastodonNotFoundError as e:
            self.logger.error("Fetch mentions")
            self.logger.error("MastodonNotFoundError: {} on line {}".format(e, e.__traceback__.tb_lineno))
            return False
        except:
            self.logger.error("Error while processing mentions for {}".format(self.username))
            return False

    def print_mentions(self):
        if self.mentions:
            for mention in self.mentions:
                print(mention, "\n")

    def process_mentions(self):
        if self.mentions:
            for mention_item in self.mentions:
                account = {"account": mention_item["account"]["username"].strip(),
                            "url": mention_item["account"]["url"].strip()}
                mention = {"id": mention_item["id"],
                           "conversation": mention_item["status"]["id"],
                           "url": mention_item["status"]["url"],
                           "content": False}
                self.logger.debug("Working on {} {}".format(mention["id"], mention["url"]))

                mention_content = mention_item["status"]["content"].strip().split("</span></a></span>")
                if len(mention_content) > 0:
                    clean = re.compile('<.*?>')
                    mention["content"] = re.sub(clean, '', mention_content[1].strip())

                if mention["content"]:
                    self.logger.info("Mention {} from {} : '{}'".format(mention["id"], account["account"], mention["content"]))

                    if mention["content"].startswith(bot_command["query"]):
                        try:
                            indicator = mention["content"].split(bot_command["query"])[1].strip()
                            self.logger.info(" {} - {} - indicator {}".format(account["account"], bot_command["query"], indicator))
                            self.replies[mention["id"]] = {"conversation": mention["conversation"], "misp": self.misp_query(indicator)}
                        except IndexError as e:
                            logger.error("Error: {} on line {}".format(e, e.__traceback__.tb_lineno))
                        except:
                            logger.error("Error when isolating indicator")
                    elif mention["content"].startswith(bot_command["sighting"]):
                        try:
                            indicator = mention["content"].split(bot_command["sighting"])[1].strip()
                            self.logger.info(" {} - {} - indicator {}".format(account["account"], bot_command["sighting"], indicator))
                            self.sightings[mention["id"]] = {"conversation": mention["conversation"], "misp": self.misp_sighting(indicator, account["account"])}
                        except IndexError as e:
                            self.logger.error("Error: {} on line {}".format(e, e.__traceback__.tb_lineno))
                        except:
                            self.logger.error("Error when isolating indicator")
                    else:
                        try:
                            self.remaining_notifications[mention["id"]] = {"conversation": mention["conversation"]}
                        except IndexError as e:
                            self.logger.error("Error: {} on line {}".format(e, e.__traceback__.tb_lineno))
                        except:
                            self.logger.error("Error when processing command")
                else:
                    self.logger.error("Unable to extract content from mention {}".format(mention["content"]))
        else:
            self.logger.info("No mentions available")

    def convert_to_reply(self, misp_result):
        message = ""
        if len(misp_result) > 0:
            for result in misp_result:
                if len(result["context"]) > 0:
                    context = "\n  {}".format(result["context"])
                else:
                    context = ""
                message = "{} Found in: {} ({} / {} / {} / {}){}\n\n".format(message, result["info"], result["date"], result["uuid"], result["threat_level"], result["analysis"], context)

        else:
            message = "Not found"
        return message

    def reply(self):
        for status_id in self.replies:
            message = self.convert_to_reply(self.replies[status_id]["misp"])
            conversation = self.replies[status_id]["conversation"]
            self.reply_status(status_id, conversation, message)

    def reply_status(self, status_id, conversation, message):
        self.logger.info("Reply mentions for {} {}".format(status_id, conversation))
        if status_id > 0 and len(message) > 0:
            try:
                for i in range(0, len(message), self.mastodon_config["textcharlimit"]):
                    chunk = message[i:i + self.mastodon_config["textcharlimit"]]
                    status_post = self.client.status_post(chunk, in_reply_to_id=conversation, visibility=self.mastodon_config["visibility"])
                    self.logger.debug("Replied {} {}".format(status_id, conversation))
                self.logger.debug("Finished replying to {} {}".format(status_id, conversation))
            except:
                self.logger.error("Error when replying to {}".format(status_id))

    def misp_sighting(self, indicator, username):
        self.misp.add_sighting({"value": indicator, "source": "MISPbot {}".format(username)})
        self.logger.info("Sighting {} of {}".format(username, indicator))        

    def misp_query(self, indicator):
        misp_result = []
        event_matches = []
        search_match = self.misp.search("attributes", to_ids=self.misp_config.get("to_ids", True), value=indicator, tags=self.misp_config.get("tags", []),
                                        published=self.misp_config.get("published", True), limit=self.misp_config.get("limit", 100), 
                                        enforceWarninglist=self.misp_config.get("warninglist", True), pythonify=True)
        if len(search_match) > 0:
            self.logger.info("Found {} results for {}".format(len(search_match), indicator))
            for attribute in search_match:
                if attribute.Event.uuid not in event_matches:
                    event_matches.append(attribute.Event.uuid)
                    event_details = self.misp.search("events", uuid=attribute.Event.uuid, pythonify=True)[0]
                    event_tags = []
                    for tag in event_details.tags:
                        if tag.name not in event_tags:
                            event_tags.append(tag.name.strip())
                    for tag in attribute.tags:
                        if tag.name not in event_tags:
                            event_tags.append(tag.name.strip())
                    misp_result_tags = ""
                    for tag in event_tags:
                        misp_result_tags = "{}{} ".format(misp_result_tags, tag)

                    misp_result.append({"id": attribute.Event.id,
                                            "uuid": attribute.Event.uuid,
                                            "organisation": event_details.Orgc,
                                            "info": attribute.Event.info.strip()[:self.misp_config["info_max_length"]].replace("\n", "").replace("\r", ""),
                                            "date": event_details.date,
                                            "threat_level": ThreatLevel(event_details.threat_level_id),
                                            "analysis": Analysis(event_details.analysis),
                                            "context": misp_result_tags})
        return misp_result

    def clear_remaining_notifications(self):
        for status_id in self.remaining_notifications:
            try:
                self.client.notifications_dismiss(status_id)
                self.logger.info("Dismiss remaining notification {}".format(status_id))
            except MastodonNotFoundError as e:
                self.logger.error("Clear remaining notification")
                self.logger.error("MastodonNotFoundError: {} on line {}".format(e, e.__traceback__.tb_lineno))

    def clear_mentions(self):
        for status_id in self.replies:
            try:
                self.client.notifications_dismiss(status_id)
                self.logger.info("Dismiss notification {}".format(status_id))
            except MastodonNotFoundError as e:
                self.logger.error("Clear mentions")
                self.logger.error("MastodonNotFoundError: {} on line {}".format(e, e.__traceback__.tb_lineno))

    def clear_sightings(self):
        for status_id in self.sightings:
            try:
                self.client.notifications_dismiss(status_id)
                self.logger.info("Dismiss notification {}".format(status_id))
            except MastodonNotFoundError as e:
                self.logger.error("Clear mentions")
                self.logger.error("MastodonNotFoundError: {} on line {}".format(e, e.__traceback__.tb_lineno))

if __name__ == '__main__':
    # # export PYTHONIOENCODING='utf8'
    logger = logging.getLogger("mispbot")
    logger.setLevel(logging.DEBUG)
    ch = logging.FileHandler(log_file, mode="a")
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    mastodon_client = mastodon_handler(mastodon_config, misp_config, logger)
    mastodon_client.fetch_mentions()
    #mastodon_client.print_mentions()
    mastodon_client.process_mentions()
    mastodon_client.reply()
    mastodon_client.clear_mentions()
    mastodon_client.clear_sightings()
    mastodon_client.clear_remaining_notifications()
    mastodon_client.close()
