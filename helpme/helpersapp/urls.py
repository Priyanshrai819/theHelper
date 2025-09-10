from django.contrib import admin
from django.urls import path
from . import views

app_name = 'helpersapp'  # Add this line

urlpatterns = [
    path("dashboard/" ,views.dashboard,name='dashboard'),
    path("request_help/" ,views.request_help,name='request_help'),
    path("logout/" ,views.logout,name='logout'),
    path("auth/", views.auth, name='auth'),
    path('request/<int:request_id>/', views.request_details, name='request_details'),
    path('request/cancel/<int:request_id>/', views.cancel_request, name='cancel_request'),
    path('verify-otp/<int:request_id>/', views.verify_otp_view, name='verify_otp'),
    path('contact_helper/<int:request_id>/', views.contact_helper, name='contact_helper'),
    path('api/messages/<int:request_id>/', views.get_chat_messages, name='get_chat_messages'),
    path('api/send-message/<int:request_id>/', views.send_chat_message, name='send_chat_message'),


    # --- PAYMENT URLs ---
    path('payment/options/<int:request_id>/', views.payment_options_view, name='payment_options'),
    path('payment/initiate/<int:request_id>/', views.initiate_payment, name='initiate_payment'),
    path('payment/success/<int:request_id>/', views.payment_success, name='payment_success'),
    path('payment/after-completion/<int:request_id>/', views.pay_after_completion, name='pay_after_completion'),
]