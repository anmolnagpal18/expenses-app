from django.urls import path
from .views import (
    GroupListCreateView,
    GroupDetailView,
    AddMemberView,
    MembershipDetailView,
    GroupBalancesView,
    GroupBalanceExplanationView
)

urlpatterns = [
    path('', GroupListCreateView.as_view(), name='group-list-create'),
    path('<uuid:id>/', GroupDetailView.as_view(), name='group-detail'),
    path('<uuid:id>/members/', AddMemberView.as_view(), name='add-member'),
    path('<uuid:group_id>/members/<uuid:membership_id>/', MembershipDetailView.as_view(), name='membership-detail'),
    path('<uuid:id>/balances/', GroupBalancesView.as_view(), name='group-balances'),
    path('<uuid:id>/balances/explanation/', GroupBalanceExplanationView.as_view(), name='group-balance-explanation'),
]
