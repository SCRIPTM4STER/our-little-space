"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path

from api.views import frontend_index


from pathlib import Path
from django.conf import settings
from django.http import JsonResponse

def media_diagnostic(request):
    p = (
        Path(settings.MEDIA_ROOT)
        / "profile-avatars"
        / "Midnight_Music_Dreams_Avatar.png"
    )

    return JsonResponse({
        "media_root": str(settings.MEDIA_ROOT),
        "file_exists": p.exists(),
        "file_path": str(p),
    })



urlpatterns = [
    path('admin/', admin.site.urls),
    path("debug-media-check/", media_diagnostic),
    path('api/', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all: serve the React SPA for any route not handled by Django API/admin
urlpatterns += [
    re_path(r'^(?!api|admin|static|media).*$', frontend_index),
]


