"""
URL configuration for helpme project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
# In your_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from helpersapp.views import options # 1. Import the new view

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 2. Point the root URL to the options view
    path('', options, name='options'), 

    # 3. Handle app-specific URLs under prefixes
    path('user/', include('helpersapp.urls')),
    path('helper/', include('helpers.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
