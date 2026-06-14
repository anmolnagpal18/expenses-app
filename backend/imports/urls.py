from django.urls import path
from .views import (
    ImportUploadView,
    AnomalyDetectView,
    ImportBatchDetailView,
    ResolveAnomalyView,
    CommitBatchView
)

urlpatterns = [
    path('upload/', ImportUploadView.as_view(), name='import-upload'),
    path('<uuid:batch_id>/detect/', AnomalyDetectView.as_view(), name='import-detect'),
    path('batches/<uuid:batch_id>/', ImportBatchDetailView.as_view(), name='import-batch-detail'),
    path('rows/<uuid:row_id>/resolve/', ResolveAnomalyView.as_view(), name='import-row-resolve'),
    path('batches/<uuid:batch_id>/commit/', CommitBatchView.as_view(), name='import-batch-commit'),
]

