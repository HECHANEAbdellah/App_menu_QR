from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Table, MenuItem, Order, OrderItem, Category, Notification
import json
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Prefetch
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.core import serializers
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from functools import wraps
from collections import defaultdict
from django.contrib.sessions.backends.db import SessionStore

def cuisinier_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not hasattr(request.user, 'cuisinier_profile'):
            return redirect('cuisinier_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def serveur_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not hasattr(request.user, 'serveur_profile'):
            return redirect('serveur_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def get_orders_for_table(request, table_id):
    try:
        table = Table.objects.get(pk=table_id)
        # Exclure les commandes payées
        orders = Order.objects.filter(table=table, is_paid=False) \
            .exclude(status='annulee') \
            .exclude(status='servie', updated_at__gte=timezone.now()-timezone.timedelta(minutes=3)) \
            .order_by('-created_at')
        orders_data = []
        for order in orders:
            order_data = {
                'id': order.id,
                'created_at': order.created_at.strftime("%d/%m/%Y %H:%M"),
                'status': order.status,
                'total_price': float(order.total_price()),
                'items': []
            }
            for item in order.items.all():
                order_data['items'].append({
                    'name': item.item.name,
                    'quantity': item.quantity,
                    'price': float(item.item.price)
                })
            orders_data.append(order_data)
        return JsonResponse({'orders': orders_data})
    except Table.DoesNotExist:
        return JsonResponse({'error': 'Table introuvable'}, status=404)

def interface_menu(request):
    message = request.session.pop('message_annulation', None)
    orders = Order.objects.filter(...)  # ta logique ici
    return render(request, 'interface_menu.html', {'orders': orders, 'message_annulation': message})

@require_POST
@csrf_exempt  # à retirer si tu gères bien le CSRF côté JS
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status == 'en_attente_serveur':
        order.status = 'annulee'
        order.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': "Impossible d'annuler cette commande."})

def is_serveur(user):
    return hasattr(user, 'serveur_profile')

@serveur_required
@user_passes_test(is_serveur)
def serveur_interface(request):
    pending_orders = Order.objects.filter(status='en_attente_serveur').exclude(status='annulee').order_by('-created_at')
    items_prets = OrderItem.objects.filter(statut='prete') \
        .select_related('order__table', 'item') \
        .order_by('order__table__number')
    orders_items = defaultdict(list)
    for item in items_prets:
        orders_items[item.order].append(item)
    orders_items = {order: items for order, items in orders_items.items() if items}
    orders_to_pay = Order.objects.filter(status__in=['prete', 'servie'], is_paid=False)
    return render(request, 'serveur/interface.html', {
        'orders_items': orders_items,
        'pending_orders': pending_orders,
        'orders_to_pay': orders_to_pay,
    })

@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    new_status = request.POST.get('status')
    allowed = False
    # Autoriser seulement les transitions valides pour la cuisine
    if order.status == 'nouvelle' and new_status in ['preparation', 'prete']:
        allowed = True
    elif order.status == 'preparation' and new_status == 'prete':
        allowed = True
    if allowed:
        order.status = new_status
        order.save()
        order.items.update(statut=new_status)
        if new_status == 'prete':
            Notification.objects.create(
                order=order,
                message=f"La commande {order.id} pour la table {order.table.number} est prête à être servie.",
                is_seen=False
            )
    return redirect('cuisine_interface')

@require_POST
def mark_item_served(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id)
    item.statut = 'servie'
    item.save()
    order = item.order
    if all(i.statut == 'servie' for i in order.items.all()):
        order.status = 'servie'
        order.save()
    return redirect('serveur_interface')

@require_POST
@serveur_required
def serveur_mark_all_served(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    order.items.filter(statut='prete').update(statut='servie')
    if all(item.statut == 'servie' for item in order.items.all()):
        order.status = 'servie'
        order.save()
        Notification.objects.create(
            order=order,
            message=f"La commande {order.id} pour la table {order.table.number} a été entièrement servie.",
            is_seen=False
        )
    return redirect('serveur_interface')

@require_GET
def get_order_status(request, order_id):
    try:
        order = Order.objects.get(pk=order_id)
        return JsonResponse({'status': order.status})
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Commande introuvable'}, status=404)

@require_POST
def delete_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    table = order.table
    session = SessionStore()
    session[f'table_{table.id}_message'] = f"Commande #{order.id} annulée par le restaurant"
    session.save()
    table.session_key = session.session_key
    table.save()
    order.items.all().delete()
    order.delete()
    messages.success(request, f"Commande #{order.id} annulée avec succès")
    return redirect('cuisine_interface')

@require_POST
def mark_order_ready(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if order.status != 'prete':
        order.items.filter(statut__in=['nouvelle', 'preparation']).update(statut='prete')
        order.status = 'prete'
        order.save()
        Notification.objects.create(
            order=order,
            message=f"La commande {order.id} pour la table {order.table.number} est prête à être servie.",
            is_seen=False
        )
    return redirect('cuisine_interface')

def is_cuisinier(user):
    return hasattr(user, 'cuisinier_profile')

def cuisinier_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Mettre à jour is_online
            if hasattr(user, 'cuisinier_profile'):
                user.cuisinier_profile.is_online = True
                user.cuisinier_profile.save()
            return redirect('cuisine_interface')
        else:
            return render(request, 'menu/cuisinier_login.html', {'error': "Identifiants invalides ou accès refusé."})
    return render(request, 'menu/cuisinier_login.html')

def cuisinier_logout(request):
    if request.user.is_authenticated and hasattr(request.user, 'cuisinier_profile'):
        request.user.cuisinier_profile.is_online = False
        request.user.cuisinier_profile.save()
    logout(request)
    return redirect('cuisinier_login')

@cuisinier_required
@user_passes_test(is_cuisinier)
def cuisine_interface(request):
    # جلب الطلبات اللي مازالين خدامين
    orders = Order.objects.exclude(status__in=['annulee', 'en_attente_serveur', 'servie']) \
        .prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('item'))
        ).order_by('-created_at')

    for order in orders:
        # ترتيب الأطباق: nouvelle > preparation > prete > servie
        order.sorted_items = sorted(
            order.items.all(),
            key=lambda x: (
                0 if x.statut == 'nouvelle' else
                1 if x.statut == 'preparation' else
                2 if x.statut == 'prete' else
                3
            )
        )
        # تحديث حالة الطلب إذا كلشي الأطباق فحالة وحدة
        item_statuses = list(order.items.values_list('statut', flat=True))
        if item_statuses and all(s == item_statuses[0] for s in item_statuses):
            order.status = item_statuses[0]
            order.save()

    return render(request, 'menu/cuisine.html', {
        'orders': orders,
        'now': timezone.now()
    })

@csrf_exempt
def update_orderitem_status(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(OrderItem, pk=item_id)
        new_status = request.POST.get('statut')
        allowed = False
        # فقط الانتقالات المنطقية
        if item.statut == 'nouvelle' and new_status in ['preparation', 'prete']:
            allowed = True
        elif item.statut == 'preparation' and new_status == 'prete':
            allowed = True
        if allowed:
            item.statut = new_status
            item.save()
            # هنا المنطق: إذا كلشي items عندهم نفس الحالة، الطلب ياخذ نفس الحالة
            order = item.order
            item_statuses = list(order.items.values_list('statut', flat=True))
            if all(s == item_statuses[0] for s in item_statuses):
                order.status = item_statuses[0]
                order.save()
        return redirect('cuisine_interface')
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

def menu_view(request, table_id):
    table = get_object_or_404(Table, pk=table_id)
    search_query = request.GET.get('search', '').strip()
    menu_items_query = MenuItem.objects.all()
    categories_query = Category.objects.all()
    if search_query:
        menu_items_query = menu_items_query.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        categories_query = categories_query.filter(
            Q(name__icontains=search_query) |
            Q(menuitem__name__icontains=search_query)
        ).distinct()
    categories = categories_query.prefetch_related(
        Prefetch('menuitem_set', queryset=menu_items_query)
    )
    order = Order.objects.filter(
        table=table
    ).exclude(status='annulee').order_by('-created_at').first()
    notification_message = None
    if table.session_key:
        try:
            session = SessionStore(session_key=table.session_key)
            notification_message = session.get(f'table_{table.id}_message')
            if notification_message:
                del session[f'table_{table.id}_message']
                session.save()
                table.session_key = None
                table.save()
        except Exception as e:
            pass
    return render(request, 'menu/menu.html', {
        'table': table,
        'categories': categories,
        'order': order,
        'notification_message': notification_message,
        'search_query': search_query
    })

def submit_order(request, table_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            table = Table.objects.get(pk=table_id)
            order = Order.objects.create(table=table, status='en_attente_serveur')
            for item_data in items:
                item = MenuItem.objects.get(pk=item_data['id'])
                quantity = item_data.get('quantity', 1)
                OrderItem.objects.create(order=order, item=item, quantity=quantity)
            Notification.objects.create(
                order=order,
                message=f"La commande {order.id} a été soumise et attend la validation du serveur.",
                is_seen=False
            )
            return JsonResponse({'status': 'success', 'order_id': order.id})
        except Exception as e:
            return JsonResponse({'error': f"Erreur lors de la soumission de la commande: {str(e)}"}, status=400)
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

def serveur_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Mettre à jour is_online
            if hasattr(user, 'serveur_profile'):
                user.serveur_profile.is_online = True
                user.serveur_profile.save()
            return redirect('serveur_interface')
        else:
            return render(request, 'menu/serveur_login.html', {'error': "Identifiants invalides ou accès refusé."})
    return render(request, 'menu/serveur_login.html')

def serveur_logout(request):
    if request.user.is_authenticated and hasattr(request.user, 'serveur_profile'):
        request.user.serveur_profile.is_online = False
        request.user.serveur_profile.save()
    logout(request)
    return redirect('serveur_login')

@require_POST
@login_required
@user_passes_test(is_serveur)
def serveur_accept_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if order.status == 'en_attente_serveur':
        order.status = 'nouvelle'
        order.save()
        Notification.objects.create(
            order=order,
            message=f"Commande {order.id} acceptée par le serveur.",
            is_seen=False
        )
    return redirect('serveur_interface')

@require_POST
@serveur_required
def order_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    order.is_paid = True
    order.save()
    return redirect('serveur_interface')

def accueil(request):
    return render(request, 'menu/accueil.html')

from django.shortcuts import render, get_object_or_404
from .models import Table, Order

def historique_commandes(request, table_id):
    table = get_object_or_404(Table, id=table_id)
    orders = Order.objects.filter(table=table).order_by('-created_at')
    return render(request, 'menu/historique.html', {'orders': orders, 'table': table})

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Order, OrderItem

@csrf_exempt
def update_order_item(request, order_id):
    import json
    if request.method == "POST":
        data = json.loads(request.body)
        order_item_id = data.get('item_id')  # <-- id de OrderItem !
        action = data.get('action')
        try:
            order = Order.objects.get(id=order_id, status='en_attente_serveur')
            order_item = OrderItem.objects.get(id=order_item_id, order=order)
            if action == 'increase':
                order_item.quantity += 1
                order_item.save()
            elif action == 'decrease':
                if order_item.quantity > 1:
                    order_item.quantity -= 1
                    order_item.save()
                else:
                    order_item.delete()
            elif action == 'remove':
                order_item.delete()
            else:
                return JsonResponse({'success': False, 'message': 'Action inconnue'})
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})