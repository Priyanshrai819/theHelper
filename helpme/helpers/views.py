from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from helpersapp.models import User,ServiceRequest  # Assuming Helper model is in helpersapp
from helpersapp.models import Notification as UserNotification
from django.contrib import messages
from .models import Helper, JobApplication,Notification,PasswordResetToken
from django.db.models import Sum
import random
from django.http import JsonResponse
from helpersapp.models import ChatMessage, ServiceRequest, Notification

from django.conf import settings

# from django.core.mail import send_mail

# from django.urls import reverse






# def forgot_password_view(request):
#     """
#     Handles the request to send a password reset link to the user's email.
#     """
#     if request.method == 'POST':
#         email = request.POST.get('email')
        
#         # 1. Check if email exists in either the User or Helper tables
#         user_exists = User.objects.filter(email=email).exists()
#         helper_exists = Helper.objects.filter(email=email).exists()
        
#         if user_exists or helper_exists:
#             # 2. Delete any existing unused tokens for this email to prevent spam
#             PasswordResetToken.objects.filter(email=email).delete()
            
#             # 3. Create a new secure, random token
#             token_obj = PasswordResetToken.objects.create(email=email)
            
#             # 4. Build the full URL for the reset link (e.g., http://127.0.0.1:8000/reset-password/<token>/)
#             reset_url = request.build_absolute_uri(
#                 reverse('helpersapp:reset_password', args=[token_obj.token])
#             )
            
#             # 5. Send the Email
#             try:
#                 send_mail(
#                     subject='Password Reset Request - theHelpers',
#                     message=f'Hello,\n\nYou requested a password reset. Click the link below to set a new password:\n\n{reset_url}\n\nThis link will expire in 1 hour. If you did not request this, please ignore this email.',
#                     from_email=settings.DEFAULT_FROM_EMAIL,
#                     recipient_list=[email],
#                     fail_silently=False,
#                 )
#             except Exception as e:
#                 print(f"Error sending email: {e}")
                
#         # Always show a success message even if the email wasn't found (security best practice)
#         messages.success(request, "If an account with that email exists, we have sent a password reset link to your inbox.")
#         return redirect('helpersapp:forgot_password')
        
#     return render(request, 'forgot_password.html')


# def reset_password_view(request, token):
#     """
#     Handles the actual password reset using the token from the email link.
#     """
#     # 1. Look up the token in the database
#     token_obj = get_object_or_404(PasswordResetToken, token=token)
    
#     # 2. Check if the token is older than 1 hour
#     if not token_obj.is_valid():
#         messages.error(request, "This password reset link has expired. Please request a new one.")
#         return redirect('helpersapp:forgot_password')
        
#     if request.method == 'POST':
#         password = request.POST.get('password')
#         confirm_password = request.POST.get('confirm_password')
        
#         # 3. Ensure passwords match
#         if password != confirm_password:
#             messages.error(request, "Passwords do not match.")
#             return render(request, 'reset_password.html', {'token': token})
            
#         # 4. Hash the new password securely
#         hashed_password = make_password(password)
        
#         # 5. Apply the new password to the correct account type (User or Helper)
#         user = User.objects.filter(email=token_obj.email).first()
#         if user:
#             user.password = hashed_password
#             user.save()
            
#         helper = Helper.objects.filter(email=token_obj.email).first()
#         if helper:
#             helper.password = hashed_password
#             helper.save()
            
#         # 6. Delete the token so it cannot be reused
#         token_obj.delete()
        
#         messages.success(request, "Your password has been reset successfully! You can now log in.")
        
#         # Redirect to the correct login page based on account type
#         if helper:
#             return redirect('helpers:helper_auth')
#         return redirect('helpersapp:auth')
        
#     # Render the reset password HTML template you selected
#     return render(request, 'reset_password.html', {'token': token})








def helper_chat_view(request, request_id):
    """
    Displays the chat page for the Helper.
    """
    if 'helper_id' not in request.session:
        return redirect('helpers:helper_auth')
    
    helper = get_object_or_404(Helper, id=request.session['helper_id'])
    # Ensure the helper can only access chats for jobs they accepted
    service_request = get_object_or_404(ServiceRequest, id=request_id, accepted_helper=helper)
    
    return render(request, 'helpers/helper_chat.html', {
        'request': service_request,
        'helper': helper,
        'user': service_request.user
    })

def helper_get_chat_messages(request, request_id):
    """
    API endpoint to fetch chat messages for the Helper.
    """
    if 'helper_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    messages = ChatMessage.objects.filter(service_request_id=request_id).order_by('timestamp')
    data = []
    for msg in messages:
        data.append({
            'id': msg.id,
            'text': msg.message,
            # If sender_helper exists, it means "I" (the helper) sent it
            'is_me': bool(msg.sender_helper), 
            'sender_name': msg.sender_helper.fname if msg.sender_helper else msg.sender_user.fname,
            'time': msg.timestamp.strftime('%I:%M %p')
        })
    return JsonResponse({'messages': data})

