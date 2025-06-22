from .models import Notification

def notification_context(request):
    return {
        'notifications': Notification.objects.filter(is_paid=False)
    }
