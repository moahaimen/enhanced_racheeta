from rest_framework import serializers

from .models import Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ("id", "slug", "name_ar", "name_en", "parent")
        read_only_fields = fields
