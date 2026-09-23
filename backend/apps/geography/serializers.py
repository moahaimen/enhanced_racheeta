from rest_framework import serializers

from .models import City, Country, Governorate


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "code", "name_ar", "name_en")
        read_only_fields = fields


class GovernorateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Governorate
        fields = ("id", "country", "slug", "name_ar", "name_en")
        read_only_fields = fields


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "governorate", "slug", "name_ar", "name_en")
        read_only_fields = fields
