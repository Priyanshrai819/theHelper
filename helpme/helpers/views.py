from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from helpersapp.models import ServiceRequest  # Assuming Helper model is in helpersapp
from helpersapp.models import Notification as UserNotification
from django.contrib import messages
from .models import Helper, JobApplication,Notification
from django.db.models import Sum
import random
from django.http import JsonResponse



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