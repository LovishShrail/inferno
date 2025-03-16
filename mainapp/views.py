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
def place_order(request):
    """Handle placing buy/sell orders (market or limit)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    stock_symbol = request.POST.get("stock_symbol")
    quantity = int(request.POST.get("quantity"))
    order_type = request.POST.get("order_type")  # 'market' or 'limit'
    price = request.POST.get("price")  # Required for limit orders

    # Fetch current market price from Redis
    redis_key = f"candlestick_data:{stock_symbol}"
    data = redis_conn.get(redis_key)

    if not data:
        return JsonResponse({"error": "No data found for the selected stock"}, status=404)

    latest_data = json.loads(data)[-1]  # Get the latest candlestick data
    market_price = Decimal(latest_data["close"])  # Use the closing price as the market price

    if order_type == "market":
        # Execute market order immediately
        if request.POST.get("action") == "buy":
            result = buy_stock(request.user, stock_symbol, quantity, market_price)
        elif request.POST.get("action") == "sell":
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
        LimitOrder.objects.create(
            user=request.user,
            stock=stock_symbol,
            quantity=quantity,
            price=limit_price,
            order_type="BUY" if request.POST.get("action") == "buy" else "SELL",
        )
        return JsonResponse({
            "success": True,
            "message": f"Limit order placed for {quantity} shares of {stock_symbol} at ${limit_price}",
        })
    else:
        return JsonResponse({"error": "Invalid order type"}, status=400)




def get_live_prices(request):
    """Fetch live prices for the user's bought stocks."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    # Fetch user's bought stocks
    user_stocks = UserStock.objects.filter(user=request.user)
    live_prices = {}

    for stock in user_stocks:
        redis_key = f"candlestick_data:{stock.stock}"
        data = redis_conn.get(redis_key)

        if data:
            latest_data = json.loads(data)[-1]  # Get the latest candlestick data
            live_prices[stock.stock] = {
                "quantity": stock.quantity,
                "live_price": latest_data["close"],
                "total_value": float(stock.quantity * latest_data["close"]),
            }

    return JsonResponse(live_prices)







# @csrf_exempt
# @require_POST
# def buy_stock(request):
#     """Handle buying stocks for the logged-in user."""
#     if not request.user.is_authenticated:
#         return JsonResponse({"error": "User not authenticated"}, status=401)

#     stock_symbol = request.POST.get("stock_symbol")
#     quantity = int(request.POST.get("quantity"))

#     # Fetch current market price from Redis
#     redis_key = f"candlestick_data:{stock_symbol}"
#     data = redis_conn.get(redis_key)

#     if not data:
#         return JsonResponse({"error": "No data found for the selected stock"}, status=404)

#     latest_data = json.loads(data)[-1]  # Get the latest candlestick data
#     market_price = Decimal(latest_data["close"])  # Use the closing price as the market price

#     # Fetch user profile and check balance
#     user_profile = UserProfile.objects.get(user=request.user)
#     total_cost = market_price * quantity

#     if user_profile.balance < total_cost:
#         return JsonResponse({"error": "Insufficient balance"}, status=400)

#     # Deduct balance and add stock to user's portfolio
#     user_profile.balance -= total_cost
#     user_profile.save()

#     # Add stock to user's portfolio
#     user_stock, created = UserStock.objects.get_or_create(
#         user=request.user,
#         stock=stock_symbol,
#         defaults={"quantity": quantity, "average_price": market_price}
#     )

#     if not created:
#         # Update existing stock entry
#         total_quantity = user_stock.quantity + quantity
#         user_stock.average_price = (
#             (user_stock.average_price * user_stock.quantity) + (market_price * quantity)
#         ) / total_quantity
#         user_stock.quantity = total_quantity
#         user_stock.save()

#     return JsonResponse({
#         "success": True,
#         "balance": float(user_profile.balance),
#         "stock": stock_symbol,
#         "quantity": quantity,
#         "price": float(market_price)  # Return the market price used for the purchase
#     })
    
    
    
    
    
    
    
# # @csrf_exempt
# # @require_POST
# # def buy_stock(request):
# #     """Handle buying stocks for the logged-in user."""
# #     if not request.user.is_authenticated:
# #         return JsonResponse({"error": "User not authenticated"}, status=401)

# #     stock_symbol = request.POST.get("stock_symbol")
# #     quantity = int(request.POST.get("quantity"))
# #     price = Decimal(request.POST.get("price"))

# #     # Fetch user profile and check balance
# #     user_profile = UserProfile.objects.get(user=request.user)
# #     total_cost = price * quantity

# #     if user_profile.balance < total_cost:
# #         return JsonResponse({"error": "Insufficient balance"}, status=400)

# #     # Deduct balance and add stock to user's portfolio
# #     user_profile.balance -= total_cost
# #     user_profile.save()

# #     # Add stock to user's portfolio (assuming a model called `UserStock` exists)
# #     user_stock, created = UserStock.objects.get_or_create(
# #         user=request.user,
# #         stock=stock_symbol,
# #         defaults={"quantity": quantity, "average_price": price}
# #     )

