from django.urls import path
from .views import ImportUploadView, AnomalyDetectView

urlpatterns = [
    path('upload/', ImportUploadView.as_view(), name='import-upload'),
    path('<uuid:batch_id>/detect/', AnomalyDetectView.as_view(), name='import-detect'),
]
