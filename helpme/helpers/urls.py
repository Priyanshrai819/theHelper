from django.contrib import admin
from django.urls import path
from . import views

app_name = 'helpers'  # Add this line

urlpatterns = [
    path('auth/', views.helper_auth, name='helper_auth'),
    path('helper_dashboard/', views.helper_dashboard, name='helper_dashboard'),
    # path("request_help/" ,views.request_help,name='request_help'),
    path("logout/" ,views.logout,name='logout'),
    path('request/<int:request_id>/', views.request_details, name='request_details'),
    path('request/accept/<int:request_id>/', views.accept_request, name='accept_request'),
    path('request/complete/<int:request_id>/', views.mark_job_completed, name='complete_request'),
    # path('request/cancel/<int:request_id>/', views.cancel_request, name='cancel_request'),
]