from django.urls import path
from .views import ProductList,ChatView

urlpatterns = [
    path('products/',ProductList.as_view(),  name='home'),
    path('chats/',ChatView.as_view(),  name='ChatView'),
]