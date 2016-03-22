"""
Celery set up, as recommended by celery
http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html
"""
# absolute_import prevents conflicts between project celery.py file
# and the celery package.
from __future__ import absolute_import

import os

from celery import Celery

from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'genevieve_client.settings')

broker_url = os.getenv('CELERY_BROKER_URL', 'amqp://')
app = Celery('genevieve_client', broker=broker_url)

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
