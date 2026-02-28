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

    path('helper_profile/settings/', views.helper_profile_settings, name='helper_profile_settings'),

    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),


    path('chat/<int:request_id>/', views.helper_chat_view, name='helper_chat'),
    path('api/chat/get/<int:request_id>/', views.helper_get_chat_messages, name='helper_get_chat_messages'),
    path('api/chat/send/<int:request_id>/', views.helper_send_chat_message, name='helper_send_chat_message'),

     # --- PASSWORD RESET URLs ---
    # path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    # path('reset-password/<uuid:token>/', views.reset_password_view, name='reset_password'),
]