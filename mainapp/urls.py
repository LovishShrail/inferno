from django.contrib import admin
from django.urls import path ,include
from . import views

urlpatterns = [
    
    path('', views.stockPicker ,name='stockpicker'),
    path('stocktracker/', views.stockTracker ,name='stocktracker'),
    path("get_stock_updates/", views.get_stock_updates, name="get_stock_updates")

]