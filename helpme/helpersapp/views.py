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



# --- NEW: Import signals and Django's default User model ---
from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from django.contrib.auth.models import User as AuthUser








def get_notifications(request):
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
        'link': n.link,
        'created_at': n.created_at.strftime('%b %d, %H:%M')
    } for n in notifications]
    
    return JsonResponse({'notifications': data, 'count': len(data)})

def mark_notification_read(request, notification_id):
    """
    Marks a specific notification as read.
    """
    notification = get_object_or_404(Notification, id=notification_id)
    notification.is_read = True
    notification.save()
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
            if not fname: register_errors['firstName'] = 'First name is required.'
            if not lname: register_errors['lastName'] = 'Last name is required.'
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
        Notification.objects.create(
            user=user,
            title="Login Successful",
            message="You have successfully logged in to your dashboard.",
            link="/user/dashboard/"
        )
        
        # Get all requests for the user
        all_requests = ServiceRequest.objects.filter(user=user)

        # Calculate the counts for each status
        active_requests_count = all_requests.filter(status='Active').count()
        pending_requests_count = all_requests.filter(status='Pending').count()
        completed_requests_count = all_requests.filter(status='Completed').count()
        
        total_spent = 0
        completed_requests = all_requests.filter(status='Completed')
        for req in completed_requests:
            if req.budget: # Only add if budget has a value
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
    Logs the user out by clearing the session.
    """
    if 'user_id' in request.session:
        del request.session['user_id']
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return redirect('options')



def request_help(request):
    """
    Handles the multi-step form for creating a new ServiceRequest.
    """

    # This view assumes the user must be logged in.
    # A @login_required decorator would be ideal here.
    if 'user_id' not in request.session:
        return redirect('helpersapp:auth') # Redirect to your login page

    if request.method == 'POST':
        try:
            # --- Get the logged-in user ---
            current_user = User.objects.get(id=request.session['user_id'])

            # --- Step 1: Service Details ---
            service_category = request.POST.get('service_category')
            subcategory = request.POST.get('subcategory')
            task_description = request.POST.get('task_description')
            
            # --- Step 2: Location & Schedule ---
            address = request.POST.get('address')
            preferred_date = request.POST.get('preferred_date')
            preferred_time = request.POST.get('preferred_time')
            is_flexible = 'is_flexible' in request.POST
            is_urgent = 'is_urgent' in request.POST
            has_parking = 'has_parking' in request.POST

            # --- Step 3: Budget & Requirements ---
            payment_type = request.POST.get('payment_type')
            budget = request.POST.get('budget')
            special_requirements = request.POST.get('special_requirements')
            helper_brings_tools = 'helper_brings_tools' in request.POST
            background_check_required = 'background_check_required' in request.POST
            insurance_needed = 'insurance_needed' in request.POST
            experience_required = 'experience_required' in request.POST

            # --- Create the ServiceRequest instance ---
            new_request = ServiceRequest.objects.create(
                user=current_user,
                service_category=service_category,
                subcategory=subcategory,
                task_description=task_description,
                address=address,
                preferred_date=preferred_date,
                preferred_time=preferred_time,
                is_flexible=is_flexible,
                is_urgent=is_urgent,
                has_parking=has_parking,
                payment_type=payment_type,
                budget=budget,
                special_requirements=special_requirements,
                helper_brings_tools=helper_brings_tools,
                background_check_required=background_check_required,
                insurance_needed=insurance_needed,
                experience_required=experience_required,
                status='Pending' # Default status
            )

            # --- Handle multiple photo uploads ---
            uploaded_images = request.FILES.getlist('photos') # 'photos' is the name of your file input
            for image in uploaded_images:
                RequestPhoto.objects.create(
                    service_request=new_request,
                    image=image
                )
            
            # --- REDIRECT TO PAYMENT OPTIONS INSTEAD OF DASHBOARD ---
            return redirect('helpersapp:payment_options', request_id=new_request.id)
        

        except Exception as e:
            # Handle potential errors, e.g., user not found or invalid data
            messages.error(request, f"An error occurred: {e}")
            return render(request, 'request_help.html', {'user': current_user}) # Re-render the form page with an error

    
    _user = User.objects.get(id=request.session['user_id'])
    # For a GET request, just display the form
    return render(request, 'request_help.html', {'user': _user})




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
    
    # A user can only contact the helper if one has been accepted
    if not service_request.accepted_helper:
         messages.error(request, "No helper has been assigned to this request yet.")
         Notification.objects.create(
        user=service_request.user, # Notify the Requester
        title="No Helper Assigned",
        message=f"No helper has been assigned to your request for {service_request.subcategory} yet.",
        link=f"/user/request/{service_request.id}/" # Link to details
        )
         return redirect('helpersapp:dashboard')

    chat_messages = ChatMessage.objects.filter(service_request=service_request)
    
    context = {
        'request': service_request,
        'helper': service_request.accepted_helper,
        'chat_messages': chat_messages
    }
    return render(request, 'contact_helper.html', context)

def get_chat_messages(request, request_id):
    """
    API endpoint to fetch chat messages as JSON for real-time updates.
    """
    chat_messages = ChatMessage.objects.filter(service_request_id=request_id).values(
        'message', 
        'timestamp', 
        'sender_user__fname', 
        'sender_helper__fname'
    )
    return JsonResponse(list(chat_messages), safe=False)

def send_chat_message(request, request_id):
    """
    API endpoint to handle sending a new chat message.
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
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)














def options(request):
    return render(request, 'options.html')
