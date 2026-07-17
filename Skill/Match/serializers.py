from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, ServiceProvider, ServiceCategory, Service,
    ServiceRequest, Review, CompanyDocument
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone', 'location']
        read_only_fields = ['id']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name', 'role', 'phone', 'location']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError("Invalid credentials")
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Must include username and password")

        return attrs


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id', 'slug']


class CompanyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyDocument
        fields = ['id', 'service_provider', 'document_name', 'document_file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ServiceProviderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    documents = CompanyDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceProvider
        fields = [
            'id', 'user', 'company_name', 'contact_number', 'address',
            'website', 'profile_completed', 'is_verified', 'is_active',
            'latitude', 'longitude', 'created_at', 'documents'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class ServiceSerializer(serializers.ModelSerializer):
    provider = ServiceProviderSerializer(read_only=True)
    category = ServiceCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceCategory.objects.all(),
        source='category',
        write_only=True
    )
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceProvider.objects.all(),
        source='provider',
        write_only=True
    )

    class Meta:
        model = Service
        fields = [
            'id', 'provider', 'provider_id', 'category', 'category_id',
            'title', 'description', 'is_verified', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    provider = ServiceProviderSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    service_request = serializers.PrimaryKeyRelatedField(
        queryset=ServiceRequest.objects.all()
    )

    class Meta:
        model = Review
        fields = [
            'id', 'service_request', 'provider', 'user',
            'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ServiceRequestSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        source='service',
        write_only=True
    )

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'user', 'service', 'service_id', 'location',
            'latitude', 'longitude', 'description', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class ServiceRequestDetailSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    review = ReviewSerializer(read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'user', 'service', 'location',
            'latitude', 'longitude', 'description', 'status', 'created_at', 'review'
        ]
        read_only_fields = ['id', 'user', 'created_at']
