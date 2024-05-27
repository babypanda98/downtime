import asyncio
import aiohttp
import logging
import json
import os
import random
from bs4 import BeautifulSoup
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("website_monitor.log"),
        logging.StreamHandler()
    ]
)

# Load configuration from a JSON file or environment variables
CONFIG_FILE = 'config.json'
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
else:
    config = {
        "urls": os.getenv("URLS").split(","),
        "keyword": os.getenv("KEYWORD"),
        "check_interval": int(os.getenv("CHECK_INTERVAL", 60)),
        "notification": {
            "type": os.getenv("NOTIFICATION_TYPE", "slack"),
            "url": os.getenv("NOTIFICATION_URL")
        },
        "retries": int(os.getenv("RETRIES", 5)),
        "backoff_factor": int(os.getenv("BACKOFF_FACTOR", 2))
    }

urls = config["urls"]
keyword = config["keyword"]
check_interval = config["check_interval"]
notification_type = config["notification"]["type"]
notification_url = config["notification"]["url"]
retries = config["retries"]
backoff_factor = config["backoff_factor"]

async def fetch(session, url, keyword):
    for attempt in range(retries):
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                if keyword in soup.get_text():
                    logging.info(f"Keyword '{keyword}' found on {url}.")
                    return True, text
                else:
                    logging.info(f"Keyword '{keyword}' not found on {url}.")
                    return False, text
        except aiohttp.ClientError as e:
            logging.error(f"Error checking website {url}: {e}")
            await asyncio.sleep(backoff_factor * (2 ** attempt))
    return False, ""

async def send_notification(message):
    if notification_type == "slack":
        await send_slack_notification(message)
    # Add other notification types here (e.g., Teams, Email)

async def send_slack_notification(message):
    if notification_url:
        payload = {"text": message}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(notification_url, json=payload) as response:
                    response.raise_for_status()
                    logging.info("Notification sent successfully.")
            except aiohttp.ClientError as e:
                logging.error(f"Error sending notification: {e}")
    else:
        logging.error("Slack webhook URL not provided in the configuration.")

async def monitor_websites():
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = [fetch(session, url, keyword) for url in urls]
            results = await asyncio.gather(*tasks)

            for url, (keyword_found, content) in zip(urls, results):
                if not keyword_found:
                    snippet = content[:200]  # Get a snippet of the content for context
                    message = (f"Keyword '{keyword}' not found on {url}. "
                               f"Current content snippet: '{snippet}'")
                    await send_notification(message)

            # Randomize check interval within a range to avoid synchronous bursts
            randomized_interval = random.uniform(check_interval * 0.8, check_interval * 1.2)
            await asyncio.sleep(randomized_interval)

if __name__ == "__main__":
    try:
        asyncio.run(monitor_websites())
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user.")
