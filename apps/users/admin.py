from django.contrib import admin
from .models import User, Client, Worker

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_client', 'is_worker', 'is_superuser')
    list_filter = ('is_superuser',)
    search_fields = ('username', 'email', 'phone_number')

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'profile_pic')
    search_fields = ('user__username', 'user__email')

@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'profile_pic')
    search_fields = ('user__username', 'user__email')