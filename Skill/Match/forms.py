# service_provider/forms.py

from django import forms
from django.contrib.auth import get_user_model
from .models import ServiceProvider, CompanyDocument, Service, ServiceCategory

User = get_user_model()


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
    latitude = forms.FloatField(
        widget=forms.HiddenInput(),
        required=False
    )

    longitude = forms.FloatField(
        widget=forms.HiddenInput(),
        required=False
    )

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
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Acme Services Ltd'
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. +254...'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Street, Building, Office number...'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        lat = cleaned_data.get("latitude")
        lng = cleaned_data.get("longitude")

        if lat is None or lng is None:
            raise forms.ValidationError(
                "You must pin your company location on the map before submitting."
            )

        return cleaned_data


# =========================
# Service Form (Option 3)
# =========================

class ServiceForm(forms.ModelForm):

    # Override ForeignKey field with text input
    category = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'list': 'category_list',
            'placeholder': 'Enter or select a category'
        })
    )

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
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'min_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean_category(self):
        name = self.cleaned_data['category'].strip()

        # Case-insensitive lookup
        category = ServiceCategory.objects.filter(name__iexact=name).first()

        if not category:
            category = ServiceCategory.objects.create(name=name)

        return category


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
