from django.urls import path
from .views import CreateExpenseView, ExpenseDetailView
from .settlement_views import CreateSettlementView, SettlementDetailView

urlpatterns = [
    path('', CreateExpenseView.as_view(), name='expense-create'),
    path('<uuid:id>/', ExpenseDetailView.as_view(), name='expense-detail'),
]

settlement_urlpatterns = [
    path('', CreateSettlementView.as_view(), name='settlement-create'),
    path('<uuid:id>/', SettlementDetailView.as_view(), name='settlement-detail'),
]
