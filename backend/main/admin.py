from django.contrib import admin
from singlemodeladmin import SingleModelAdmin

from main.models import Preference


@admin.register(Preference)
class PreferenceAdmin(SingleModelAdmin):
    pass
