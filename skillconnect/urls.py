from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="SkillConnect API",
        default_version='v1',
        description="API for SkillConnect platform",
    ),
    public=True,
)

urlpatterns = [
    path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('users/', include('apps.users.urls')),
    path('jobs/', include('apps.jobs.urls')),
    path('payments/', include('apps.payments.urls')),
    path('disputes/', include('apps.disputes.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('recommendations/', include('apps.recommendations.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)