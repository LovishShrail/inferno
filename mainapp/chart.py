import pandas as pd
from lightweight_charts import Chart
import tkinter as tk
from tkinter import ttk

# Define CSV file path
CSV_FILE = r"C:\infernoproject\stocktracker\stockproject\mainapp\multi_stock_data.csv"

def load_stock_data(selected_stock):
    """Load stock data for the selected stock symbol and compute SMA."""
    df = pd.read_csv(CSV_FILE, parse_dates=["date"])

    # Filter data for the selected stock symbol
    df = df[df["ticker"] == selected_stock]

    if df.empty:
        raise ValueError(f"No data found for stock: {selected_stock}")

    # Compute 20-day Simple Moving Average (SMA)
    df["sma_20"] = df["close"].rolling(window=20).mean()

    # Rename columns for Lightweight Charts compatibility
    df.rename(columns={"date": "time"}, inplace=True)

    # Prepare SMA data for the chart (Rename "value" to "SMA 20")
    sma = df[["time", "sma_20"]].rename(columns={"sma_20": "SMA 20"}).dropna()

    return df, sma

def update_chart(selected_stock):
    """Update chart based on selected stock symbol."""
    try:
        df, sma = load_stock_data(selected_stock)

        # Clear previous data and update chart
        chart.set(df[["time", "open", "high", "low", "close", "volume"]])

        # Update SMA line with correctly named column
        line.set(sma)

    except ValueError as e:
        print(e)

def on_stock_select(event):
    """Handles stock selection from dropdown."""
    selected_stock = stock_dropdown.get()
    update_chart(selected_stock)

if __name__ == "__main__":
    # Load all stock symbols from the CSV
    df_all = pd.read_csv(CSV_FILE)
    stock_symbols = df_all["ticker"].unique().tolist()

    # Initialize the chart
    chart = Chart()
    line = chart.create_line(name="SMA 20")  # Now the name matches the SMA column

    # Initialize Tkinter GUI for dropdown selection
    root = tk.Tk()
    root.title("Stock Selector")

    ttk.Label(root, text="Select Stock:").pack(pady=5)

    stock_dropdown = ttk.Combobox(root, values=stock_symbols, state="readonly")
    stock_dropdown.pack(pady=5)
    stock_dropdown.set(stock_symbols[0])  # Default selection

    # Bind selection event
    stock_dropdown.bind("<<ComboboxSelected>>", on_stock_select)

    # Start with the first stock
    update_chart(stock_symbols[0])

    # Show the chart in a non-blocking way
    chart.show(block=False)

    # Run the dropdown UI
    root.mainloop()






# import pandas as pd
# import pandas_ta as ta
# import yfinance as yf
# from lightweight_charts import Chart

# if __name__ == '__main__':
    
#     chart = Chart()
#     symbol ="AMD"
#     msft = yf.Ticker(symbol)
#     df = msft.history(period="1y")

#     # prepare indicator values
#     sma = df.ta.sma(length=20).to_frame()
    
#     sma = sma.reset_index()
#     sma = sma.rename(columns={"Date": "time", "SMA_20": "value"})
#     sma = sma.dropna()
    
#     # this library expects lowercase columns for date, open, high, low, close, volume
#     df = df.reset_index()
#     df.columns = df.columns.str.lower()
#     chart.set(df)
 
#     # add sma line
#     line = chart.create_line()    
#     line.set(sma)

#     chart.watermark(symbol)
    
#     chart.show(block=True)
    
    
    
    