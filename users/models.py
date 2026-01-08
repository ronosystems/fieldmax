from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Role(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Rename role_fk to role
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Other fields
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Phone Number")
    id_number = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="ID Number")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Date of Birth")
    passport_image = models.ImageField(upload_to='passports/', blank=True, null=True, verbose_name="Passport Image")
    
    def __str__(self):
        return f"{self.user.username}'s profile"


# ✅ FIXED: Auto-create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create profile only when user is first created"""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save profile when user is saved, create if doesn't exist"""
    # Use get_or_create to avoid IntegrityError
    try:
        profile = instance.profile
        profile.save()
    except Profile.DoesNotExist:
        # Profile doesn't exist, create it
        Profile.objects.create(user=instance)