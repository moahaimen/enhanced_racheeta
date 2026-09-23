import django_filters
from django.db.models import Q

from .models import JobPost, JobSeekerProfile
from .types import DEGREE_RANK, Degree, EmploymentType, Profession, ShiftType, WorkMode


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
    language_level = django_filters.CharFilter(method="filter_language_level")
    availability = django_filters.CharFilter(field_name="availability")
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
        return queryset.filter(skills__name_normalized=" ".join(value.lower().split())).distinct()

    def filter_language(self, queryset, name, value):
        return queryset.filter(
            languages__language_normalized=" ".join(value.lower().split())
        ).distinct()

    def filter_language_level(self, queryset, name, value):
        return queryset.filter(languages__level=value.upper()).distinct()

    def filter_employment(self, queryset, name, value):
        return queryset.filter(employment_preferences__contains=[value])
