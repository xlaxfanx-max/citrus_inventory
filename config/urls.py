from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .health import healthz, readyz

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('readyz/', readyz, name='readyz'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('lots.urls')),
    path('capture/', include('sampling.urls')),
    path('', include('forecast.urls')),
]
