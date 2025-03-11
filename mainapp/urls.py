from django.urls import path
from . import views

urlpatterns = [
    path('', views.stockPicker, name='stockpicker'),  
    path('stocktracker/', views.stockTracker, name='stocktracker'),  
    path('get_stock_updates/', views.get_stock_updates, name='get_stock_updates'),
    path("api/stock-chart/<str:stock_symbol>/", views.stock_chart_data, name="stock_chart_data"),
    path('chart/', views.chart_view, name='chart'),
]
