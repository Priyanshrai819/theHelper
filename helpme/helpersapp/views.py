import json
from django.shortcuts import render , HttpResponse ,redirect ,get_object_or_404
from datetime import datetime
from django.contrib import messages
from django.http import JsonResponse
import requests
from django.contrib.auth.hashers import make_password, check_password
from .models import User, ServiceRequest, RequestPhoto ,Payment, ChatMessage,Notification
from helpers.models import Helper 
from django.conf import settings
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

import re

# --- NEW: Import signals and Django's default User model ---
from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User as AuthUser

from django.core.mail import send_mail

from django.urls import reverse

from .models import User, PasswordResetToken

from django.template.loader import render_to_string
from django.utils.html import strip_tags



def forgot_password_view(request):
    """
    Handles the request to send a password reset link to the user's email.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # 1. Fetch the user or helper object (so we can get their name for the email)
        user = User.objects.filter(email=email).first()
        helper = Helper.objects.filter(email=email).first()
        
        if user or helper:
            # 2. Delete any existing unused tokens for this email to prevent spam
            PasswordResetToken.objects.filter(email=email).delete()
            
            # 3. Create a new secure, random token
            token_obj = PasswordResetToken.objects.create(email=email)
            
            # 4. Build the full URL for the reset link (e.g., http://127.0.0.1:8000/reset-password/<token>/)
            reset_url = request.build_absolute_uri(
                reverse('helpersapp:reset_password', args=[token_obj.token])
            )
            
            # Get the user's first name for the email greeting
            user_name = user.fname if user else helper.fname
            
            # 5. Compile the HTML template with dynamic data
            html_message = render_to_string('email/email_forget_password.html', {
                'user_name': user_name.upper(), # Uppercase to match your design
                'reset_url': reset_url
            })
            
            # Create a plain text fallback for email clients that don't support HTML
            plain_message = strip_tags(html_message)
            
            # 6. Send the Email
            try:
                send_mail(
                    subject='Password Reset Request - theHelpers',
                    message=plain_message, # Fallback text
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message, # THIS RENDERS THE BEAUTIFUL HTML DESIGN
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Error sending email: {e}")
                
        # Always show a success message even if the email wasn't found (security best practice)
        messages.success(request, "If an account with that email exists, we have sent a password reset link to your inbox.")
        return redirect('helpersapp:forgot_password')
        
    return render(request, 'forgot_password.html')

def reset_password_view(request, token):
    """
    Handles the actual password reset using the token from the email link.
    """
    # 1. Gracefully handle invalid or used tokens to prevent 404 crashes
    try:
        token_obj = PasswordResetToken.objects.get(token=token)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "This password reset link is invalid or has already been used.")
        return redirect('helpersapp:forgot_password')
    
    # 2. Check if the token is older than 1 hour
    if not token_obj.is_valid():
        messages.error(request, "This password reset link has expired. Please request a new one.")
        return redirect('helpersapp:forgot_password')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # 3. Ensure passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'reset_password.html', {'token': token})
            
        # 4. Hash the new password securely
        hashed_password = make_password(password)
        
        # 5. Apply the new password to the correct account type (User or Helper)
        user = User.objects.filter(email=token_obj.email).first()
        if user:
            user.password = hashed_password
            user.save()
            
        helper = Helper.objects.filter(email=token_obj.email).first()
        if helper:
            helper.password = hashed_password
            helper.save()
            
        # 6. Delete the token so it cannot be reused
        token_obj.delete()
        
        messages.success(request, "Your password has been reset successfully! You can now log in.")
        
        # Redirect to the correct login page based on account type
        if helper:
            return redirect('helpers:helper_auth')
        return redirect('helpersapp:auth')
        
    # Render the reset password HTML template you selected
    return render(request, 'reset_password.html', {'token': token})






def get_notifications_api(request):
    """
    API to fetch unread notifications for the logged-in user or helper.
    """
    user_id = request.session.get('user_id')
    helper_id = request.session.get('helper_id')
    
    notifications = []
    if user_id:
        notifications = Notification.objects.filter(user_id=user_id, is_read=False)
    elif helper_id:
        notifications = Notification.objects.filter(helper_id=helper_id, is_read=False)
        
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'link': n.link or '#',
        'created_at': n.created_at.strftime('%b %d, %H:%M')
    } for n in notifications]
    
    return JsonResponse({'notifications': data, 'count': len(data)})

def mark_notification_read(request, notification_id):
    """
    Marks a specific notification as read.
    """
    # Try finding in User notifications first, then Helper
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

def mark_all_notifications_read(request):
    """
    Marks ALL unread notifications as read for the current user/helper.
    """
    user_id = request.session.get('user_id')
    helper_id = request.session.get('helper_id')

    if user_id:
        Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
    elif helper_id:
        Notification.objects.filter(helper_id=helper_id, is_read=False).update(is_read=True)
        
    return JsonResponse({'status': 'success'})










# --- CORRECTED: Signal Receiver Function ---
@receiver(user_logged_in)
def user_logged_in_receiver(request, user, **kwargs):
    """
    Listens for a successful login from allauth (including Google).
    This function acts as a bridge: it finds or creates our custom User
    and then sets our custom 'user_id' in the session to ensure the user
    is logged into our custom authentication system.
    """
    # Find our custom User by email. If it doesn't exist, create it.
    custom_user, created = User.objects.get_or_create(
        email=user.email,
        defaults={
            'fname': user.first_name or user.username,
            'lname': user.last_name or '',
            # Create a dummy, unusable password for social-only users
            'password': make_password(None) 
        }
    )
    
    # This is the crucial step: Set the custom session variable that
    # the dashboard and other views are checking for. This fixes the redirect loop.
    request.session['user_id'] = custom_user.id





def profile_settings(request):
    """
    Allows the logged-in user (Requester) to update their profile details.
    """
    # 1. Security Check: Ensure user is logged in
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')
    
    # 2. Get the User Object
    user = get_object_or_404(User, id=request.session['user_id'])
    
    # 3. Handle Form Submission (POST)
    if request.method == 'POST':
        try:
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            
            # Update fields if data is provided
            if fname: 
                user.fname = fname
            if lname: 
                user.lname = lname
            
            # Handle Profile Image Upload
            # request.FILES handles file uploads
            if 'profile_image' in request.FILES:
                user.profile_image = request.FILES['profile_image']
            
            # Save changes to the database
            user.save()
            
            messages.success(request, "Profile updated successfully.")
            return redirect('helpersapp:profile_settings')
            
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")

    # 4. Render the page (GET request)
    return render(request, 'profile_settings.html', {'user': user})




def verify_otp_view(request, request_id):
    """
    Verifies the OTP submitted by the helper.
    """
    if request.method == 'POST':
        service_request = get_object_or_404(ServiceRequest, id=request_id)
        submitted_otp = request.POST.get('otp')

        if submitted_otp == service_request.otp_code:
            # OTP is correct, mark the job as completed
            service_request.status = 'Completed'
            service_request.otp_code = None # Clear the OTP
            service_request.save()
            
            messages.success(request, "Job successfully marked as completed!")
            Notification.objects.create(
            user=service_request.user, # Notify the Requester
            title="Job Completed",
            message=f"Your request for {service_request.subcategory} has been marked as completed by the helper.",
            link=f"/user/request/{service_request.id}/" # Link to details
            )
            return redirect('helpers:helper_dashboard')
        else:
            # OTP is incorrect
            messages.error(request, "Invalid OTP. Please try again.")
            return redirect('helpers:complete_request', request_id=request_id)
            
    return redirect('helpers:helper_dashboard')




def auth(request):
    """
    Handles both user registration and login directly in the view
    without using a forms.py file.
    """
    login_errors = {}
    register_errors = {}

    if request.method == 'POST':
        # Differentiate between login and registration based on the submit button's name
        if 'login_submit' in request.POST:
            email = request.POST.get('email')
            password = request.POST.get('password')

            # --- Login Validation ---
            if not email:
                login_errors['email'] = 'This field is required.'
            if not password:
                login_errors['password'] = 'This field is required.'

            if not login_errors:
                try:
                    user = User.objects.get(email=email)
                    if check_password(password, user.password):
                        request.session['user_id'] = user.id
                        
                        # --- CORRECT PLACE: Only runs once on successful login ---
                        messages.success(request, f"Welcome back, {user.fname}!") 
                        
                        return redirect('helpersapp:dashboard')
                    else:
                        login_errors['general'] = 'Invalid email or password.'
                except User.DoesNotExist:
                    login_errors['general'] = 'Invalid email or password.'

        elif 'register_submit' in request.POST:
            fname = request.POST.get('firstName')
            lname = request.POST.get('lastName')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirmPassword')
            profile_image = request.FILES.get('profile_image')

            # --- Registration Validation ---
            
            # Strict Name Validation (Letters Only)
            if not fname: 
                register_errors['firstName'] = 'First name is required.'
            elif not re.match(r'^[a-zA-Z]+$', fname):
                register_errors['firstName'] = 'First name can only contain letters (A-Z).'

            if not lname: 
                register_errors['lastName'] = 'Last name is required.'
            elif not re.match(r'^[a-zA-Z]+$', lname):
                register_errors['lastName'] = 'Last name can only contain letters (A-Z).'

            # Email Validation
            if not email:
                register_errors['email'] = 'Email is required.'
            else:
                try:
                    validate_email(email)
                    if User.objects.filter(email=email).exists():
                        register_errors['email'] = 'An account with this email already exists.'
                except ValidationError:
                    register_errors['email'] = 'Enter a valid email address.'
            
            if not password: register_errors['password'] = 'Password is required.'
            if password != confirm_password:
                register_errors['confirmPassword'] = 'Passwords do not match.'

            if not register_errors:
                hashed_password = make_password(password)
                user = User.objects.create(
                    fname=fname,
                    lname=lname,
                    email=email,
                    password=hashed_password,
                    profile_image=profile_image
                )
                request.session['user_id'] = user.id
                messages.success(request, f'Welcome, {user.fname}! Your account has been created.')
                return redirect('helpersapp:dashboard')

    # For a GET request or if there are errors, render the page
    return render(request, 'auth.html', {
        'login_errors': login_errors,
        'register_errors': register_errors,
        'old_input': request.POST if request.method == 'POST' else {}
    })

def dashboard(request):
    """
    A simple dashboard view. Protect this view so only logged-in users can see it.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')

    try:
        user = User.objects.get(id=request.session['user_id'])
        
        # Get all requests for the user
        all_requests = ServiceRequest.objects.filter(user=user)

        # Calculate the counts for each status
        active_requests_count = all_requests.filter(status='Active').count()
        pending_requests_count = all_requests.filter(status='Pending').count()
        completed_requests_count = all_requests.filter(status='Completed').count()
        
        # Calculate total spent from completed requests
        total_spent = 0
        completed_requests = all_requests.filter(status='Completed')
        for req in completed_requests:
            if req.budget:
                total_spent += req.budget

        context = {
            'user': user,
            'requests': all_requests,
            'active_requests_count': active_requests_count,
            'pending_requests_count': pending_requests_count,
            'completed_requests_count': completed_requests_count,
            'total_spent': total_spent
        }
        
        return render(request, 'dashboard.html', context)
    except User.DoesNotExist:
        del request.session['user_id']
        return redirect('helpersapp:auth')

def logout(request):
    """
    Logs the user out by clearing the entire session.
    This ensures all messages (toasts) and session data are removed.
    """
    request.session.flush()
    return redirect('helpersapp:auth')



def request_help(request):
    """
    Handles the multi-step form for creating a new ServiceRequest.
    """
    # 1. Check if user is logged in
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')

    # 2. Fetch the user object to display name/profile in header
    try:
        user = User.objects.get(id=request.session['user_id'])
    except User.DoesNotExist:
        del request.session['user_id']
        return redirect('helpersapp:auth')

    if request.method == 'POST':
        try:
            # --- Get Data from Form ---
            service_category = request.POST.get('service_category')
            subcategory = request.POST.get('subcategory')
            task_description = request.POST.get('task_description')
            address = request.POST.get('address')
            preferred_date = request.POST.get('preferred_date')
            preferred_time = request.POST.get('preferred_time')
            budget = request.POST.get('budget')
            payment_type = request.POST.get('payment_type')
            special_requirements = request.POST.get('special_requirements')

            # --- Create the ServiceRequest instance ---
            new_request = ServiceRequest.objects.create(
                user=user,
                service_category=service_category,
                subcategory=subcategory,
                task_description=task_description,
                address=address,
                preferred_date=preferred_date,
                preferred_time=preferred_time,
                is_flexible='is_flexible' in request.POST,
                is_urgent='is_urgent' in request.POST,
                has_parking='has_parking' in request.POST,
                payment_type=payment_type,
                budget=budget,
                special_requirements=special_requirements,
                helper_brings_tools='helper_brings_tools' in request.POST,
                background_check_required='background_check_required' in request.POST,
                insurance_needed='insurance_needed' in request.POST,
                experience_required='experience_required' in request.POST,
                status='Pending'
            )

            # --- Handle multiple photo uploads ---
            uploaded_images = request.FILES.getlist('photos')
            for image in uploaded_images:
                RequestPhoto.objects.create(
                    service_request=new_request,
                    image=image
                )
            
            messages.success(request, 'Your help request has been submitted successfully!')
            
            # Redirect to the payment options page
            return redirect('helpersapp:payment_options', request_id=new_request.id)

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            # Ensure 'user' is passed back even on error so header doesn't break
            return render(request, 'request_help.html', {'user': user})

    # 3. Pass the user object to the template for GET requests
    return render(request, 'request_help.html', {'user': user})




def payment_options_view(request, request_id):
    """
    Displays the payment options page after a request is created.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')
    
    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    
    context = {
        'request': service_request,
        'razorpay_api_key': settings.RAZORPAY_API_KEY # Pass key for Razorpay
    }
    return render(request, 'payment_options.html', context)


def pay_after_completion(request, request_id):
    """
    Handles the 'Pay After Completion' choice.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')
        
    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    messages.success(request, f"Your request for '{service_request.get_service_category_display()}' has been posted! You can pay after the job is completed.")
    Notification.objects.create(
        user=service_request.user, # Notify the Requester
        title="Request Posted",
        message=f"Your request for {service_request.subcategory} has been successfully posted. You can pay after completion.",
        link=f"/user/request/{service_request.id}/" # Link to details
    )
    return redirect('helpersapp:dashboard')









def request_status(request):
    user = None
    user_id = request.session.get('user_id')

    requests = []
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            requests = ServiceRequest.objects.filter(requester=user)
        except User.DoesNotExist:
            user = None
    return render(request,'dashboard.html', {'user': user, 'requests': requests})



def request_details(request, request_id):
    """
    Displays the full details of a single service request.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')
    
    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    return render(request, 'request_details.html', {'request': service_request})


def cancel_request(request, request_id):
    """
    Marks a service request as 'Cancelled'.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')

    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    
    # You can only cancel pending or active requests
    if service_request.status in ['Pending', 'Active']:
        service_request.status = 'Cancelled'
        service_request.save()
        messages.success(request, f"Request '{service_request.get_service_category_display()}' has been cancelled.")
        Notification.objects.create(
        user=service_request.user, # Notify the Requester
        title="Request Cancelled",
        message=f"Your request for {service_request.subcategory} has been cancelled.",
        link=f"/user/request/{service_request.id}/" # Link to details
    )


    else:
        messages.error(request, "This request cannot be cancelled.")
        
    return redirect('helpersapp:dashboard')



