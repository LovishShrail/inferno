from django.shortcuts import render
from django.http.response import HttpResponse

from django.http import JsonResponse
import pandas as pd
from .tasks import update_stock
from asgiref.sync import sync_to_async

# Path to CSV file
CSV_FILE_PATH = "C:/projects/stocktracker/stockproject/mainapp/generated_stock_data.csv"

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
            "current_price": row["current_price"],
            "previous_close": row["previous_close"],
            "volume": row["volume"],
            "market_cap": row["market_cap"],
            "open_price": row["open_price"],
            "day_high": row["day_high"],
            "day_low": row["day_low"],
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

