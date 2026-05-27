from django.contrib import admin

from .models import Contact, Deal, DealActivity


class DealActivityInline(admin.TabularInline):
    model = DealActivity
    extra = 0
    readonly_fields = ("entry_type", "content", "created_at")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email", "phone")
    search_fields = ("first_name", "last_name", "company", "email")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "stage", "value", "updated_at")
    list_filter = ("stage",)
    search_fields = ("name", "company", "description")
    filter_horizontal = ("contacts",)
    inlines = [DealActivityInline]


@admin.register(DealActivity)
class DealActivityAdmin(admin.ModelAdmin):
    list_display = ("deal", "entry_type", "created_at")
    list_filter = ("entry_type", "created_at")
    search_fields = ("deal__name", "deal__company", "content")
