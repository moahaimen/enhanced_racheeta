import django_filters
from django import forms
from django.db.models import Exists, OuterRef, Q

from .models import JobPost, JobSeekerProfile, LanguageSkill, Skill
from .types import (
    DEGREE_RANK,
    Availability,
    Degree,
    EmploymentType,
    LanguageLevel,
    Profession,
    ShiftType,
    WorkMode,
)


class _UpperChoiceField(forms.ChoiceField):
    """Accepts `advanced` as `ADVANCED`; anything outside the choices is still a 400."""

    def to_python(self, value):
        value = super().to_python(value)
        return value.upper() if value else value


class StrictChoiceFilter(django_filters.ChoiceFilter):
    field_class = _UpperChoiceField


class JobFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    profession = django_filters.ChoiceFilter(choices=Profession.choices)
    specialty = django_filters.CharFilter(field_name="general_specialty__slug")
    detailed_specialty = django_filters.CharFilter(
        field_name="detailed_specialty", lookup_expr="icontains"
    )
    degree = django_filters.ChoiceFilter(field_name="minimum_degree", choices=Degree.choices)
    governorate = django_filters.UUIDFilter(field_name="governorate_id")
    city = django_filters.UUIDFilter(field_name="city_id")
    min_experience = django_filters.NumberFilter(
        field_name="minimum_experience_years", lookup_expr="gte"
    )
    max_experience = django_filters.NumberFilter(
        field_name="minimum_experience_years", lookup_expr="lte"
    )
    employment_type = django_filters.ChoiceFilter(choices=EmploymentType.choices)
    work_mode = django_filters.ChoiceFilter(choices=WorkMode.choices)
    shift_type = django_filters.ChoiceFilter(choices=ShiftType.choices)
    salary_available = django_filters.BooleanFilter(method="filter_salary")
    employer = django_filters.UUIDFilter(field_name="employer_id")

    class Meta:
        model = JobPost
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(detailed_specialty__icontains=value)
            | Q(employer__name__icontains=value)
        )

    def filter_salary(self, queryset, name, value):
        if value:
            return queryset.filter(salary_visible=True).filter(
                Q(salary_min__isnull=False) | Q(salary_max__isnull=False)
            )
        return queryset


class TalentFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    profession = django_filters.ChoiceFilter(choices=Profession.choices)
    specialty = django_filters.CharFilter(field_name="general_specialty__slug")
    detailed_specialty = django_filters.CharFilter(
        field_name="detailed_specialty", lookup_expr="icontains"
    )
    degree = django_filters.ChoiceFilter(
        choices=Degree.choices, method="filter_degree", help_text="Minimum degree"
    )
    min_experience = django_filters.NumberFilter(
        field_name="years_of_experience", lookup_expr="gte"
    )
    max_experience = django_filters.NumberFilter(
        field_name="years_of_experience", lookup_expr="lte"
    )
    governorate = django_filters.UUIDFilter(field_name="governorate_id")
    city = django_filters.UUIDFilter(field_name="city_id")
    skill = django_filters.CharFilter(method="filter_skill")
    language = django_filters.CharFilter(method="filter_language")
    language_level = StrictChoiceFilter(
        choices=LanguageLevel.choices, method="filter_language_level"
    )
    availability = StrictChoiceFilter(choices=Availability.choices)
    employment_type = django_filters.ChoiceFilter(
        choices=EmploymentType.choices, method="filter_employment"
    )

    class Meta:
        model = JobSeekerProfile
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(professional_title__icontains=value)
            | Q(professional_summary__icontains=value)
            | Q(detailed_specialty__icontains=value)
        )

    def filter_degree(self, queryset, name, value):
        rank = DEGREE_RANK.get(value, 0)
        allowed = [d for d, r in DEGREE_RANK.items() if r >= rank]
        return queryset.filter(degree__in=allowed)

    def filter_skill(self, queryset, name, value):
        rows = Skill.objects.filter(
            profile=OuterRef("pk"), name_normalized=" ".join(value.lower().split())
        )
        return queryset.filter(Exists(rows))

    def _language_rows(self):
        """One subquery for `language` and `language_level` so both conditions
        apply to the SAME LanguageSkill row (English BASIC + Arabic ADVANCED
        must not match English ADVANCED). EXISTS also avoids duplicate rows."""
        data = self.form.cleaned_data
        rows = LanguageSkill.objects.filter(profile=OuterRef("pk"))
        if data.get("language"):
            rows = rows.filter(language_normalized=" ".join(data["language"].lower().split()))
        if data.get("language_level"):
            rows = rows.filter(level=data["language_level"])
        return rows

    def filter_language(self, queryset, name, value):
        return queryset.filter(Exists(self._language_rows()))

    def filter_language_level(self, queryset, name, value):
        if self.form.cleaned_data.get("language"):
            return queryset  # already applied together with the language
        return queryset.filter(Exists(self._language_rows()))

    def filter_employment(self, queryset, name, value):
        return queryset.filter(employment_preferences__contains=[value])
