from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Order, Notification, Table
from django.contrib.sessions.backends.db import SessionStore

@receiver(post_save, sender=Order)
def handle_order_changes(sender, instance, created, **kwargs):
    if created:
        # Notification pour nouvelle commande
        Notification.objects.create(
            order=instance,
            message=f"Nouvelle commande pour la table {instance.table.number}"
        )
    elif instance.status == 'annulee':
        # Notification pour annulation
        notify_table(instance, f"Commande #{instance.id} annulée")

def notify_table(order, message):
    """Crée une notification pour la table concernée"""
    # Notification en base de données
    Notification.objects.create(
        order=order,
        message=message,
        is_seen=False
    )
    
    # Notification via session
    if order.table:
        session = SessionStore()
        session[f'table_{order.table.id}_message'] = message
        session.save()
        order.table.session_key = session.session_key
        order.table.save()

@receiver(pre_delete, sender=Order)
def handle_order_deletion(sender, instance, **kwargs):
    """Gère la suppression depuis l'admin"""
    instance.status = 'annulee'
    instance.save()  # Déclenchera le signal post_save