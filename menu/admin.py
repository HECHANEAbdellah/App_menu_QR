from django.contrib import admin
from .models import Order, Notification, Table, Category, MenuItem, OrderItem, Cuisinier, Serveur
from django.utils.html import format_html
from django.urls import path
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Group

admin.site.unregister(Group)

# Désactiver la gestion des commandes et notifications
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'table_number', 'created_at', 'status', 'total_price_display', 'is_paid')
    list_filter = ('status', 'created_at', 'is_paid')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    def total_price_display(self, obj):
        return f"{obj.total_price():.2f} DH"
    total_price_display.short_description = "Total"

    def table_number(self, obj):
        return obj.table.number
    table_number.short_description = "N° Table"

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        orders = Order.objects.filter(status='servie')
        
        recette_jour = sum(o.total_price() for o in orders.filter(created_at__date=today,is_paid=True,status='servie'))
        recette_7j = sum(o.total_price() for o in orders.filter(created_at__date__gte=week_ago,is_paid=True,status='servie'))
        recette_mois = sum(o.total_price() for o in orders.filter(created_at__date__gte=month_ago,is_paid=True,status='servie'))
        extra_context = extra_context or {}
        extra_context['recette_jour'] = recette_jour
        extra_context['recette_7j'] = recette_7j
        extra_context['recette_mois'] = recette_mois
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Exclure les commandes annulées
        return qs.exclude(status='annulee')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('order', 'message', 'is_paid', 'created_at')
    list_filter = ('is_paid', 'created_at')
    # ...le reste du code...

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

# Laisser la gestion complète pour ces modèles :
@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('number', 'qr_code')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price')
    list_filter = ('category',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'item', 'quantity', 'statut')
    list_filter = ('order',)

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Cuisinier)
class CuisinierAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'hire_date', 'last_login', 'is_online')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    autocomplete_fields = ['user']

    def last_login(self, obj):
        return obj.user.last_login

@admin.register(Serveur)
class ServeurAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'hire_date', 'last_login', 'is_online')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    autocomplete_fields = ['user']

    def last_login(self, obj):
        return obj.user.last_login

class RecetteAdminView(admin.ModelAdmin):
    change_list_template = "admin/recette_dashboard.html"

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        orders = Order.objects.filter(status='servie')
        recette_jour = sum(o.total_price() for o in orders.filter(created_at__date=today))
        recette_7j = sum(o.total_price() for o in orders.filter(created_at__date__gte=week_ago))
        recette_mois = sum(o.total_price() for o in orders.filter(created_at__date__gte=month_ago))

        extra_context = extra_context or {}
        extra_context['recette_jour'] = recette_jour
        extra_context['recette_7j'] = recette_7j
        extra_context['recette_mois'] = recette_mois
        return super().changelist_view(request, extra_context=extra_context)

# Ajoute ce dashboard à l'admin (optionnel, ou tu peux juste afficher dans OrderAdmin)