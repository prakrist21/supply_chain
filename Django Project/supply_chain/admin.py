from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Council, Contractor, Bid, Project, Package, Activity, Team
from .forms import CouncilAdminForm


class CouncilAdmin(admin.ModelAdmin):
    form = CouncilAdminForm
    list_display = ('name', 'get_username', 'contact', 'contact_email', 'slug', 'created_at')
    search_fields = ('name', 'contact', 'contact_email')
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('User Account', {
            'fields': ('username', 'email', 'password'),
            'description': 'Login credentials for this council'
        }),
        ('Council Information', {
            'fields': ('name', 'contact', 'contact_email', 'slug')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_username(self, obj):
        try:
            return obj.user.username
        except:
            return "NO USER!"

    get_username.short_description = 'Username'


admin.site.register(Council, CouncilAdmin)

class ContractorAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_username', 'contact', 'contact_email', 'role', 'experience', 'bid_count', 'slug','created_at')
    search_fields = ('name', 'contact', 'contact_email', 'role')
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ('role', 'experience')
    readonly_fields = ('created_at', 'updated_at')

    def get_username(self, obj):
        try:
            return obj.user.username
        except:
            return "NO USER!"

    get_username.short_description = 'Username'

    def bid_count(self, obj):
        return obj.bids.count()

    bid_count.short_description = 'Total Bids'

admin.site.register(Contractor, ContractorAdmin)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'council', 'budget', 'status', 'start_date', 'end_date', 'package_count', 'created_at')
    list_filter = ('council', 'status', 'start_date')
    search_fields = ('title', 'description', 'council__name')
    readonly_fields = ('created_at', 'updated_at')
    def package_count(self, obj):
        return obj.package_set.count()

    package_count.short_description = 'Packages'
admin.site.register(Project, ProjectAdmin)

class PackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'budget', 'bid_count', 'has_approved', 'created_at')
    list_filter = ('project', 'project__council', 'created_at')
    search_fields = ('title', 'description', 'project__title')
    readonly_fields = ('created_at', 'updated_at')

    def bid_count(self, obj):
        return obj.bids.count()

    bid_count.short_description = 'Total Bids'

    def has_approved(self, obj):
        return obj.has_approved_bid()
    has_approved.boolean = True
    has_approved.short_description = 'Awarded'

admin.site.register(Package, PackageAdmin)

class BidAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'contractor', 'council', 'package', 'status', 'amount', 'date','has_documents')
    list_filter = ('status', 'council', 'date', 'project')
    search_fields = ('project__title', 'contractor__name', 'council__name')
    readonly_fields = ('date', 'created_at', 'updated_at')

    def has_documents(self, obj):
        count = sum([bool(obj.document1), bool(obj.document2), bool(obj.document3)])
        return f"{count}/3"

    has_documents.short_description = 'Documents'

admin.site.register(Bid, BidAdmin)

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')

    def get_role(self, obj):
        if obj.is_superuser:
            return 'Superuser'
        elif obj.is_staff:
            return 'Admin'
        elif hasattr(obj, 'contractor'):
            return 'Contractor'
        elif hasattr(obj, 'council'):
            return 'Council'
        return 'No Role'

    get_role.short_description = 'Role'

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'message', 'project', 'package', 'bid', 'is_read', 'created_at')
    list_filter = ('activity_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message', 'activity_type')
    readonly_fields = ('created_at',)
    list_per_page = 20

admin.site.register(Activity, ActivityAdmin)

class TeamAdmin(admin.ModelAdmin):
    list_display = ('project', 'name', 'created_at', 'member_count', 'contractor_count')
    search_fields = ('name', 'project__title')
    readonly_fields = ('created_at', 'updated_at')

    def member_count(self, obj):
        return obj.member_count()

    member_count.short_description = 'Members'

    def contractor_count(self, obj):
        return obj.contractor_count()

    contractor_count.short_description = 'Contractors'

admin.site.register(Team, TeamAdmin)