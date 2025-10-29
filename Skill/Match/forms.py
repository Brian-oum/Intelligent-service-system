# service_provider/forms.py
from django import forms
from .models import ServiceProvider, CompanyDocument
from django.contrib.auth import get_user_model

User = get_user_model()  # Use the custom user model

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = User  # now points to your custom user model
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data


class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = ['company_name', 'contact_number', 'address', 'services_offered', 'logo', 'latitude', 'longitude']
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'company_name': forms.TextInput(attrs={'class':'form-control'}),
            'contact_number': forms.TextInput(attrs={'class':'form-control'}),
            'address': forms.Textarea(attrs={'class':'form-control', 'rows':2}),
            'services_offered': forms.Textarea(attrs={'class':'form-control', 'rows':4}),
        }


class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ['document_name', 'document_file']
        widgets = {
            'document_name': forms.TextInput(attrs={'class':'form-control'}),
            'document_file': forms.FileInput(attrs={'class':'form-control'}),
        }
