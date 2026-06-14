from rest_framework import serializers

class ImportUploadSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    file = serializers.FileField()

    def validate_file(self, value):
        # Enforce that the uploaded file is a CSV and is not empty
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV.")
        if value.size == 0:
            raise serializers.ValidationError("File cannot be empty.")
        return value
