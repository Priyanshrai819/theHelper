from django.db import models
import uuid
from django.utils import timezone


class User(models.Model):
    fname = models.CharField(max_length=50)
    lname = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # Store hashed password in production
    profile_image = models.ImageField(upload_to='profile_image/', blank=True, null=True)

    def __str__(self):
        return f"{self.fname} {self.lname}"
    



class ServiceRequest(models.Model):
    """
    Represents a single help request created by a user.
    """
    # --- CHOICES ---
    SERVICE_CATEGORY_CHOICES = [
        ('cleaning', 'Cleaning Services'),
        ('moving', 'Moving & Delivery'),
        ('assembly', 'Furniture Assembly'),
        ('gardening', 'Gardening & Landscaping'),
        ('handyman', 'Handyman Services'),
        ('other', 'Other Services'),
    ]
    TIME_SLOT_CHOICES = [
        ('Morning', 'Morning (8am - 12pm)'),
        ('Afternoon', 'Afternoon (12pm - 5pm)'),
        ('Evening', 'Evening (5pm - 9pm)'),
    ]
    PAYMENT_TYPE_CHOICES = [('Hourly', 'Hourly Rate'), ('Fixed', 'Fixed Price')]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
    ]

    # --- RELATIONSHIPS ---
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_requests')

     # --- 2. ADD THIS FIELD ---
    accepted_helper = models.ForeignKey(
        'helpers.Helper',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_requests'
    )

    otp_code = models.CharField(max_length=6, blank=True, null=True, help_text="6-digit code for verifying job completion")


    # --- FIELDS ---
    service_category = models.CharField(max_length=50, choices=SERVICE_CATEGORY_CHOICES)
    subcategory = models.CharField(max_length=100)
    task_description = models.TextField(max_length=500)
    address = models.CharField(max_length=255)
    preferred_date = models.DateField()
    preferred_time = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    is_flexible = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    budget = models.DecimalField(max_digits=8, decimal_places=2)
    special_requirements = models.TextField(blank=True, null=True)
    helper_brings_tools = models.BooleanField(default=False)
    background_check_required = models.BooleanField(default=False)
    insurance_needed = models.BooleanField(default=False)
    experience_required = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    
    # --- NEW PAYMENT STATUS FIELD ---
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"'{self.get_service_category_display()}' request by {self.user.fname}"

    class Meta:
        ordering = ['-created_at']


class ChatMessage(models.Model):
    """
    Stores a single message in a conversation related to a ServiceRequest.
    """
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='chat_messages')
    sender_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, help_text="Set if the sender is a User")
    sender_helper = models.ForeignKey('helpers.Helper', on_delete=models.CASCADE, null=True, blank=True, help_text="Set if the sender is a Helper")
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.sender_user:
            return f"Message from User {self.sender_user.fname} on Request #{self.service_request.id}"
        else:
            return f"Message from Helper {self.sender_helper.fname} on Request #{self.service_request.id}"

    class Meta:
        ordering = ['timestamp']



class RequestPhoto(models.Model):
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='request_photos/')

    def __str__(self):
        return f"Photo for request {self.service_request.id}"



class Payment(models.Model):
    """
    Stores details of a payment transaction for a ServiceRequest.
    """
    service_request = models.OneToOneField(ServiceRequest, on_delete=models.CASCADE, related_name='payment')
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100)
    razorpay_signature = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Request {self.service_request.id}"






class Notification(models.Model):
    """
    Stores notifications for both Requesters and Helpers.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='requester_notifications')
    helper = models.ForeignKey('helpers.Helper', on_delete=models.CASCADE, null=True, blank=True, related_name='helper_notifications_userapp')
    title = models.CharField(max_length=100)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True) # URL to redirect when clicked
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user or self.helper}: {self.title}"




# --- NEW PASSWORD RESET MODEL ---
class PasswordResetToken(models.Model):
    """
    Stores temporary tokens for password resets. 
    It links directly to the email so it works for both Users and Helpers.
    """
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        # Token is valid for 1 hour (3600 seconds)
        return (timezone.now() - self.created_at).total_seconds() < 3600

    def __str__(self):
        return f"Reset token for {self.email}"