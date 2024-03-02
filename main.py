import os
import re
import json

import pytz
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from keep_alive import keep_alive
from pymongo import MongoClient
from twikit import Client

connection_string = os.environ.get("connection_string")
storage_client = MongoClient(connection_string)

db = storage_client['chelsea_news']
collection = db["absolute_chelsea"]

TELEGRAM_BOT_TOKEN = os.environ.get("bot_token")
TELEGRAM_CHAT_ID = os.environ.get("chat_id")
TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"

TWITTER_EMAIL = os.environ.get("twitter_email")
TWITTER_PHONE_NUMBER = os.environ.get("twitter_phone_number")
TWITTER_PASSWORD = os.environ.get("twitter_password")
COOKIES_FILE = "cookies.json"

keep_alive()

try:
    with open(COOKIES_FILE, 'r') as file:
        cookies_data = json.load(file)
except FileNotFoundError:
    cookies_data = None

twitter_client = Client(language='en-US', cookies=cookies_data)

def login_and_save_cookies():
    twitter_client.login(
        auth_info_1=TWITTER_EMAIL,
        auth_info_2=TWITTER_PHONE_NUMBER,
        password=TWITTER_PASSWORD
    )
    with open(COOKIES_FILE, 'w') as file:
        json.dump(twitter_client.get_cookies(), file)


def get_tweets_info():
    twitter_screen_name = 'AbsoluteChelsea'
    
    try:
        twitter_user = twitter_client.get_user_by_screen_name(twitter_screen_name)
    except twikit.errors.TooManyRequests as e:
        print(f"Rate limit exceeded. Waiting for {e.retry_after} seconds.")
        time.sleep(e.retry_after)
        login_and_save_cookies()
        twitter_user = twitter_client.get_user_by_screen_name(twitter_screen_name)

    twitter_user_id = twitter_user.id  # 4504718963

    tweets = twitter_client.get_user_tweets(twitter_user_id, 'Tweets', count=10)
    print(len(tweets))

    tweets_info_list = []

    for tweet in tweets:
        tweet_text = tweet.text
        # Define a regular expression pattern for matching HTTPS links
        url_pattern = re.compile(r'https://\S+')

        # Remove matched URLs from tweet text
        modified_tweet_text = re.sub(url_pattern, '', tweet_text)

        # Extract matched URLs from the original tweet text
        url_matches = re.findall(url_pattern, tweet_text)

        # Use the first image URL if available
        image_url = url_matches[0] if url_matches else None

        tweets_info_list.append({"text": modified_tweet_text, "url": image_url})

    return tweets_info_list


# Function to send Twitter updates to Telegram
def send_tweets_to_telegram(tweet_items):
    for item in tweet_items:
        tweet_text = item.get("text")
        tweet_image_url = item.get("url", "")

        telegram_message = f"🚨 {tweet_text}\n\n" \
                           f"📲 @JustCFC"
        print(telegram_message)

        saved_texts = collection.find_one({"text": tweet_text})
        if saved_texts:
            continue

        if not tweet_image_url:
            response = requests.post(TELEGRAM_BASE_URL + "sendMessage",
                                     json={
                                         "chat_id": TELEGRAM_CHAT_ID,
                                         "text": telegram_message
                                     })
        else:
            response = requests.post(TELEGRAM_BASE_URL + "sendPhoto",
                                     json={
                                         "chat_id": TELEGRAM_CHAT_ID,
                                         "disable_web_page_preview": False,
                                         "parse_mode": "HTML",
                                         "caption": telegram_message,
                                         "photo": tweet_image_url
                                     })

        if response.status_code == 200:
            print("Message sent successfully.")

            collection.insert_one({"text": tweet_text})
        else:
            print(
                f"Message sending failed. Status code: {response.text}"
            )


def main():
    tweets_info = get_tweets_info()
    send_tweets_to_telegram(tweets_info)


nigerian_tz = pytz.timezone("Africa/Lagos")
scheduler = BlockingScheduler(timezone=nigerian_tz)
scheduler.add_job(main, "interval", minutes=30, coalesce=True)
scheduler.start()

# main()
