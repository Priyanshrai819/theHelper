from django.contrib import admin
from django.urls import path
from . import views

app_name = 'helpersapp'  # Add this line

urlpatterns = [
    path("dashboard/" ,views.dashboard,name='dashboard'),
    path("options/" ,views.options,name='options'),
    path("how-it-works/" ,views.how_it_works_view,name='how_it_works'),
    path("services/" ,views.services_view,name='services'),
    path("about/" ,views.about_view,name='about'),
    path("contact/" ,views.contact_view,name='contact'),

    path("request_help/" ,views.request_help,name='request_help'),
    path("logout/" ,views.logout,name='logout'),
    path("auth/", views.auth, name='auth'),
    path('request/<int:request_id>/', views.request_details, name='request_details'),
    path('request/cancel/<int:request_id>/', views.cancel_request, name='cancel_request'),
    path('verify-otp/<int:request_id>/', views.verify_otp_view, name='verify_otp'),

    path('contact-helper/<int:request_id>/', views.contact_helper, name='contact_helper'),
    path('api/chat/get/<int:request_id>/', views.get_chat_messages, name='get_chat_messages'),
    path('api/chat/send/<int:request_id>/', views.send_chat_message, name='send_chat_message'),

    

    path('profile/settings/', views.profile_settings, name='profile_settings'),

     # Fetches unread notifications for the dropdown
    path('api/notifications/', views.get_notifications_api, name='get_notifications_api'),
    
    # Marks a specific notification as read when clicked
    path('api/notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # Marks all notifications as read at once
    path('api/notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    # path(''),

    # --- PAYMENT URLs ---
    path('payment/options/<int:request_id>/', views.payment_options_view, name='payment_options'),
    path('payment/initiate/<int:request_id>/', views.initiate_payment, name='initiate_payment'),
    path('payment/success/<int:request_id>/', views.payment_success, name='payment_success'),
    path('payment/after-completion/<int:request_id>/', views.pay_after_completion, name='pay_after_completion'),

     # --- PASSWORD RESET URLs ---
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<uuid:token>/', views.reset_password_view, name='reset_password'),
]