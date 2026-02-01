from django import forms
from .models import StaffApplication

class StaffApplicationForm(forms.ModelForm):
    class Meta:
        model = StaffApplication
        fields = [
            'first_name', 'last_name', 'email', 'phone', 
            'id_number', 'address', 'position', 'experience',
            'passport_photo', 'id_front', 'id_back',
            'terms_accepted', 'privacy_accepted'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@email.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254 7XX XXX XXX'
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your ID or passport number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your full residential address'
            }),
            'position': forms.Select(attrs={
                'class': 'form-control'
            }),
            'experience': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your previous work experience...'
            }),
            'terms_accepted': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'privacy_accepted': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_passport_photo(self):
        photo = self.cleaned_data.get('passport_photo')
        if photo:
            # Check file size (2MB max)
            if photo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Passport photo size should not exceed 2MB.")
            
            # Check file extension
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            extension = photo.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                raise forms.ValidationError("Unsupported file format. Please upload JPG, JPEG, PNG or GIF.")
        
        return photo
    
    def clean_id_front(self):
        photo = self.cleaned_data.get('id_front')
        if photo:
            if photo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("ID front photo size should not exceed 2MB.")
        return photo
    
    def clean_id_back(self):
        photo = self.cleaned_data.get('id_back')
        if photo:
            if photo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("ID back photo size should not exceed 2MB.")
        return photo
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if StaffApplication.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please use a different email.")
        return email
    
    def clean_id_number(self):
        id_number = self.cleaned_data.get('id_number')
        if StaffApplication.objects.filter(id_number=id_number).exists():
            raise forms.ValidationError("This ID number is already registered.")
        return id_number