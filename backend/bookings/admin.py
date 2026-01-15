from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student', 'slot', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('student__name', 'student__email', 'slot__faculty__name')
    ordering = ('-created_at',)
    
    readonly_fields = ('created_at', 'updated_at', 'cancelled_at')
