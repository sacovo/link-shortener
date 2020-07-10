from django.urls import path
from shortener import views

urlpatterns = [
    path('<slug:slug>/', views.link_detail, name="link-detail"),
    path('', views.index, name="index"),
]
