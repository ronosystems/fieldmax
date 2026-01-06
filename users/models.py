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

# Auto-create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()