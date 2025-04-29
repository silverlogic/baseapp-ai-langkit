from urllib.parse import urlparse

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from baseapp_ai_langkit.rest_framework.router import baseapp_ai_langkit_router

__all__ = [
    "urlpatterns",
]

v1_urlpatterns = [
    path(r"langkit/", include(baseapp_ai_langkit_router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", include((v1_urlpatterns, "v1"), namespace="v1")),
]

media_url = urlparse(settings.MEDIA_URL)
urlpatterns += static(media_url.path, document_root=settings.MEDIA_ROOT)
