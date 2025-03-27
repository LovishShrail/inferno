from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
import pandas as pd
from .tasks import update_stock
from asgiref.sync import sync_to_async
import redis
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Sum  # Import Sum for aggregation
from .models import UserProfile, StockDetail ,UserStock,LimitOrder# Import your models
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.db import models 
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from .order_utils import buy_stock, sell_stock  
from django.contrib.auth.models import User




# Path to CSV file
CSV_FILE_PATH = "mainapp\multi_stock_data.csv"

# Load CSV into a DataFrame
df = pd.read_csv(CSV_FILE_PATH)

# Dictionary to store current index for each stock
stock_indices = {ticker: 0 for ticker in df["ticker"].unique()} # output will be {'AAPL': 0, 'GOOGL': 0, 'MSFT': 0, 'AMZN': 0, 'TSLA': 0} , here 0 is the index of the stock

def get_stock_updates(selected_stocks):
    """Fetch stock data from CSV and simulate real-time updates."""
    global stock_indices 
    data = {}

    for ticker in selected_stocks:
        stock_data = df[df["ticker"] == ticker] 
        index = stock_indices.get(ticker, 0)  # .get is used to get the value of the key from the dictionary, if the key does not exist then it will return the default value which is 0 , example stock_indices.get('AAPL',0) will return 0 as AAPL is not present in the dictionary

        # If we reach the end of the dataset, loop back to the beginning
        if index >= len(stock_data):
            index = 0

        row = stock_data.iloc[index]# iloc is used to get the data from the index

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
    stock_picker = df["ticker"].unique().tolist() # unique is used to get the unique values from the column , tolist is used to convert the output to list
    return render(request, "mainapp/stockpicker.html", {"stock_picker": stock_picker})

@sync_to_async
def checkAuthenticated(request):
    return bool(request.user.is_authenticated)

async def stockTracker(request):
    is_loginned = await checkAuthenticated(request)
    if not is_loginned:
        return HttpResponse("Login First")

    """View to fetch initial stock data and trigger Celery updates."""
    selected_stocks = request.GET.getlist("stock_picker") # getlist is used to get the multiple values from the query parameter

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
    data = redis_conn.get(redis_key) # output will be the data stored in the redis key example - '[{"time": "2021-01-01", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0}, ...]'

    if not data:
        return JsonResponse({"error": "No data found"}, status=404)

    df = pd.DataFrame(json.loads(data)) # Convert JSON string to DataFrame , output will be a dataframe with columns time,open,high,low,close
    df["time"] = pd.to_datetime(df["time"]).astype(int) // 10**9

    chart_data = df[["time", "open", "high", "low", "close"]].to_dict(orient="records")
    return JsonResponse(chart_data, safe=False)




