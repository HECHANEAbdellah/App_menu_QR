from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('menu/<int:table_id>/', views.menu_view, name='menu'),
    path('menu/<int:table_id>/submit_order/', views.submit_order, name='submit_order'),
    path('cuisine/', views.cuisine_interface, name='cuisine_interface'),
    path('cuisine/update/<int:item_id>/', views.update_orderitem_status, name='update_orderitem_status'),
    path('mark-order-ready/<int:order_id>/', views.mark_order_ready, name='mark_order_ready'),
    path('delete-order/<int:order_id>/', views.delete_order, name='delete_order'),
    path('order-status/<int:order_id>/', views.get_order_status, name='order_status'),
    path('update-order-status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('order/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),
    path('serveur/', views.serveur_interface, name='serveur_interface'),
    path('serveur/mark-served/<int:item_id>/', views.mark_item_served, name='mark_item_served'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('get-orders/<int:table_id>/', views.get_orders_for_table, name='get_orders'),
    path('cuisinier/login/', views.cuisinier_login, name='cuisinier_login'),
    path('cuisinier/logout/', views.cuisinier_logout, name='cuisinier_logout'),
    path('serveur/login/', views.serveur_login, name='serveur_login'),
    path('serveur/logout/', views.serveur_logout, name='serveur_logout'),
    path('serveur/accept-order/<int:order_id>/', views.serveur_accept_order, name='serveur_accept_order'),
    path('serveur/mark-all-served/<int:order_id>/', views.serveur_mark_all_served, name='serveur_mark_all_served'),
     path('menu/<int:table_id>/historique/', views.historique_commandes, name='historique_commandes'),   
    path('serveur/order-payment/<int:order_id>/', views.order_payment, name='order_payment'),
    path('update-order-item/<int:order_id>/', views.update_order_item, name='update_order_item'),
]
