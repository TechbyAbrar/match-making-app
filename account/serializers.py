from account.models import UserAuth, MakeYourProfilePop
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .utils import generate_username, send_otp_email, generate_tokens_for_user, generate_otp, get_otp_expiry
from django.contrib.auth import get_user_model
User = get_user_model()
from django.conf import settings


# profile pop up image serializer
class MakeYourProfilePopSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MakeYourProfilePop
        fields = ["id", "user", "image", "image_url", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def get_image_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

    def validate(self, attrs):
        user = self.context["request"].user
        if self.instance is None and user.pop_images.count() >= 7:
            raise serializers.ValidationError("You can upload a maximum of 7 pop-up images.")
        return attrs

class UserSerializer(serializers.ModelSerializer):
    pop_images = MakeYourProfilePopSerializer(many=True, read_only=True)
    profile_pic_url = serializers.SerializerMethodField()
    height = serializers.SerializerMethodField()
    height_inches_total = serializers.SerializerMethodField()
    age = serializers.ReadOnlyField()  # uses @property age
    profile_link = serializers.ReadOnlyField()

    class Meta:
        model = UserAuth
        fields = [
            "user_id",
            "email",
            "phone",
            "username",
            "full_name",

            "profile_pic",
            "profile_pic_url",

            "gender",
            "brings",
            "that",
            "looking_for",

            "professional_field",
            "interests",
            "lifestyle",
            "hobbies",
            "bio",

            "height_feet",
            "height_inches",
            "height",
            "height_inches_total",

            "dob",
            "age",

            "city",
            "province",
            "location",
            "distance",

            "is_verified",
            "is_active",
            "is_online",
            "last_login",

            "is_subscribed",
            "subscription_expiry",
            
            "pop_images",

            "created_at",
            "updated_at",

            "profile_link",
        ]

        read_only_fields = [
            "user_id",
            "is_active",
            "is_verified",
            "is_online",
            "last_login",
            "created_at",
            "updated_at",
            "profile_link",
            "age",
        ]

    def get_profile_pic_url(self, obj):
        if obj.profile_pic:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile_pic.url)
            return f"{settings.SITE_BASE_URL}{obj.profile_pic.url}"
        return None

    def get_height(self, obj):
        if obj.height_feet or obj.height_inches:
            return obj.height_display()
        return None

    def get_height_inches_total(self, obj):
        return obj.height_in_inches()

        
class SignupSerialzier(serializers.Serializer):
    # full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": "Email already registered."})
        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")

        if not validated_data.get("username"):
            validated_data["username"] = generate_username(validated_data["email"])

        user = User(**validated_data)
        user.password = make_password(password)

        # Generate OTP
        user.otp = generate_otp()
        user.otp_expired = get_otp_expiry()
        user.save()

        # Send OTP via email/SMS
        message = f"Your verification code is {user.otp}. It expires in 30 minutes."
        send_otp_email(user.email, message)

        return user
    
    
class VerifyOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, write_only=True)

    def validate(self, data):
        try:
            user = User.objects.get(otp=data["otp"], otp_expired__gte=timezone.now())
        except User.DoesNotExist:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})

        if user.is_verified:
            raise serializers.ValidationError({"otp": "User already verified."})

        data["user"] = user
        return data

    def save(self, **kwargs):
        user = self.validated_data["user"]
        from django.db import transaction
        with transaction.atomic():
            user.is_verified = True
            user.otp = None
            user.otp_expired = None
            user.save(update_fields=["is_verified", "otp", "otp_expired"])
        return user
    
    
    
class ResendVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate(self, data):
        try:
            user = User.objects.get(email=data["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Email not registered."})

        if user.is_verified:
            raise serializers.ValidationError({"email": "User already verified."})

        data["user"] = user
        return data

    def save(self, **kwargs):
        user = self.validated_data["user"]

        # Generate new OTP
        user.otp = generate_otp()
        user.otp_expired = get_otp_expiry()
        user.save(update_fields=["otp", "otp_expired"])

        # Send SMS
        message = f"Your new verification code is {user.otp}. It expires in 30 minutes."
        send_otp_email(user.email, message)

        return user
    
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=6)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError({
                "email": "Email is required.",
                "password": "Password is required."
            })

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})

        attrs['user'] = user
        return attrs



class ForgetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.only('email', 'otp', 'otp_expired').get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("user account not found.")

        self.context['user'] = user
        return value

    def save(self):
        user = self.context['user']
        user.set_otp()
        user.save(update_fields=['otp', 'otp_expired'])
        send_otp_email(user.email, user.otp)
        return user


class VerifyForgetPasswordOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, write_only=True)

    def validate_otp(self, value):
        try:
            user = User.objects.only(
                'user_id', 'email', 'otp', 'otp_expired', 'is_verified'
            ).get(otp=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired OTP.")

        if not user.is_verified:
            raise serializers.ValidationError("user account is not verified. Please, verify your email first.")

        if user.otp_expired is None or user.otp_expired < timezone.now():
            raise serializers.ValidationError("OTP has expired.")

        self.context['user'] = user
        return value

    def create_access_token(self):
        user = self.context['user']
        tokens = generate_tokens_for_user(user)
        return tokens['access']

    def to_representation(self, instance):
        """Custom response after successful OTP verification."""
        user = self.context['user']
        return {
            "success": True,
            "message": "OTP verified successfully.",
            "access_token": self.create_access_token(),
            "user": {
                "user_id": user.user_id,
                "email": user.email,
            },
        }


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        new = attrs.get("new_password")
        confirm = attrs.get("confirm_password")

        if new != confirm:
            raise serializers.ValidationError("Passwords do not match.")

        user = self.context["request"].user
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("otp verification token required.")

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
    

# multiselect field serializer
class MultiSelectFieldSerializer(serializers.ListField):
    child = serializers.CharField()

    def to_representation(self, value):
        # value comes as a list already from django-multiselectfield
        return value or []

    def to_internal_value(self, data):
        if isinstance(data, str):
            raise serializers.ValidationError("Expected a list of values, not a string.")

        return super().to_internal_value(data)


# profile update serializer
class UserProfileUpdateSerializer(serializers.ModelSerializer):
    brings = MultiSelectFieldSerializer(required=False)
    that = MultiSelectFieldSerializer(required=False)
    looking_for = MultiSelectFieldSerializer(required=False)

    class Meta:
        model = UserAuth
        fields = [
            "full_name",
            "username",
            "phone",
            "profile_pic",
            "gender",
            "brings",
            "that",
            "looking_for",
            "professional_field",
            "interests",
            "lifestyle",
            "hobbies",
            "bio",
            "height_feet",
            "height_inches",
            "dob",
            'country',
            "city",
            "province",
            "location",
            "distance",
        ]

    def validate_username(self, value):
        user = self.context["request"].user
        if UserAuth.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value
    



# who liked user serializer
class WhoLikedUserSerializer(serializers.ModelSerializer):
    profile_pic = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    class Meta:
        model = UserAuth
        fields = ["user_id", "username", "full_name", "is_online", "profile_pic", "hobbies", 'distance']

    def get_profile_pic(self, obj):

        request = self.context.get("request")
        pic = getattr(obj, "profile_pic", None)


        if not pic:
            return None
        try:
            url = pic.url
        except Exception:
            # File may not exist on storage
            return None
        if request is None:
        # relative URL
            return url
        return request.build_absolute_uri(url)


    def get_distance(self, obj):
        return getattr(obj, "distance", None)
    