# Connect to Redis

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
def place_order(request):
    """Handle placing buy/sell orders (market or limit)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    stock_symbol = request.POST.get("stock_symbol") # get the stock symbol from the post request
    quantity = int(request.POST.get("quantity"))
    order_type = request.POST.get("order_type")  # 'market' or 'limit'
    price = request.POST.get("price")  # Required for limit orders
    action = request.POST.get("action")  # 'buy' or 'sell'

    # Fetch current market price from Redis
    redis_key = f"candlestick_data:{stock_symbol}"
    data = redis_conn.get(redis_key)

    if not data:
        return JsonResponse({"error": "No data found for the selected stock"}, status=404)

    latest_data = json.loads(data)[-1]  # Get the latest candlestick data
    market_price = Decimal(latest_data["close"])  # Use the closing price as the market price

    # Validate sell orders
    if action == "sell":
        # Check if the user owns the stock
        user_stock = UserStock.objects.filter(user=request.user, stock=stock_symbol).first()
        if not user_stock:
            return JsonResponse({"error": "You do not own this stock"}, status=400)

        # Check if the user has enough shares to sell
        if user_stock.quantity < quantity:
            return JsonResponse({"error": "Not enough holding shares"}, status=400)

    if order_type == "market":
        # Execute market order immediately
        if action == "buy":
            result = buy_stock(request.user, stock_symbol, quantity, market_price)
        elif action == "sell":
            result = sell_stock(request.user, stock_symbol, quantity, market_price)
        else:
            return JsonResponse({"error": "Invalid action"}, status=400)

        if "error" in result:
            return JsonResponse({"error": result["error"]}, status=400)

        return JsonResponse({
            "success": True,
            "balance": result["balance"],
            "stock": stock_symbol,
            "quantity": quantity,
            "price": float(result["price"]),  # Market price used for the order
        })
    elif order_type == "limit":
        # Create a limit order
        if not price:
            return JsonResponse({"error": "Price is required for limit orders"}, status=400)

        limit_price = Decimal(price)
        LimitOrder.objects.create( # create a new limit order
            user=request.user,
            stock=stock_symbol,
            quantity=quantity,
            price=limit_price,
            order_type="BUY" if action == "buy" else "SELL",
        )
        return JsonResponse({
            "success": True,
            "message": f"Limit order placed for {quantity} shares of {stock_symbol} at ${limit_price}",
        })
    else:
        return JsonResponse({"error": "Invalid order type"}, status=400)


def get_live_prices(request):
    """Fetch live prices for the user's bought stocks and calculate profit/loss."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    # Fetch user's bought stocks
    user_stocks = UserStock.objects.filter(user=request.user) # wrong : output will be the list of stocks bought by the user , how ? UserStock is a model which has a field user which is a foreign key to the User model , so when we filter the UserStock model with the user=request.user , we get the list of stocks bought by the user
    live_prices = {}

    for stock in user_stocks:
        redis_key = f"candlestick_data:{stock.stock}"
        data = redis_conn.get(redis_key)

        if data:
            latest_data = json.loads(data)[-1]  # Get the latest candlestick data
            current_price = Decimal(latest_data["close"])
            average_price = stock.average_price

            # Calculate profit/loss
            profit_loss = (current_price - average_price) * stock.quantity
            profit_loss_percentage = ((current_price - average_price) / average_price) * 100

            live_prices[stock.stock] = {
                "quantity": stock.quantity,
                "average_price": float(average_price),
                "live_price": latest_data["close"],
                "total_value": float(stock.quantity * latest_data["close"]),
                "profit_loss": float(profit_loss),  # Total profit/loss in currency
                "profit_loss_percentage": float(profit_loss_percentage),  # Profit/loss percentage
            }

    return JsonResponse(live_prices)



def order_history(request):
    """Fetch all orders (market and limit) for the logged-in user."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    # Fetch executed market orders and executed limit orders (from UserStock)
    executed_orders = []
    user_stocks = UserStock.objects.filter(user=request.user)
    for stock in user_stocks:
        executed_orders.append({
            "type": "Limit Order" if stock.order_type == "LIMIT" else "Market Order",
            "stock": stock.stock,
            "quantity": stock.quantity,
            "price": float(stock.average_price),
            "status": "Executed",
            "timestamp": stock.created_at,
        })

    # Fetch pending limit orders (from LimitOrder)
    pending_orders = []
    limit_orders = LimitOrder.objects.filter(user=request.user)
    for order in limit_orders:
        pending_orders.append({
            "type": "Limit Order",
            "stock": order.stock,
            "quantity": order.quantity,
            "price": float(order.price),
            "status": "Pending",
            "timestamp": order.created_at,
        })

    # Combine executed and pending orders
    all_orders = executed_orders + pending_orders

    return render(request, "mainapp/order_history.html", {"orders": all_orders})


def leaderboard(request):
    """Fetch leaderboard data and render the leaderboard page."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    # Fetch all users and calculate their total profit
    users = User.objects.all()
    leaderboard_data = []

    for user in users:
        user_stocks = UserStock.objects.filter(user=user)
        total_profit = Decimal(0)

        for stock in user_stocks:
            redis_key = f"candlestick_data:{stock.stock}"
            data = redis_conn.get(redis_key)

            if data:
                latest_data = json.loads(data)[-1]  # Get the latest candlestick data
                current_price = Decimal(latest_data["close"])
                average_price = stock.average_price
                profit_loss = (current_price - average_price) * stock.quantity
                total_profit += profit_loss

        
        leaderboard_data.append({
            "username": user.username,
            "total_profit": float(total_profit),
        })

    # Sort users by total profit (descending order)
    leaderboard_data.sort(key=lambda x: x["total_profit"], reverse=True)

    # Render the leaderboard template with the data
    return render(request, "mainapp/leaderboard.html", {"leaderboard_data": leaderboard_data})