from django.urls import path

from . import views

app_name = 'forecast'

urlpatterns = [
    path('readiness/', views.readiness, name='readiness'),
    path('accuracy/', views.accuracy, name='accuracy'),
    path('report/<str:code>/', views.report_preview, name='report_preview'),
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/lock/', views.plan_lock, name='plan_lock'),
    path('plans/<int:pk>/decide/<int:rec_pk>/', views.plan_decide, name='plan_decide'),
    path('plans/publish/<str:code>/', views.plan_publish, name='plan_publish'),
]
