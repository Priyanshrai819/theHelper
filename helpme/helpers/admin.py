from django.contrib import admin
from .models import Helper, JobApplication
# Register your models here.
@admin.register(Helper)
class HelperAdmin(admin.ModelAdmin):
    list_display = ('id', 'fname', 'lname', 'email', 'city', 'state')
    search_fields = ('fname', 'lname', 'email')
    list_filter = ('city', 'state')
    ordering = ('-id',)
@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'helper', 'service_request', 'status', 'applied_at')
    search_fields = ('helper__fname', 'service_request__title')
    list_filter = ('status',)
    ordering = ('-applied_at',)
