import pandas as pd
import json
import redis
from lightweight_charts import Chart
import tkinter as tk
from tkinter import ttk
import threading
import time

# Connect to Redis
redis_conn = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def fetch_stock_data_from_redis(selected_stock):
    """Fetch standardized data from Redis for the chart."""
    redis_key = f"candlestick_data:{selected_stock}"
    data = redis_conn.get(redis_key)

    if not data:
        raise ValueError(f"No data found for stock: {selected_stock}")

    # Convert JSON data to DataFrame
    df = pd.DataFrame(json.loads(data))

    # Ensure correct column names and data types
    df["time"] = pd.to_datetime(df["time"])
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)

    print("[DEBUG] Cleaned Data for Chart:")
    print(df.head())

    return df

def update_chart(selected_stock):
    """Fetch data from Redis and update the chart."""
    try:
        df = fetch_stock_data_from_redis(selected_stock)

        if df.empty:
            print(f"[WARNING] No valid data for {selected_stock}, chart will not update.")
            return

        print("\n[DEBUG] Updating Chart with Data:\n", df.tail())  # Print last few rows

        # Clear and update chart
        chart.set(df[["time", "open", "high", "low", "close", "volume"]])

    except ValueError as e:
        print("[ERROR]", e)

def on_stock_select(event=None):
    """Handles stock selection from dropdown."""
    selected_stock = stock_dropdown.get()
    update_chart(selected_stock)

def auto_refresh():
    """Automatically refresh chart every 10 seconds."""
    while True:
        time.sleep(10)
        on_stock_select()

if __name__ == "__main__":
    # Fetch available stocks from Redis
    stock_keys = redis_conn.keys("candlestick_data:*")
    stock_symbols = [key.split(":")[-1] for key in stock_keys]

    if not stock_symbols:
        raise ValueError("No stock data found in Redis!")

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

    # Start auto-refresh in background thread
    threading.Thread(target=auto_refresh, daemon=True).start()

    # Show chart (non-blocking)
    chart.show(block=False)

    # Run UI
    root.mainloop()