import pandas as pd
import json
import redis
import asyncio
import websockets
from lightweight_charts import Chart
import tkinter as tk
from tkinter import ttk

# Connect to Redis
redis_conn = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# WebSocket URL template
WS_URL_TEMPLATE = "ws://localhost:8000/ws/stock/{room_name}/"

async def send_to_websocket(data, selected_stock):
    """Send stock data updates to WebSocket."""
    ws_url = WS_URL_TEMPLATE.format(room_name=selected_stock)
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps({"action": "update_chart", "data": data}))
        print(f"[DEBUG] Sent data for {selected_stock} to WebSocket")

def fetch_stock_data_from_redis(selected_stock):
    """Fetch latest stock data from Redis."""
    redis_key = f"candlestick_data:{selected_stock}"
    data = redis_conn.get(redis_key)

    if not data:
        print(f"[WARNING] No data found for stock: {selected_stock}")
        return pd.DataFrame()  # Empty DataFrame

    df = pd.DataFrame(json.loads(data))

    # Convert timestamps if necessary
    if isinstance(df["time"].iloc[0], str):
        df["time"] = pd.to_datetime(df["time"])
    else:
        df["time"] = pd.to_datetime(df["time"], unit="s")

    df = df.sort_values("time")

    print(f"\n[DEBUG] {selected_stock} Data for Chart:\n", df.tail())
    return df

def update_chart(selected_stock):
    """Fetch data from Redis and update the chart."""
    try:
        df = fetch_stock_data_from_redis(selected_stock)

        if df.empty:
            print(f"[WARNING] No valid data for {selected_stock}, chart will not update.")
            return

        # Update chart
        chart.set(df[["time", "open", "high", "low", "close", "volume"]])

        # Send data to WebSocket (Non-blocking)
        asyncio.create_task(send_to_websocket(df.to_dict(orient="records"), selected_stock))

    except Exception as e:
        print("[ERROR] Failed to update chart:", e)

def on_stock_select(event=None):
    """Handles stock selection from dropdown."""
    selected_stock = stock_dropdown.get()
    update_chart(selected_stock)

def periodic_update():
    """Refresh chart every 10 seconds."""
    on_stock_select()
    root.after(10000, periodic_update)  # Schedule next update

if __name__ == "__main__":
    # Fetch available stocks from Redis
    stock_keys = redis_conn.keys("candlestick_data:*")
    stock_symbols = [key.split(":")[-1] for key in stock_keys]

    if not stock_symbols:
        print("[ERROR] No stock data found in Redis! Using default stocks.")
        stock_symbols = ["AAPL", "GOOGL"]  # Default stocks if Redis is empty

    # Initialize chart
    chart = Chart()

    # Initialize Tkinter UI
    root = tk.Tk()
    root.title("Stock Selector")

    ttk.Label(root, text="Select Stock:").pack(pady=5)

    stock_dropdown = ttk.Combobox(root, values=stock_symbols, state="readonly")
    stock_dropdown.pack(pady=5)
    stock_dropdown.set(stock_symbols[0])

    # Bind dropdown event
    stock_dropdown.bind("<<ComboboxSelected>>", on_stock_select)

    # Start with first stock
    update_chart(stock_symbols[0])

    # Start periodic auto-refresh
    root.after(10000, periodic_update)  

    # Show chart (non-blocking)
    chart.show(block=False)

    # Run UI
    root.mainloop()
