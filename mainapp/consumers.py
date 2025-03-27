import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import redis
from urllib.parse import parse_qs

# Connect to Redis
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

class StockConsumer(AsyncWebsocketConsumer):
    """Manages stock selection and periodic updates using Celery Beat."""

    @sync_to_async
    def add_to_celery_beat(self, stockpicker):
        """Updates or creates a Celery Beat task for fetching stock data."""
        from django_celery_beat.models import PeriodicTask, IntervalSchedule

        task = PeriodicTask.objects.filter(name="every-1-seconds").first()

        if task:
            # Reset task args with the newly selected stocks
            task.args = json.dumps([stockpicker])
            task.save()
        else:
            # Create a new periodic task if it doesn't exist
            schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.SECONDS)
            task = PeriodicTask.objects.create(
                interval=schedule,
                name="every-1-seconds",
                task="mainapp.tasks.update_stock",
                args=json.dumps([stockpicker])
            )

        print("Final Celery Task Args:", json.loads(task.args))  # Debugging

    @sync_to_async
    def add_to_stock_detail(self, stockpicker):
        """Adds selected stocks to the StockDetail model for the user."""
        from mainapp.models import StockDetail

        user = self.scope["user"]  # Get the user from WebSocket scope

        # Remove all existing stocks for this user first (reset selection)
        StockDetail.objects.filter(user=user).delete()

        # Add only the newly selected stocks
        for stock in stockpicker:
            stock_obj, _ = StockDetail.objects.get_or_create(stock=stock)
            stock_obj.user.add(user)

        print(f"Updated StockDetail for {user}: {stockpicker}")  # Debugging

    async def connect(self):
        """Handles new WebSocket connections."""
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"stock_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Parse query_string
        query_params = parse_qs(self.scope["query_string"].decode())
        print("Query Params:", query_params)  # Debugging

        stockpicker = query_params.get('stock_picker', [])

        # Ensure stockpicker is a list
        stockpicker = [item for sublist in stockpicker for item in sublist.split(",")]

        print("Final Selected Stocks:", stockpicker)  # Debugging

        # Add stocks to Celery Beat and database
        await self.add_to_celery_beat(stockpicker)
        await self.add_to_stock_detail(stockpicker)

        await self.accept()

    @sync_to_async
    def remove_user_stocks(self):
        """Removes the user's stocks and updates Celery Beat accordingly."""
        from mainapp.models import StockDetail
        from django_celery_beat.models import PeriodicTask

        user = self.scope["user"]
        stocks = StockDetail.objects.filter(user=user)

        # Remove user's stocks from database
        for stock in stocks:
            stock.user.remove(user)
            if stock.user.count() == 0:  # If no users have this stock, delete it
                stock.delete()

        # Update Celery Beat task
        task = PeriodicTask.objects.filter(name="every-1-seconds").first()
        if task:
            existing_stocks = set(json.loads(task.args)[0])  # Convert to set for removal
            updated_stocks = list(existing_stocks - set(stocks.values_list("stock", flat=True)))

            if updated_stocks:
                task.args = json.dumps([updated_stocks])
                task.save()
            else:
                task.delete()  # No stocks left, delete the periodic task

        print(f"Removed stocks for user {user}")

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection."""
        await self.remove_user_stocks()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handles messages from WebSocket clients."""
        text_data_json = json.loads(text_data)
        message = text_data_json.get("message", "")

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "stock_update", "message": message}
        )

    @sync_to_async
    def select_user_stocks(self):
        """Fetches the stocks selected by the user from the database."""
        user = self.scope["user"]
        return list(user.stockdetail_set.values_list("stock", flat=True))

    async def send_stock_update(self, event):
        """Sends stock updates to clients, filtered by the user's selected stocks."""
        message = event["message"]
        user_stocks = await self.select_user_stocks()

        # Fetch data from Redis for the user's selected stocks
        filtered_message = {}
        for stock in user_stocks:
            redis_key = f"candlestick_data:{stock}"
            data = redis_client.get(redis_key)
            if data:
                filtered_message[stock] = json.loads(data)[-1]  # Send only the latest data

        # Send filtered data to frontend
        await self.send(text_data=json.dumps(filtered_message))