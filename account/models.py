from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.core.validators import RegexValidator
from .managers import UserManager
from .utils import generate_otp, get_otp_expiry, validate_image
from multiselectfield import MultiSelectField
from django.conf import settings

class UserAuth(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
    
    GENDER_CHOICES = [
        ('MALE', 'MALE'),
        ('FEMALE', 'FEMALE'),
        ('OTHER', 'OTHER'),
    ]

    BRINGS_CHOICES = [
        ('LOVE', 'LOVE'),
        ('FRIENDSHIP', 'FRIENDSHIP'),
        ('NETWORKING', 'NETWORKING'),
        ('NEURODIVERSE CONNECTION', 'NEURODIVERSE CONNECTION'),
        ('ADVENTURE PARTNER', 'ADVENTURE PARTNER'),
    ]
    
    THAT_CHOICES = [
        ('INTROVERT', 'INTROVERT'),
        ('EXTROVERT', 'EXTROVERT'),
        ('KOMBUCHA', 'KOMBUCHA'),
        ('CHAMPAGNE', 'CHAMPAGNE'),
        ('GAME OF THRONES', 'GAME OF THRONES'),
        ('GILMORE GIRLS', 'GILMORE GIRLS'),
        ('GUCCI', 'GUCCI'),
        ('NIKE', 'NIKE'),
        ('NIGHTCLUB', 'NIGHTCLUB'),
        ('NIGHAT AT HOME', 'NIGHT AT HOME'),
        ('INTUITION', 'INTUITION'),
        ('LOGIC', 'LOGIC'),
        ('BURGER', 'BURGER'),
        ('SALAD', 'SALAD'),
        ('MOUNTAIN CABIN', 'MOUNTAIN CABIN'),
        ('BOUTIQUE HOTEL', 'BOUTIQUE HOTEL'),
        ('SWEET', 'SWEET'),
        ('SALTY', 'SALTY'),
        ('DOG', 'DOG'),
        ('CAT', 'CAT'),
    ]

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\+?\d{9,15}$", message="Phone number must be valid")]
    )
    username = models.CharField(max_length=50, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=100, null=True, blank=True)

    profile_pic = models.ImageField(
        upload_to="profile/",
        default="profile/profile.png",
        null=True,
        blank=True,
        validators=[validate_image],
    )

    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expired = models.DateTimeField(blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    

    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, null=True)
    brings = MultiSelectField(max_length=50, choices=BRINGS_CHOICES, blank=True, null=True)
    that = MultiSelectField(max_length=50, choices=THAT_CHOICES, blank=True, null=True)
    
    professional_field = models.JSONField(default=list, blank=True, null=True)
    interests = models.JSONField(default=list, blank=True, null=True)
    lifestyle = models.JSONField(default=list, blank=True, null=True)
    about = models.TextField(max_length=500, blank=True, null=True)
    hobies = models.JSONField(default=list, blank=True, null=True)
    
    height_feet = models.PositiveSmallIntegerField(default=0)
    height_inches = models.PositiveSmallIntegerField(default=0)
    
    
    dob = models.DateField(blank=True, null=True)
    
    city = models.CharField(max_length=100, blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)
    
    distance = models.PositiveIntegerField(blank=True, null=True)  # in miles/km
    
    
    is_subscribed = models.BooleanField(default=False)
    subscription_expiry = models.DateTimeField(blank=True, null=True)
    
    is_online = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    

    # Required by Django
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"] # Fields required when creating superuser 
    # "username", "phone"
    objects = UserManager()

    def __str__(self):
        return self.username or self.email or self.phone or f"User-{self.pk}"

    def get_full_name(self):
        return self.full_name

    def set_otp(self, otp: str = None, expiry_minutes: int = 30) -> None:
        self.otp = otp or generate_otp()
        self.otp_expired = get_otp_expiry(expiry_minutes)

    def is_otp_valid(self, otp: str) -> bool:
        return self.otp == otp and self.otp_expired and timezone.now() <= self.otp_expired
    
    def height_display(self):
        return f"{self.height_feet}′ {self.height_inches}″"

    def height_in_inches(self):
        return self.height_feet * 12 + self.height_inches
    
    @property
    def profile_link(self):
        base = settings.SITE_BASE_URL.rstrip("/")
        return f"{base}/{self.username}"
    
    
# global feed pop images for user profiles
from django.contrib.auth import get_user_model
User = get_user_model()

class MakeYourProfilePop(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pop_images")
    image = models.ImageField(
        upload_to="user_pop_images/",
        validators=[validate_image],
    )
    image_url = models.URLField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "image")  # optional, prevent duplicates

    def __str__(self):
        return f"PopImage-{self.pk} for User-{self.user.user_id}"

    def save(self, *args, **kwargs):
        # Limit a user to 4 images
        if self.user.pop_images.count() >= 7 and not self.pk:
            raise ValueError("You can upload a maximum of 7 pop-up images.")
        super().save(*args, **kwargs)
        
        
        
class UserLike(models.Model):
    user_from = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes_given"
    )
    user_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_from", "user_to")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_from} liked {self.user_to}"
