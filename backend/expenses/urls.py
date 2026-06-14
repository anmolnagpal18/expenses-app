from django.urls import path
from .views import CreateExpenseView, ExpenseDetailView

urlpatterns = [
    path('', CreateExpenseView.as_view(), name='expense-create'),
    path('<uuid:id>/', ExpenseDetailView.as_view(), name='expense-detail'),
]