# #     if not created:
# #         # Update existing stock entry
# #         total_quantity = user_stock.quantity + quantity
# #         user_stock.average_price = (
# #             (user_stock.average_price * user_stock.quantity) + (price * quantity)
# #         ) / total_quantity
# #         user_stock.quantity = total_quantity
# #         user_stock.save()

# #     return JsonResponse({
# #         "success": True,
# #         "balance": float(user_profile.balance),
# #         "stock": stock_symbol,
# #         "quantity": quantity,
# #         "price": float(price)
# #     })
    
    
    
# @csrf_exempt
# @require_POST
# def sell_stock(request):
#     """Handle selling stocks for the logged-in user."""
#     if not request.user.is_authenticated:
#         return JsonResponse({"error": "User not authenticated"}, status=401)

#     stock_symbol = request.POST.get("stock_symbol")
#     quantity = int(request.POST.get("quantity"))

#     # Fetch current market price from Redis
#     redis_key = f"candlestick_data:{stock_symbol}"
#     data = redis_conn.get(redis_key)

#     if not data:
#         return JsonResponse({"error": "No data found for the selected stock"}, status=404)

#     latest_data = json.loads(data)[-1]  # Get the latest candlestick data
#     market_price = Decimal(latest_data["close"])  # Use the closing price as the market price

#     # Fetch user profile and check if the user owns the stock
#     user_profile = UserProfile.objects.get(user=request.user)
#     user_stock = UserStock.objects.filter(user=request.user, stock=stock_symbol).first()

#     if not user_stock:
#         return JsonResponse({"error": "You do not own this stock"}, status=400)

#     if user_stock.quantity < quantity:
#         return JsonResponse({"error": "Insufficient quantity to sell"}, status=400)

#     # Calculate total sale value
#     total_sale_value = market_price * quantity

#     # Update user balance
#     user_profile.balance += total_sale_value
#     user_profile.save()

#     # Update or delete the user's stock holding
#     if user_stock.quantity == quantity:
#         user_stock.delete()  # Delete the stock if all shares are sold
#     else:
#         user_stock.quantity -= quantity
#         user_stock.save()

#     return JsonResponse({
#         "success": True,
#         "balance": float(user_profile.balance),
#         "stock": stock_symbol,
#         "quantity": quantity,
#         "price": float(market_price)  # Return the market price used for the sale
#     })    
    
    
# # @csrf_exempt
# # @require_POST
# # def sell_stock(request):
# #     """Handle selling stocks for the logged-in user."""
# #     if not request.user.is_authenticated:
# #         return JsonResponse({"error": "User not authenticated"}, status=401)

# #     stock_symbol = request.POST.get("stock_symbol")
# #     quantity = int(request.POST.get("quantity"))
# #     price = Decimal(request.POST.get("price"))

# #     # Fetch user profile and check if the user owns the stock
# #     user_profile = UserProfile.objects.get(user=request.user)
# #     user_stock = UserStock.objects.filter(user=request.user, stock=stock_symbol).first()

# #     if not user_stock:
# #         return JsonResponse({"error": "You do not own this stock"}, status=400)

# #     if user_stock.quantity < quantity:
# #         return JsonResponse({"error": "Insufficient quantity to sell"}, status=400)

# #     # Calculate total sale value
# #     total_sale_value = price * quantity

# #     # Update user balance
# #     user_profile.balance += total_sale_value
# #     user_profile.save()

# #     # Update or delete the user's stock holding
# #     if user_stock.quantity == quantity:
# #         user_stock.delete()  # Delete the stock if all shares are sold
# #     else:
# #         user_stock.quantity -= quantity
# #         user_stock.save()

# #     return JsonResponse({
# #         "success": True,
# #         "balance": float(user_profile.balance),
# #         "stock": stock_symbol,
# #         "quantity": quantity,
# #         "price": float(price)
# #     })    
    
    
    
    







# def login_page(request):
#     if request.method=="POST":
        
#         username=request.POST.get('username')
#         password=request.POST.get('password')
        
#         if not User.objects.filter(username=username).exists():
#             messages.error(request,'invalid username')
#             return redirect('/login/')
         
#         user = authenticate(username=username,password=password) #we suse authenticate method to check the username and password because password is encrypted
#         if user is None:
#             messages.error(request,'invalid password')
#             return redirect('/login/')  
#         else:
#             login(request,user) #login method is used to login the user and store the user in the session
#             return redirect('/receipes/')   
            
#     return render(request,'login.html')  

# def register(request):
#     if request.method=="POST":
#         first_name=request.POST.get('first_name')
#         last_name=request.POST.get('last_name')
#         username=request.POST.get('username')
#         password=request.POST.get('password')
        
#         user =User.objects.filter(username=username)
#         if user.exists():
#             messages.info(request,'Username is already taken') 
#             return redirect('/register/')
#         user = User.objects.create(
#             first_name=first_name,last_name=last_name,username=username)
        
#         #in django we use set_password method to store the password in encrypted form , it does not encrpyt the password by default because it is string     
#         user.set_password(password)
#         user.save()
#         messages.info(request,'account created successfully')
#         return redirect('/register/')       
        
    
#     return render(request,'register.html')


# def logout_page(request):
#     logout(request)
#     return render(request,'logout.html')
    
