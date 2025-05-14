from django.contrib import admin
from .models import User, Client, Worker, VerificationToken

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_client', 'is_worker', 'is_superuser', 'is_verified')
    list_filter = ('is_superuser', 'is_verified')
    search_fields = ('username', 'email', 'phone_number')

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'profile_pic')
    search_fields = ('user__username', 'user__email')

@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'profile_pic')
    search_fields = ('user__username', 'user__email')

@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'purpose', 'created_at', 'expires_at', 'is_used')
    search_fields = ('user__username', 'code')
    list_filter = ('purpose', 'is_used', 'expires_at')