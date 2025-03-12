from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
import pandas as pd
from .tasks import update_stock
from asgiref.sync import sync_to_async
import redis
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Sum  # Import Sum for aggregation
from .models import UserProfile, Order  # Import your models



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



def chart_view(request):
    stocks = Stock.objects.all()  # Fetch all stocks from the database
    return render(request, 'chart.html', {'stocks': stocks})




@login_required
def buy_stock(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        stock = data.get('stock')
        quantity = int(data.get('quantity'))
        price = float(data.get('price'))

        user_profile = get_object_or_404(UserProfile, user=request.user)
        total_cost = quantity * price

        if user_profile.balance >= total_cost:
            # Deduct balance and create order
            user_profile.balance -= total_cost
            user_profile.save()

            Order.objects.create(
                user=request.user,
                stock=stock,
                order_type='BUY',
                quantity=quantity,
                price=price,
            )
            return JsonResponse({"status": "success", "message": "Order placed successfully."})
        else:
            return JsonResponse({"status": "error", "message": "Insufficient balance."}, status=400)

    return JsonResponse({"status": "error", "message": "Invalid request method."}, status=405)

@login_required
def sell_stock(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        stock = data.get('stock')
        quantity = int(data.get('quantity'))
        price = float(data.get('price'))

        user_profile = get_object_or_404(UserProfile, user=request.user)

        # Check if the user has enough stocks to sell
        total_owned = Order.objects.filter(user=request.user, stock=stock, order_type='BUY').aggregate(total=models.Sum('quantity'))['total'] or 0
        total_sold = Order.objects.filter(user=request.user, stock=stock, order_type='SELL').aggregate(total=models.Sum('quantity'))['total'] or 0
        available_quantity = total_owned - total_sold

        if available_quantity >= quantity:
            # Add balance and create order
            user_profile.balance += quantity * price
            user_profile.save()

            Order.objects.create(
                user=request.user,
                stock=stock,
                order_type='SELL',
                quantity=quantity,
                price=price,
            )
            return JsonResponse({"status": "success", "message": "Order placed successfully."})
        else:
            return JsonResponse({"status": "error", "message": "Insufficient stocks to sell."}, status=400)

    return JsonResponse({"status": "error", "message": "Invalid request method."}, status=405)