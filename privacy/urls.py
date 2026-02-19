from django.urls import path
from .views import (
    PrivacyPolicyView,
    AboutUsView,
    TermsConditionsView, SubmitQuerryView, SubmitQuerryDetailView, ShareThoughtsView
)

urlpatterns = [
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy-policy'),
    path('about-us/', AboutUsView.as_view(), name='aboutus'),
    path('terms-conditions/', TermsConditionsView.as_view(), name='terms-conditions'),
    
    #querry submission
    path('submit/querry/', SubmitQuerryView.as_view(), name='submit-querry'),
    path("submit/querry/<int:pk>/", SubmitQuerryDetailView.as_view(), name="single-submit-query"),
    
    #thoughts
    path('thoughts/', ShareThoughtsView.as_view(), name='share-thoughts'),
]   