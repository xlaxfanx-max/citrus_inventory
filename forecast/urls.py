from django.urls import path

from . import views

app_name = 'forecast'

urlpatterns = [
    path('accuracy/', views.accuracy, name='accuracy'),
    path('report/<str:code>/', views.report_preview, name='report_preview'),
]
