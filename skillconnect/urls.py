from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib import admin
from rest_framework import permissions
from django.views.generic import RedirectView

schema_view = get_schema_view(
    openapi.Info(
        title="SkillConnect API",
        default_version='v1',
        description="API for SkillConnect platform",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', RedirectView.as_view(url='/swagger/', permanent=False), name='index'),
    path('admin/', admin.site.urls),
    path('users/', include('apps.users.urls')),
    path('jobs/', include('apps.jobs.urls')),
    path('payments/', include('apps.payments.urls')),
    path('disputes/', include('apps.disputes.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('recommendations/', include('apps.recommendations.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
