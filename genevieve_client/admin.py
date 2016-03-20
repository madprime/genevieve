from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import GennotesEditor, GenomeReport

User = get_user_model()

admin.site.register(GennotesEditor)
admin.site.register(GenomeReport)
