from django.contrib import admin
from .models import User, ServiceRequest, RequestPhoto, Payment
# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'fname', 'lname', 'email', 'profile_image')
    search_fields = ('email', 'fname', 'lname')
    list_filter = ('email',)
    ordering = ('-id',)
    readonly_fields = ('id',)
    
    def has_add_permission(self, request):
        return False
    



class RequestPhotoInline(admin.TabularInline):
    """
    Allows photos to be added directly within the ServiceRequest admin page.
    'TabularInline' provides a compact, table-based layout.
    """
    model = RequestPhoto
    extra = 1  # Show 1 extra empty slot for a new photo by default.

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    """
    Customizes the display and functionality of the ServiceRequest model in the admin panel.
    """
    # Use the inline class to embed photo management
    inlines = [RequestPhotoInline]
    
    # Fields to display in the main list view of requests
    list_display = ('service_category', 'user', 'status', 'preferred_date', 'created_at')
    
    # Fields that can be used to filter the list of requests
    list_filter = ('status', 'service_category', 'created_at')
    
    # Fields that can be searched
    search_fields = ('user__fname', 'user__lname', 'user__email', 'task_description', 'address')
    
    # Fields that are read-only and cannot be edited in the admin
    readonly_fields = ('created_at', 'updated_at')
    
    # Organize the edit form into logical sections
    fieldsets = (
        ('Request Details', {
            'fields': ('user', 'service_category', 'subcategory', 'task_description', 'status')
        }),
        ('Location & Schedule', {
            'fields': ('address', 'preferred_date', 'preferred_time', 'is_flexible', 'is_urgent', 'has_parking')
        }),
        ('Budget & Requirements', {
            'fields': ('payment_type', 'payment_status', 'budget', 'special_requirements', 'helper_brings_tools', 'background_check_required', 'insurance_needed', 'experience_required')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',) # Make this section collapsible
        }),
    )




class PaymentInline(admin.StackedInline):
    """
    Displays payment details directly within the associated ServiceRequest admin page.
    Made read-only because payments should not be manually altered.
    """
    model = Payment
    can_delete = False
    readonly_fields = ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'amount', 'timestamp')
    
    def has_add_permission(self, request, obj=None):
        return False
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Customizes the display for the Payment model.
    Payments are typically viewed here but not edited.
    """
    list_display = ('service_request', 'amount', 'razorpay_payment_id', 'timestamp')
    search_fields = ('service_request__id', 'razorpay_payment_id')
    readonly_fields = ('service_request', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'amount', 'timestamp')

    def has_add_permission(self, request):
        # Prevents manually adding new payments from the admin.
        return False


  