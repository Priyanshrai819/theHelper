from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import User

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a new user instance when a user signs up via a social provider.
        """
        user = sociallogin.user
        
        # Check if a user with this email already exists in our custom User model
        try:
            existing_user = User.objects.get(email=user.email)
            # If they exist, link the social account to the existing user
            sociallogin.user = existing_user
            sociallogin.save(request)
            return existing_user
        except User.DoesNotExist:
            # If it's a new user, map the data from Google to our User model
            user.fname = sociallogin.account.extra_data.get('given_name', '')
            user.lname = sociallogin.account.extra_data.get('family_name', '')
            user.email = user.email
            # The password will be unusable since they log in via Google
            user.set_unusable_password()
            user.save()
            sociallogin.save(request)
            return user
