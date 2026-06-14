from django.contrib import admin
from .models import ImportBatch, ImportRow, ImportAnomaly, ImportResolution

@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_filename', 'group', 'uploaded_by', 'status', 'uploaded_at', 'approved_at')
    list_filter = ('status', 'uploaded_at', 'group')
    search_fields = ('original_filename', 'uploaded_by__username')

@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'row_number', 'status')
    list_filter = ('status', 'batch__original_filename')
    search_fields = ('batch__original_filename', 'row_number')

@admin.register(ImportAnomaly)
class ImportAnomalyAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'row', 'anomaly_type', 'severity', 'is_resolved')
    list_filter = ('anomaly_type', 'severity', 'is_resolved', 'batch__original_filename')
    search_fields = ('anomaly_type', 'description', 'row__row_number')

@admin.register(ImportResolution)
class ImportResolutionAdmin(admin.ModelAdmin):
    list_display = ('id', 'anomaly', 'resolved_by', 'action_taken', 'resolved_at')
    list_filter = ('action_taken', 'resolved_at')
    search_fields = ('anomaly__anomaly_type', 'resolved_by__username', 'notes')
