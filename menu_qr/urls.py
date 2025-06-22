from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),         # Accès à l'admin Django
    path('', include('menu.urls')),          # Inclusion des URLs de l'app "menu"
]

# 🔥 Configuration pour servir les fichiers médias en mode développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
