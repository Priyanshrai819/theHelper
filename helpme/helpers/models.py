from django.db import models
from helpersapp.models import ServiceRequest # Import ServiceRequest from your user app

class Helper(models.Model):
    """
    Stores all information for a person providing services (a helper).
    This is a separate user type from the regular User.
    """
    fname = models.CharField(max_length=50)
    lname = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128) # Always store hashed passwords
    phone_number = models.CharField(max_length=15, blank=True, null=True)  # Optional phone number
    profile_image = models.ImageField(upload_to='helper_profiles/', blank=True, null=True)
    
    # --- Profile Details ---
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    zip = models.CharField(max_length=10)
    
    def __str__(self):
        return f"Helper: {self.fname} {self.lname}"

class JobApplication(models.Model):
    """
    Represents when a helper applies for a specific service request.
    """
    STATUS_CHOICES = [
        ('Applied', 'Applied'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]
    
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='applications')
    helper = models.ForeignKey(Helper, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Applied')
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.helper.fname} applied for Request #{self.service_request.id}"

    