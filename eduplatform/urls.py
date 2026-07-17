"""
URL configuration for eduplatform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import HttpResponse

def loaderio_view(request):
    return HttpResponse("loaderio-cddfd63c006292899295e61a7593259e")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('loaderio-cddfd63c006292899295e61a7593259e/', loaderio_view),
    path('loaderio-cddfd63c006292899295e61a7593259e.txt', loaderio_view),
    path('', include('game_core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
