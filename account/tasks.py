from celery import shared_task
from django.core.management import call_command

@shared_task
def mark_offline_task():
    call_command("mark_offline")