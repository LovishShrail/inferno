from django.urls import path
from . import views

urlpatterns = [
    path('', views.stockPicker, name='stockpicker'),  
    path('stocktracker/', views.stockTracker, name='stocktracker'),  
    path('get_stock_updates/', views.get_stock_updates, name='get_stock_updates'),
    path('api/get_stock_data/', views.get_stock_data, name='get_stock_data'),  # Added trailing slash & name
]
