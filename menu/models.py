from django.db import models
import qrcode
from io import BytesIO
from django.core.files import File
from django.contrib.postgres.fields import JSONField
from django.conf import settings
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class Notification(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_paid = models.BooleanField(default=False)
    is_seen = models.BooleanField(default=False)  # Nouveau champ
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.message

class Table(models.Model):
    number = models.PositiveIntegerField(unique=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    session_key = models.CharField(max_length=40, blank=True, null=True) 

    def save(self, *args, **kwargs):
        # Vérifie si l'objet n'a pas encore été enregistré (donc pas de PK)
        if not self.pk:
            super().save(*args, **kwargs)  # Sauvegarde initiale pour obtenir une PK

        # Maintenant self.pk est disponible, on peut créer le QR
        qr_data = f"{settings.SITE_URL}/menu/{self.pk}/"
        qr = qrcode.make(qr_data)
        fname = f'qr-{self.number}.png'
        buffer = BytesIO()
        qr.save(buffer, 'PNG')
        self.qr_code.save(fname, File(buffer), save=False)

        # Sauvegarde finale avec le QR
        super().save(*args, **kwargs)

# Puis Category
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# Puis MenuItem
class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    translations = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.name

# Ensuite Order
class Order(models.Model):
    STATUS_CHOICES = [
        ('en_attente_serveur', 'En attente serveur'),
        ('nouvelle', 'Nouvelle'),
        ('preparation', 'En préparation'),
        ('prete', 'Prête'),
        ('servie', 'Servie'),
        ('annulee', 'Annulée'),
    ]

    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='en_attente_serveur',
    )
    is_paid = models.BooleanField(default=False)
    prix_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # <-- Ajout du champ

    def __str__(self):
        return f"Commande {self.id} - Table {self.table.number}"
    
    def total_price(self):
        return sum(item.item.price * item.quantity for item in self.items.all())
   
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "Statut inconnu")
    
    def update_prix_total(self):
        self.prix_total = sum(item.item.price * item.quantity for item in self.items.all())
        self.save(update_fields=['prix_total'])
    
    def get_total(self):
        return sum(item.item.price * item.quantity for item in self.items.all())

# Et OrderItem
# models.py
class OrderItem(models.Model):
    STATUT_CHOICES = [
        ('nouvelle', 'Nouvelle'),
        ('preparation', 'En préparation'),
        ('prete', 'Prête'),
        ('servie', 'Servie'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='nouvelle')  # 🔥 nouveau champ
    
    def cancel(self, cancelled_by='system', reason=''):
        """Annule la commande proprement"""
        self.status = 'annulee'
        self.save()
        
        Notification.objects.create(
            order=self,
            message=f"Commande #{self.id} annulée ({cancelled_by}: {reason})"
        )
        
        if self.table:
            session = SessionStore()
            session[f'table_{self.table.id}_message'] = f"Votre commande #{self.id} a été annulée"
            session.save()
            self.table.session_key = session.session_key
            self.table.save()
    def delete(self, *args, **kwargs):
        """Override delete pour mettre à jour le statut avant suppression"""
        self.status = 'annulee'
        self.save()
        
        # Créer une notification
        Notification.objects.create(
            order=self,
            message=f"Commande #{self.id} annulée par l'administration"
        )
        
        # Appeler la suppression normale
        super().delete(*args, **kwargs)
    def __str__(self):
        return f"{self.quantity} x {self.item.name}"

class Cuisinier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cuisinier_profile')
    phone = models.CharField(max_length=20, blank=True)
    hire_date = models.DateField(blank=True, null=True)
    is_online = models.BooleanField(default=False)  # Nouveau champ

    def __str__(self):
        return self.user.username

class Serveur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='serveur_profile')
    phone = models.CharField(max_length=20, blank=True)
    hire_date = models.DateField(blank=True, null=True)
    is_online = models.BooleanField(default=False)  # Nouveau champ

    def __str__(self):
        return self.user.username

@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def update_order_prix_total(sender, instance, **kwargs):
    instance.order.update_prix_total()