def initiate_payment(request, request_id):
    """
    Creates a Razorpay order and includes user details in the 'notes'.
    """
    if request.method == "POST":
        try:
            # Load data from the JSON request body sent by the frontend
            data = json.loads(request.body)
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            email = data.get('email')
            phone = data.get('phone')

            service_request = get_object_or_404(ServiceRequest, id=request_id)
            amount = int(service_request.budget * 100)  # Amount in paise

            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            
            # Add the user details to the 'notes' section of the order
            order_data = {
                "amount": amount,
                "currency": "INR",
                "receipt": f"request_rcpt_{service_request.id}",
                "notes": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone,
                    "request_id": request_id 
                }
            }
            order = client.order.create(data=order_data)

            return JsonResponse({
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'api_key': settings.RAZORPAY_API_KEY
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)




@csrf_exempt
def payment_success(request, request_id):
    """
    Verifies the Razorpay signature after a successful online payment 
    and saves the payment details.
    """
    if request.method == "POST":
        service_request = get_object_or_404(ServiceRequest, id=request_id)
        client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
        
        try:
            # Verify the signature
            client.utility.verify_payment_signature({
                'razorpay_order_id': request.POST.get('razorpay_order_id'),
                'razorpay_payment_id': request.POST.get('razorpay_payment_id'),
                'razorpay_signature': request.POST.get('razorpay_signature')
            })

            # Create Payment record
            Payment.objects.create(
                service_request=service_request,
                razorpay_order_id=request.POST.get('razorpay_order_id'),
                razorpay_payment_id=request.POST.get('razorpay_payment_id'),
                razorpay_signature=request.POST.get('razorpay_signature'),
                amount=service_request.budget
            )

            # Update request status
            service_request.payment_status = 'Paid'
            service_request.save()
            
            messages.success(request, "Payment successful!")
            Notification.objects.create(
            user=service_request.user, # Notify the Requester
            title="Payment Successful",
            message=f"Your payment for {service_request.subcategory} has been successfully processed.",
            link=f"/user/request/{service_request.id}/" # Link to details
            )
            return JsonResponse({'status': 'success'})
        

        except Exception as e:
            messages.error(request, f"Payment verification failed: {e}")
            return JsonResponse({'status': 'failure'}, status=400)

def mark_as_paid_cash(request, request_id):
    """
    Marks a service request's payment status as 'Paid' for offline cash transactions.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')

    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    
    # Check if the request is completed and payment is pending
    if service_request.status == 'Completed' and service_request.payment_status == 'Pending':
        service_request.payment_status = 'Paid'
        service_request.save()
        messages.success(request, "Request has been marked as paid with cash.")
    else:
        messages.error(request, "This request cannot be marked as paid.")
        
    return redirect('helpersapp:dashboard')










def contact_helper(request, request_id):
    """
    Displays the chat page for a specific service request.
    """
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth')
    
    service_request = get_object_or_404(ServiceRequest, id=request_id, user_id=request.session['user_id'])
    user = get_object_or_404(User, id=request.session['user_id'])
    
    if not service_request.accepted_helper:
        messages.error(request, "No helper has been assigned to this request yet.")
        return redirect('helpersapp:dashboard')

    return render(request, 'contact_helper.html', {
        'request': service_request,
        'helper': service_request.accepted_helper,
        'user': user
    })

def get_chat_messages(request, request_id):
    """
    API endpoint to fetch chat messages for the User.
    """
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    messages = ChatMessage.objects.filter(service_request_id=request_id).order_by('timestamp')
    data = []
    for msg in messages:
        data.append({
            'id': msg.id,
            'text': msg.message,
            'is_me': bool(msg.sender_user), # True if sent by User, False if by Helper
            'sender_name': msg.sender_user.fname if msg.sender_user else msg.sender_helper.fname,
            'time': msg.timestamp.strftime('%I:%M %p')
        })
    return JsonResponse({'messages': data})

def send_chat_message(request, request_id):
    """
    API endpoint to send a new chat message from the User.
    """
    if request.method == 'POST' and 'user_id' in request.session:
        message_text = request.POST.get('message')
        if message_text:
            service_request = get_object_or_404(ServiceRequest, id=request_id)
            user = get_object_or_404(User, id=request.session['user_id'])
            
            ChatMessage.objects.create(
                service_request=service_request,
                sender_user=user,
                message=message_text
            )
            # Create notification for the helper
            Notification.objects.create(
                helper=service_request.accepted_helper,
                title="New Message",
                message=f"{user.fname} sent you a message regarding the {service_request.get_service_category_display()} job.",
                link=f"/helper/chat/{service_request.id}/"
            )
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)








def how_it_works_view(request):
    return render(request, 'how_it_works.html')

def services_view(request):
    return render(request, 'services.html')

def about_view(request):
    return render(request, 'about.html')

def contact_view(request):
    if request.method == 'POST':
        # In a real app, you would send an email here using send_mail()
        messages.success(request, "Thank you for reaching out! We will get back to you within 24 hours.")
        return redirect('helpersapp:contact')
    return render(request, 'contact.html')





def options(request):
    return render(request, 'options.html')
