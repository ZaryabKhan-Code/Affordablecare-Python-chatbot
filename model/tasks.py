from model.celery import *
import subprocess
import uuid
from view.bot import *


@celery.task
def process_pdf_task(benefits_url, query, chat_log, user_id, now, workflow):
    try:
        print("Coming Here")
        result = process_pdf(benefits_url, query, chat_log)
        insert_chat(
            now,
            user_id,
            workflow,
            "System",
            "Current state changed to neutral",
        )
        return result
    except Exception as e:
        print(e)
        update_state(user_id, "Neutral")
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
        return "Oops, it seems there's been a hiccup. Please try again!"
