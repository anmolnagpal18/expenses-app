from django.contrib import admin
from .models import Group, Membership

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'base_currency', 'created_by', 'created_at')
    search_fields = ('name',)
    list_filter = ('base_currency',)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'user', 'role', 'joined_at', 'left_at', 'is_active')
    list_filter = ('role', 'group')
    search_fields = ('user__email', 'group__name')
