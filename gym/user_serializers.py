from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


class UserSerializer(serializers.ModelSerializer):
    """Serializer pentru utilizatori (manageri)"""
    is_admin = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'is_staff', 'is_superuser', 'is_admin', 'date_joined', 'last_login']
        read_only_fields = ['date_joined', 'last_login']
    
    def get_is_admin(self, obj):
        """Un utilizator este admin dacă e superuser sau staff"""
        return obj.is_superuser or obj.is_staff


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer pentru crearea utilizatorilor noi"""
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['username', 'password', 'password_confirm']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Parolele nu coincid."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            is_staff=False,  # Managerii normali nu sunt staff
            is_superuser=False
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer pentru actualizarea utilizatorilor"""
    password = serializers.CharField(
        write_only=True, 
        required=False, 
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True, 
        required=False,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['username', 'password', 'password_confirm', 'is_active']
    
    def validate(self, attrs):
        if 'password' in attrs or 'password_confirm' in attrs:
            if attrs.get('password') != attrs.get('password_confirm'):
                raise serializers.ValidationError({"password_confirm": "Parolele nu coincid."})
        return attrs
    
    def update(self, instance, validated_data):
        validated_data.pop('password_confirm', None)
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance
