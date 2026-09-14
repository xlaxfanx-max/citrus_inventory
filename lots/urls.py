from django.urls import path

from . import views

app_name = 'lots'

urlpatterns = [
    path('', views.board, name='board'),
    path('lot/<int:pk>/', views.lot_detail, name='lot_detail'),
    path('lot/<int:pk>/packout/<int:packout_pk>/quality/', views.packout_quality, name='packout_quality'),
    path('imports/', views.imports, name='imports'),
    path('imports/<int:pk>/', views.import_detail, name='import_detail'),
    path('imports/template/<str:kind>.csv', views.import_template, name='import_template'),
    path('settings/', views.model_settings, name='settings'),
]