def helper_send_chat_message(request, request_id):
    """
    API endpoint to send a new chat message from the Helper.
    """
    if request.method == 'POST' and 'helper_id' in request.session:
        message_text = request.POST.get('message')
        if message_text:
            helper = get_object_or_404(Helper, id=request.session['helper_id'])
            service_request = get_object_or_404(ServiceRequest, id=request_id, accepted_helper=helper)
            
            # Save the message to the database
            ChatMessage.objects.create(
                service_request=service_request,
                sender_helper=helper,
                message=message_text
            )
            
            # Create a notification for the User (Requester)
            Notification.objects.create(
                user=service_request.user,
                title="New Message from Helper",
                message=f"{helper.fname} sent you a message regarding your {service_request.get_service_category_display()} request.",
                link=f"/contact-helper/{service_request.id}/"
            )
            return JsonResponse({'status': 'success'})
            
    return JsonResponse({'status': 'error'}, status=400)





def helper_profile_settings(request):
    """
    Allows the logged-in Helper to update their profile details.
    """
    # 1. Security Check: Ensure helper is logged in
    if 'helper_id' not in request.session:
        return redirect('helpers:helper_auth')
    
    # 2. Get the Helper Object
    helper = get_object_or_404(Helper, id=request.session['helper_id'])
    
    # 3. Handle Form Submission (POST)
    if request.method == 'POST':
        try:
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            address = request.POST.get('address')
            city = request.POST.get('city')
            state = request.POST.get('state')
            zip_code = request.POST.get('zip')
            
            # Update fields if data is provided
            if fname: helper.fname = fname
            if lname: helper.lname = lname
            if address: helper.address = address
            if city: helper.city = city
            if state: helper.state = state
            if zip_code: helper.zip = zip_code
            
            # Handle Profile Image Upload
            if 'profile_image' in request.FILES:
                helper.profile_image = request.FILES['profile_image']
            
            # Save changes to the database
            helper.save()
            
            messages.success(request, "Profile updated successfully.")
            return redirect('helpers:helper_profile_settings')
            
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")

    # 4. Render the page (GET request)
    return render(request, 'helpers/helper_profile_settings.html', {'helper': helper})



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







def mark_job_completed(request, request_id):
    """
    Generates an OTP and displays the verification page for the helper.
    """
    if 'helper_id' not in request.session:
        return redirect('helpers:helper_auth')

    service_request = get_object_or_404(ServiceRequest, id=request_id)
    
    # Generate a random 6-digit OTP
    otp = str(random.randint(100000, 999999))
    service_request.otp_code = otp
    service_request.save()
    
    # The helper needs to get this OTP from the user in person
    messages.info(request, "Please ask the user for the 6-digit OTP to complete the job.")
    
    return render(request, 'helpers/verify_completion.html', {'request': service_request})






def helper_auth(request):
    """
    Handles both registration and login for Helpers.
    """
    if request.method == 'POST':
        # Differentiate based on the submit button's name attribute
        if 'register_submit' in request.POST:
            # --- Helper Registration Logic ---
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            address = request.POST.get('address')
            city = request.POST.get('city')
            state = request.POST.get('state')
            zip_code = request.POST.get('zip')
            phone_number = request.POST.get('phone_number') 
            email = request.POST.get('email')
            password = request.POST.get('password')
            profile_image = request.FILES.get('profile_image')

            # Basic Validation
            if Helper.objects.filter(email=email).exists():
                messages.error(request, 'A helper with this email already exists.')
                return redirect('helpers:helper_auth')

            # Create and save the new helper
            hashed_password = make_password(password)
            helper = Helper.objects.create(
                fname=fname,
                lname=lname,
                address=address,
                city=city,
                state=state,
                zip=zip_code,
                email=email,
                phone_number=phone_number,
                password=hashed_password,
                profile_image=profile_image
            )
            
            # Log the new helper in by creating a session
            request.session['helper_id'] = helper.id
            messages.success(request, f'Welcome, {helper.fname}! Your account has been created.')
            return redirect('helpers:helper_dashboard')

        elif 'login_submit' in request.POST:
            # --- Helper Login Logic ---
            email = request.POST.get('email')
            password = request.POST.get('password')

            try:
                helper = Helper.objects.get(email=email)
                if check_password(password, helper.password):
                    # Password is correct, create a session
                    request.session['helper_id'] = helper.id
                    messages.success(request, f"Welcome back, {helper.fname}!") 
                    return redirect('helpers:helper_dashboard')
                else:
                    # Password is incorrect
                    messages.error(request, 'Invalid email or password.')
                    return redirect('helpers:helper_auth')
            except Helper.DoesNotExist:
                # No helper found with that email
                messages.error(request, 'Invalid email or password.')
                return redirect('helpers:helper_auth')

    # If it's a GET request, just render the page
    return render(request, 'helpers/helper_auth.html')











