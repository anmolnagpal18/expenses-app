from django.urls import path
from .views import ImportUploadView

urlpatterns = [
    path('upload/', ImportUploadView.as_view(), name='import-upload'),
]
