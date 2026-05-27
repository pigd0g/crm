from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('crm.urls')),
    path('api/v1/', include(('crm.api_urls', 'crm_api'), namespace='crm_api')),
]
