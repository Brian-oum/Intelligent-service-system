# service_provider/forms.py
from django import forms
from .models import ServiceProvider, CompanyDocument, Service
from django.contrib.auth import get_user_model

User = get_user_model()  # Use the custom user model


# =========================
# User Registration
# =========================

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data


# =========================
# Service Provider Profile
# =========================

class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = [
            'company_name',
            'contact_number',
            'address',
            'latitude',
            'longitude',
        ]
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# =========================
# Service Form (NEW)
# =========================

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            'category',
            'title',
            'description',
            'min_price',
            'max_price',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'min_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# =========================
# Company Documents
# =========================

class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ['document_name', 'document_file']
        widgets = {
            'document_name': forms.TextInput(attrs={'class': 'form-control'}),
            'document_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
