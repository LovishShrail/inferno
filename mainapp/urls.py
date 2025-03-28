from django.urls import path
from . import views

urlpatterns = [
    path('', views.land_page, name='land_page'),  
    path('stockPicker/', views.stockPicker, name='stockpicker'),  
    path('register/',views.register,name="register"),
    path('login/',views.login_page,name="login_page"),
    path('logout/',views.logout_page,name="logout_page"),

    path('stocktracker/', views.stockTracker, name='stocktracker'),  
    path('get_stock_updates/', views.get_stock_updates, name='get_stock_updates'),
    path("chart/", views.chart_view, name="chart"),
    path("chart-data/", views.fetch_stock_data, name="chart_data"),
    path('stock_chart_data/<str:stock_symbol>/', views.stock_chart_data, name='stock_chart_data'),
    path('buy_stock/', views.buy_stock, name='buy_stock'),
    path('get_live_prices/', views.get_live_prices, name='get_live_prices'),
    path('sell_stock/', views.sell_stock, name='sell_stock'),
    path('place_order/', views.place_order, name='place_order'),
    path('order_history/', views.order_history, name='order_history'), 
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('order_history_ajax/', views.order_history_ajax, name='order_history_ajax'),
    
   
    
]



