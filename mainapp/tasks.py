# from celery import shared_task
# import pandas as pd
# import time
# from channels.layers import get_channel_layer
# import asyncio
# import threading

# # Path to CSV file
# CSV_FILE_PATH = "C:/projects/stocktracker/stockproject/mainapp/generated_stock_data.csv"

# # Load CSV into a DataFrame
# df = pd.read_csv(CSV_FILE_PATH)

# # Dictionary to track current index for each stock
# stock_indices = {ticker: 0 for ticker in df["ticker"].unique()}

# # Graceful shutdown flag
# stop_flag = threading.Event()

# def fetch_stock_data_from_csv(selected_stocks):
#     """Fetch stock data from CSV, simulating real-time updates."""
#     global stock_indices
#     data = {}

#     for ticker in selected_stocks:
#         stock_data = df[df["ticker"] == ticker]
#         index = stock_indices.get(ticker, 0)

#         # If we reach the end of the dataset, loop back to the beginning
#         if index >= len(stock_data):
#             index = 0

#         row = stock_data.iloc[index]

#         # Convert NumPy types to native Python types
#         data[ticker] = {
#             "current_price": float(row["current_price"]),
#             "previous_close": float(row["previous_close"]),
#             "volume": int(row["volume"]),
#             "market_cap": float(row["market_cap"]),
#             "open_price": float(row["open_price"]),
#             "day_high": float(row["day_high"]),
#             "day_low": float(row["day_low"]),
#         }

#         # Move to the next index for the next call
#         stock_indices[ticker] = index + 1

#     return data

# @shared_task
# def update_stock(selected_stocks):
#     """Celery task to fetch and broadcast stock data every 10 seconds."""
#     channel_layer = get_channel_layer()
#     loop = asyncio.new_event_loop()  # Create the event loop once
#     asyncio.set_event_loop(loop)

#     try:
#         while not stop_flag.is_set():
#             data = fetch_stock_data_from_csv(selected_stocks)
#             print("Updated Stock Data:",data)  # Debugging log

#             # Send data to WebSockets
#             loop.run_until_complete(channel_layer.group_send("stock_track", {
#                 "type": "send_stock_update",
#                 "message": data,
#             }))

#             time.sleep(10)  # Wait for 10 seconds before fetching again
#     except KeyboardInterrupt:
#         print("Task stopped gracefully.")
#     finally:
#         loop.close()  # Clean up the event loop  




from celery import shared_task
import pandas as pd
import json
import time
from channels.layers import get_channel_layer
import asyncio
from mainapp.models import StockDetail

# Path to CSV file
CSV_FILE_PATH = "C:\infernoproject\stocktracker\stockproject\mainapp\multi_stock_data.csv"
df = pd.read_csv(CSV_FILE_PATH)

# Dictionary to track current index for each stock in the CSV
stock_indices = {ticker: 0 for ticker in df["ticker"].unique()}

def fetch_stock_data_from_csv(selected_stocks):
    """Fetch stock data from CSV, simulating real-time updates."""
    global stock_indices
    data = {}
    for ticker in selected_stocks:
        stock_data = df[df["ticker"] == ticker]
        index = stock_indices.get(ticker, 0)
        if index >= len(stock_data):
            index = 0
        row = stock_data.iloc[index]
        data[ticker] = {
            "current_price": float(row["close"]),
            
            "volume": int(row["volume"]),
            
            "open_price": float(row["open"]),
            "day_high": float(row["high"]),
            "day_low": float(row["low"]),
        }
        stock_indices[ticker] = index + 1
    return data

@shared_task
def update_stock(*args, **kwargs):
    """
    Celery task to fetch and broadcast stock data.
    Instead of reading from a stored argument, it queries the database directly
    for the latest selected stocks from StockDetail.
    """
    # Query the database for the current list of stocks (across all users)
    selected_stocks = list(StockDetail.objects.values_list("stock", flat=True))
    if not selected_stocks:
        print("No stocks selected in the database.")
        return

    # Fetch updated stock data from CSV for these stocks
    data = fetch_stock_data_from_csv(selected_stocks)
    print("Updated Stock Data:", data)

    # Get the channel layer and send the update to the "stock_track" group
    channel_layer = get_channel_layer()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(channel_layer.group_send("stock_track", {
         "type": "send_stock_update",
         "message": data,
    }))
    loop.close()
