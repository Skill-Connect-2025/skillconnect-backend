from django.contrib import admin
from .models import User, Client, Worker, VerificationToken, Education, Skill, TargetJob

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
    list_display = ('user', 'location', 'profile_pic', 'nationality', 'gender', 'has_experience')
    search_fields = ('user__username', 'user__email')

@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'purpose', 'created_at', 'expires_at', 'is_used')
    search_fields = ('user__username', 'code')
    list_filter = ('purpose', 'is_used', 'expires_at')

@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('worker', 'institute_name', 'level_of_study', 'field_of_study', 'graduation_year')
    search_fields = ('worker__user__username', 'institute_name')

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('worker', 'name', 'level')
    search_fields = ('worker__user__username', 'name')

@admin.register(TargetJob)
class TargetJobAdmin(admin.ModelAdmin):
    list_display = ('worker', 'job_title', 'level', 'open_to_work')
    search_fields = ('worker__user__username', 'job_title')
