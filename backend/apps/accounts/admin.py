from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Account


class AccountCreationForm(UserCreationForm):
    class Meta:
        model = Account
        fields = ("email", "full_name")


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = Account
        fields = "__all__"


@admin.register(Account)
class AccountAdmin(DjangoUserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    model = Account

    list_display = ("email", "full_name", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser", "preferred_language")
    search_fields = ("email", "full_name", "phone_number")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Profile", {"fields": ("full_name", "phone_number", "preferred_language")}),
        ("Role & status", {"fields": ("role", "email_verified", "is_active")}),
        (
            "Privileges",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )
