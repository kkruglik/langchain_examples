"""Slack Bolt app and event handlers for the one-shot pipeline bot."""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from slack_bolt import App

from langchain_examples.config import settings
from langchain_examples.logging import get_logger
from langchain_examples.slack.artifacts import save_artifacts
from langchain_examples.slack.pipeline import run_pipeline_once

logger = get_logger(__name__)

slack_app = App(token=settings.slack_bot_token)
_executor = ThreadPoolExecutor(max_workers=settings.max_workers)


def _run_and_reply(text: str, channel: str, slack_thread_ts: str) -> None:
    try:
        result = run_pipeline_once(text)
        file_paths = save_artifacts(result)

        if not file_paths:
            slack_app.client.chat_postMessage(channel=channel, thread_ts=slack_thread_ts, text="No artifacts produced.")
            return

        slack_app.client.files_upload_v2(
            channel=channel,
            thread_ts=slack_thread_ts,
            initial_comment="Your script is ready!",
            file_uploads=[{"file": path, "filename": Path(path).name} for path in file_paths],
        )
    except Exception as exc:
        logger.exception("Pipeline error for slack_thread_ts %s", slack_thread_ts)
        slack_app.client.chat_postMessage(channel=channel, thread_ts=slack_thread_ts, text=f"Error: {exc}")


@slack_app.event("app_mention")
def handle_mention(event):
    text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
    channel = event["channel"]
    slack_thread_ts = event.get("thread_ts") or event["ts"]
    logger.info(
        "app_mention event received: channel=%s user=%s text=%s",
        event.get("channel"),
        event.get("user"),
        text[:100],
    )
    if text.strip().lower() == "ping":
        slack_app.client.chat_postMessage(channel=channel, thread_ts=slack_thread_ts, text="pong")
        return
    slack_app.client.chat_postMessage(
        channel=channel,
        thread_ts=slack_thread_ts,
        text="Got it! Working on your script, I'll reply here when it's ready...",
    )
    _executor.submit(_run_and_reply, text, channel, slack_thread_ts)


@slack_app.event("message")
def handle_dm(event):
    logger.info(
        "message event: channel_type=%s subtype=%s bot_id=%s",
        event.get("channel_type"),
        event.get("subtype"),
        event.get("bot_id"),
    )
    # Only handle direct messages, ignore bot messages and thread replies
    if event.get("bot_id") or event.get("subtype") or event.get("thread_ts"):
        return
    if event.get("channel_type") == "im":
        text = event.get("text", "")
        channel = event["channel"]
        slack_thread_ts = event.get("thread_ts") or event["ts"]
        if text.strip().lower() == "ping":
            slack_app.client.chat_postMessage(channel=channel, thread_ts=slack_thread_ts, text="pong")
            return
        slack_app.client.chat_postMessage(
            channel=channel,
            thread_ts=slack_thread_ts,
            text="Got it! Working on your script, I'll reply here when it's ready...",
        )
        _executor.submit(_run_and_reply, text, channel, slack_thread_ts)
