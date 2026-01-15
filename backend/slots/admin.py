from django.contrib import admin
from .models import Slot


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('faculty', 'start_time', 'end_time', 'is_available', 'created_at')
    list_filter = ('is_available', 'faculty', 'start_time')
    search_fields = ('faculty__name', 'faculty__email')
    ordering = ('-start_time',)
    
    readonly_fields = ('created_at', 'updated_at')
