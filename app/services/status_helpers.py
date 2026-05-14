from __future__ import annotations

from app.models import Message, Rsvp


def get_latest_message(messages: list[Message]) -> Message | None:
    if not messages:
        return None

    return max(messages, key=lambda message: message.id)


def get_latest_sent_message(messages: list[Message]) -> Message | None:
    sent_messages = [
        message
        for message in messages
        if message.status == "sent"
    ]

    if not sent_messages:
        return None

    return max(sent_messages, key=lambda message: message.id)


def get_latest_rsvp(rsvps: list[Rsvp]) -> Rsvp | None:
    if not rsvps:
        return None

    return max(rsvps, key=lambda rsvp: rsvp.id)