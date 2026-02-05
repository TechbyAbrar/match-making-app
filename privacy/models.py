
from django.db import models

class BaseContent(models.Model):
    description = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.description[:50]  # Return first 50 characters of description

class PrivacyPolicy(BaseContent):
    pass

class AboutUs(BaseContent):
    pass

class TermsConditions(BaseContent):
    pass



class SubmitQuerry(models.Model):
    name = models.CharField(max_length=155, null=True, blank=True)
    email = models.EmailField()
    message = models.TextField(max_length=500, null=True, blank=True)
    
    created_at = models.DateField(auto_now_add=True)
    
    

from django.contrib.auth import get_user_model
User = get_user_model()

class ShareThoughts(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    thoughts = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.thoughts[:30]}"
    
    
    
    