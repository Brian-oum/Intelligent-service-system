# service_provider/forms.py

from django import forms
from django.contrib.auth import get_user_model
from .models import ServiceProvider, CompanyDocument, Service, ServiceCategory, Review, User
from django.contrib.auth.forms import PasswordChangeForm 
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
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'min_price': forms.NumberInput(attrs={
                'placeholder': 'e.g. 1500',
                'min': '0',
                'step': '50',
            }),
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


class CompanyDocumentsForm(forms.Form):
    """
    Verification documents collected during provider signup (Step 2).

    Each of these becomes its own CompanyDocument row (see
    provider_signup_step2 in views.py), so this is a plain Form rather
    than a ModelForm — there's no single model instance that maps to
    "three files at once".
    """
    business_certificate = forms.FileField(
        label="Business Registration Certificate",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text="Certificate of incorporation / business registration.",
    )
    kra_pin_certificate = forms.FileField(
        label="KRA PIN Certificate",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text="Your KRA PIN certificate, for tax compliance verification.",
    )
    national_id = forms.FileField(
        label="National ID",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text="ID of the business owner or authorized representative.",
    )

    # Document names are fixed (not user-typed) so we can label each
    # CompanyDocument row consistently no matter what the uploader names
    # the underlying file.
    DOCUMENT_LABELS = {
        'business_certificate': 'Business Registration Certificate',
        'kra_pin_certificate': 'KRA PIN Certificate',
        'national_id': 'National ID',
    }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'location']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ServiceProviderUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = [
            'company_name',
            'contact_number',
            'address',
            'website',
            'latitude',
            'longitude'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'latitude': forms.HiddenInput,
            'longitude': forms.HiddenInput,
        }

class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(min_value=1, max_value=5, widget=forms.NumberInput(attrs={'type':'number'}))

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows':3, 'placeholder': 'Write your review...'})
        }

class NotificationSettingsForm(forms.ModelForm):
    """Tab: Notifications"""
    class Meta:
        model = User
        fields = [
            'email_notifications',
            'sms_notifications',
            'request_update_alerts',
            'marketing_emails',
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'set-switch__input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'set-switch__input'}),
            'request_update_alerts': forms.CheckboxInput(attrs={'class': 'set-switch__input'}),
            'marketing_emails': forms.CheckboxInput(attrs={'class': 'set-switch__input'}),
        }
 
 
class PrivacySettingsForm(forms.ModelForm):
    """Tab: Privacy"""
    class Meta:
        model = User
        fields = ['profile_visibility', 'show_phone_publicly']
        widgets = {
            'profile_visibility': forms.Select(attrs={'class': 'set-input'}),
            'show_phone_publicly': forms.CheckboxInput(attrs={'class': 'set-switch__input'}),
        }
 
 
class AppearanceSettingsForm(forms.ModelForm):
    """Tab: Appearance (theme + language). Theme is also mirrored instantly via JS/localStorage."""
    class Meta:
        model = User
        fields = ['theme_preference', 'preferred_language']
        widgets = {
            'theme_preference': forms.Select(attrs={'class': 'set-input'}),
            'preferred_language': forms.Select(attrs={'class': 'set-input'}),
        }
 
 
class AvatarUploadForm(forms.ModelForm):
    """Tab: Profile — optional avatar upload."""
    class Meta:
        model = User
        fields = ['avatar']
 
 
class DeactivateAccountForm(forms.Form):
    """Tab: Danger Zone"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'set-input', 'placeholder': 'Confirm your password'}),
        label="Confirm password"
    )
    confirm = forms.BooleanField(
        required=True,
        label="I understand this will deactivate my account"
    )