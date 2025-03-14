from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
import pandas as pd
from .tasks import update_stock
from asgiref.sync import sync_to_async
import redis
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Sum  # Import Sum for aggregation
from .models import UserProfile, StockDetail ,UserStock# Import your models
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.db import models 
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal






# Path to CSV file
CSV_FILE_PATH = r"C:\infernoproject\stocktracker\stockproject\mainapp\multi_stock_data.csv"

# Load CSV into a DataFrame
df = pd.read_csv(CSV_FILE_PATH)

# Dictionary to store current index for each stock
stock_indices = {ticker: 0 for ticker in df["ticker"].unique()}

def get_stock_updates(selected_stocks):
    """Fetch stock data from CSV and simulate real-time updates."""
    global stock_indices
    data = {}

    for ticker in selected_stocks:
        stock_data = df[df["ticker"] == ticker] 
        index = stock_indices.get(ticker, 0)

        # If we reach the end of the dataset, loop back to the beginning
        if index >= len(stock_data):
            index = 0

        row = stock_data.iloc[index]

        data[ticker] = {
            "time": row["date"],  # Ensure this is a string or timestamp
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        }

        # Move to the next index for the next call
        stock_indices[ticker] = index + 1

    return data

def stockPicker(request):
    """View to display available stocks for selection."""
    stock_picker = df["ticker"].unique().tolist()
    return render(request, "mainapp/stockpicker.html", {"stock_picker": stock_picker})

@sync_to_async
def checkAuthenticated(request):
    return bool(request.user.is_authenticated)

async def stockTracker(request):
    is_loginned = await checkAuthenticated(request)
    if not is_loginned:
        return HttpResponse("Login First")

    """View to fetch initial stock data and trigger Celery updates."""
    selected_stocks = request.GET.getlist("stock_picker")

    if not selected_stocks:
        return JsonResponse({"error": "No stocks selected"}, status=400)

    # Fetch initial stock data to send to frontend
    initial_data = get_stock_updates(selected_stocks)

    # Start Celery task for periodic updates
    update_stock.delay(selected_stocks)

    return render(request, "mainapp/stocktracker.html", {"room_name": "track", "data": initial_data})

redis_conn = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def stock_chart_data(request, stock_symbol):
    """Fetch stock data from Redis and return it in JSON format."""
    redis_key = f"candlestick_data:{stock_symbol}"
    data = redis_conn.get(redis_key)

    if not data:
        return JsonResponse({"error": "No data found"}, status=404)

    df = pd.DataFrame(json.loads(data))
    df["time"] = pd.to_datetime(df["time"]).astype(int) // 10**9

    chart_data = df[["time", "open", "high", "low", "close"]].to_dict(orient="records")
    return JsonResponse(chart_data, safe=False)




# Connect to Redis
redis_conn = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def fetch_stock_data(selected_stock):
    """Fetch latest candlestick data from Redis."""
    redis_key = f"candlestick_data:{selected_stock}"
    data = redis_conn.get(redis_key)

    if not data:
        return JsonResponse({"error": "No data found for stock"}, status=404)

    return JsonResponse(json.loads(data), safe=False)

def chart_view(request):
    """Fetch stocks selected by the logged-in user."""
    if request.user.is_authenticated:
        selected_stocks = StockDetail.objects.filter(user=request.user).values_list("stock", flat=True)
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        balance = user_profile.balance
    else:
        selected_stocks = []  # Empty list if user is not logged in
        balance = 0

    return render(request, "mainapp/chart.html", {
        "available_stocks": selected_stocks,
        "user": request.user,
        "balance": balance
    })




@csrf_exempt
@require_POST
def buy_stock(request):
    """Handle buying stocks for the logged-in user."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    stock_symbol = request.POST.get("stock_symbol")
    quantity = int(request.POST.get("quantity"))
    price = Decimal(request.POST.get("price"))

    # Fetch user profile and check balance
    user_profile = UserProfile.objects.get(user=request.user)
    total_cost = price * quantity

    if user_profile.balance < total_cost:
        return JsonResponse({"error": "Insufficient balance"}, status=400)

    # Deduct balance and add stock to user's portfolio
    user_profile.balance -= total_cost
    user_profile.save()

    # Add stock to user's portfolio (assuming a model called `UserStock` exists)
    user_stock, created = UserStock.objects.get_or_create(
        user=request.user,
        stock=stock_symbol,
        defaults={"quantity": quantity, "average_price": price}
    )

    if not created:
        # Update existing stock entry
        total_quantity = user_stock.quantity + quantity
        user_stock.average_price = (
            (user_stock.average_price * user_stock.quantity) + (price * quantity)
        ) / total_quantity
        user_stock.quantity = total_quantity
        user_stock.save()

    return JsonResponse({
        "success": True,
        "balance": float(user_profile.balance),
        "stock": stock_symbol,
        "quantity": quantity,
        "price": float(price)
    })
    
@property
def total_value(self):
    return self.quantity * self.average_price    