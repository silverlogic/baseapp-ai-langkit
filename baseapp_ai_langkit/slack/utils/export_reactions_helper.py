import csv
from datetime import datetime

from django.http import HttpResponse


def get_message_content(message_slack_event):
    if message_slack_event and message_slack_event.data:
        event_data = message_slack_event.data
        if "text" in event_data:
            return event_data["text"]
        elif "message" in event_data and "text" in event_data["message"]:
            return event_data["message"]["text"]
        elif "event" in event_data and "text" in event_data["event"]:
            return event_data["event"]["text"]
    return "No content available"


def get_message_url(slack_message):
    if not slack_message.output_slack_event:
        return "URL not available"

    event_data = slack_message.output_slack_event.data

    channel_id = None
    timestamp = None
    thread_ts = None

    if "channel" in event_data:
        channel_id = event_data["channel"]
    elif "event" in event_data and "channel" in event_data["event"]:
        channel_id = event_data["event"]["channel"]

    if "ts" in event_data:
        timestamp = event_data["ts"]
    elif "event" in event_data and "ts" in event_data["event"]:
        timestamp = event_data["event"]["ts"]
    elif "message" in event_data and "ts" in event_data["message"]:
        timestamp = event_data["message"]["ts"]

    if "message" in event_data and "thread_ts" in event_data["message"]:
        thread_ts = event_data["message"]["thread_ts"]
    elif "event" in event_data and "thread_ts" in event_data["event"]:
        thread_ts = event_data["event"]["thread_ts"]

    if channel_id and timestamp:
        ts_without_dot = timestamp.replace(".", "")
        base_url = f"https://silverlogic.slack.com/archives/{channel_id}/p{ts_without_dot}"

        if thread_ts:
            return f"{base_url}?thread_ts={thread_ts}&cid={channel_id}"
        else:
            return base_url

    return "URL not available"


def generate_reaction_export_csv(queryset, reaction_types, reaction_name) -> HttpResponse:
    reactions = queryset.filter(reaction__in=reaction_types)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"avi_chat_messages_{reaction_name.replace(' ', '_')}_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Reactions", "User Email", "User message", "Output message", "URL"])
    for reaction in reactions:
        message = reaction.slack_chat_message
        user_message = message.user_message_slack_event
        output_message = message.output_slack_event
        user_message_content = get_message_content(user_message)
        output_message_content = get_message_content(output_message)

        if message.output_response_output_data.get("channel", "").startswith("D"):
            url = "Direct message"
        else:
            url = get_message_url(message)

        writer.writerow(
            [
                message.id,
                reactions.count(),
                reaction.user.email,
                user_message_content,
                output_message_content,
                url,
            ]
        )

    return response
