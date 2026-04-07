from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain_examples.config import settings
from langchain_examples.logging import get_logger, setup_logging
from langchain_examples.slack.bot import slack_app

logger = get_logger(__name__)


def main():
    setup_logging()
    logger.info("Starting Slack bot (Socket Mode)...")
    SocketModeHandler(slack_app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()
