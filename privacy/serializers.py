from rest_framework import serializers
from .models import PrivacyPolicy, AboutUs, TermsConditions, SubmitQuerry, ShareThoughts

class BaseContentSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'description', 'last_updated']
        read_only_fields = ['id', 'last_updated']

class PrivacyPolicySerializer(BaseContentSerializer):
    class Meta(BaseContentSerializer.Meta):
        model = PrivacyPolicy

class AboutUsSerializer(BaseContentSerializer):
    class Meta(BaseContentSerializer.Meta):
        model = AboutUs

class TermsConditionsSerializer(BaseContentSerializer):
    class Meta(BaseContentSerializer.Meta):
        model = TermsConditions 


class SubmitQuerrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmitQuerry
        fields = ['id', 'name', 'email', 'message']
        

class ShareThoughtsSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)  # show username instead of id

    class Meta:
        model = ShareThoughts
        fields = ['id', 'user', 'thoughts', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']