"""Slack Bolt handlers for the one-shot pipeline bot."""
import re
import threading

from slack_bolt import App

from langchain_examples.logging import get_logger

logger = get_logger(__name__)


def register_handlers(app: App, run_pipeline_once, save_artifacts) -> None:
    """Register Slack event handlers on the App."""

    def _run_and_reply(text: str, channel: str, thread_ts: str) -> None:
        try:
            result = run_pipeline_once(text)
            file_paths = save_artifacts(result)

            if not file_paths:
                app.client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="No artifacts produced.")
                return

            for path in file_paths:
                with open(path, "rb") as f:
                    app.client.files_upload_v2(
                        channel=channel,
                        thread_ts=thread_ts,
                        file=f,
                        filename=path.split("/")[-1],
                    )
        except Exception as exc:
            logger.exception("Pipeline error for thread %s", thread_ts)
            app.client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f"Error: {exc}")

    def _handle(event) -> None:
        text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]

        app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Got it! Working on your script, I'll reply here when it's ready...",
        )

        threading.Thread(target=_run_and_reply, args=(text, channel, thread_ts), daemon=True).start()

    @app.event("app_mention")
    def handle_mention(event):
        logger.info("app_mention event received: channel=%s user=%s text=%s", event.get("channel"), event.get("user"), event.get("text", "")[:100])
        _handle(event)

    @app.event("message")
    def handle_dm(event):
        logger.info("message event: channel_type=%s subtype=%s bot_id=%s", event.get("channel_type"), event.get("subtype"), event.get("bot_id"))
        # Only handle direct messages, ignore bot messages and thread replies
        if event.get("bot_id") or event.get("subtype") or event.get("thread_ts"):
            return
        if event.get("channel_type") == "im":
            _handle(event)
