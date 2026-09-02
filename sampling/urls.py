from django.urls import path

from . import views

app_name = 'sampling'

urlpatterns = [
    path('', views.picker, name='picker'),
    path('lot/<int:lot_id>/', views.capture, name='capture'),
    path('sample/<int:pk>/', views.sample_status, name='sample_status'),
    path('photo/<int:pk>/', views.photo, name='photo'),
]
