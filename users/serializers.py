# users/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, Role

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']

class ProfileSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    
    class Meta:
        model = Profile
        fields = ['role', 'phone_number', 'id_number', 'date_of_birth', 'passport_image']

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'profile']