def helper_dashboard(request):
    """
    Helper ka dashboard, jisme available, active, aur completed jobs dikhte hain.
    """
    # Step 1: Check if helper is logged in
    if 'helper_id' not in request.session:
        return redirect('helpers:helper_auth')

    try:
        # Step 2: Get the logged-in helper's object
        helper = Helper.objects.get(id=request.session['helper_id'])
        
        # Step 3: Fetch all job lists
        # Available Jobs: Jo pending hain aur kisi ne accept nahi kiye
        available_jobs = ServiceRequest.objects.filter(status='Pending', accepted_helper__isnull=True)
        
        # Accepted Jobs: Jo is helper ne accept kiye hain aur 'Active' hain
        accepted_jobs = ServiceRequest.objects.filter(accepted_helper=helper, status='Active')
        
        # Completed Jobs: Jo is helper ne complete kar diye hain
        completed_jobs = ServiceRequest.objects.filter(accepted_helper=helper, status='Completed')
        
        # Step 4: Calculate stats for the summary cards
        active_jobs_count = accepted_jobs.count()
        completed_jobs_count = completed_jobs.count()
        pending_applications_count = JobApplication.objects.filter(helper=helper, status='Applied').count()
        
        # Total Earning Calculation
        total_earned = 0
        # Filter for jobs that are both completed and paid
        paid_and_completed_jobs = completed_jobs.filter(payment_status='Paid')
        for job in paid_and_completed_jobs:
            if job.budget: # Only add if the budget has a value
                total_earned += job.budget
        
        # Step 5: Pass all data to the template
        context = {
            'helper': helper,
            'available_jobs': available_jobs,
            'accepted_jobs': accepted_jobs,
            'completed_jobs': completed_jobs,
            'active_jobs_count': active_jobs_count,
            'completed_jobs_count': completed_jobs_count,
            'pending_applications_count': pending_applications_count,
            'total_earned': total_earned,
        }
        return render(request, 'helpers/helper_dashboard.html', context)
    
    except Helper.DoesNotExist:
        # Agar session me galat ID hai, to logout karke login page pe bhejo
        del request.session['helper_id']
        return redirect('helpers:helper_auth')
    

    

def logout(request):
    """
    Logs the helper out by clearing the session.
    """
    if 'helper_id' in request.session:
        del request.session['helper_id']
    request.session.flush()
    return redirect('helpers:helper_auth')


def request_details(request, request_id):
    """
    Displays the full details of a single service request for a helper.
    """
    # 1. Check if a HELPER is logged in
    if 'helper_id' not in request.session:
        return redirect('helpers:helper_auth') # Corrected: Redirect to helper login
    
    # 2. Get the request by its ID only. A helper can view any available request.
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    
    # 3. Render the specific template for the helper's view of the details
    return render(request, 'helpers/helper_request_details.html', {'request': service_request})

def accept_request(request, request_id):
    """
    Allows a logged-in helper to accept a service request.
    This is the logic for the 'accept_request' URL name.
    """
    # 1. Check if a helper is logged in
    if 'helper_id' not in request.session:
        messages.error(request, "You must be logged in as a helper to accept jobs.")
        return redirect('helpers:helper_auth')

    # 2. Get the logged-in helper and the specific service request
    helper = get_object_or_404(Helper, id=request.session['helper_id'])
    service_request = get_object_or_404(ServiceRequest, id=request_id)

    # 3. Check if the job is still available to be accepted
    if service_request.status == 'Pending' and service_request.accepted_helper is None:
        # 4. Assign the helper to the request and update its status
        service_request.accepted_helper = helper
        service_request.status = 'Active'
        service_request.save()

        # 5. Create a JobApplication record to track this action
        JobApplication.objects.create(
            service_request=service_request,
            helper=helper,
            status='Accepted'
        )
        
        messages.success(request, f"You have successfully accepted the '{service_request.get_service_category_display()}' job.")
        Notification.objects.create(
        helper=helper, # Notify the Helper
        title="Job Accepted",
        message=f"You have accepted the request for {service_request.subcategory}.",
        link=f"/helpers/request/{service_request.id}/" # Link to details
    )
    #     UserNotification.objects.create(
    #     user=service_request.user, # Notify the Requester
    #     title="Job Accepted",
    #     message=f"Helper {helper.fname} has accepted your request for {service_request.subcategory}.",
    #     link=f"/user/request/{service_request.id}/" # Link to details   
    # )
        
    else:
        # If the job was already taken, inform the helper
        messages.error(request, "This job is no longer available.")
        
    # 6. Redirect the helper back to their dashboard
    return redirect('helpers:helper_dashboard')






