# from django.db import models
# from django.contrib.auth.models import User

# class StockDetail(models.Model):
#     stock = models.CharField(max_length=255,unique=True)
#     user = models.ManyToManyField(User)
    

# class UserProfile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     balance = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)  # Initial balance

#     def __str__(self):
#         return f"{self.user.username}'s Profile"
    
    
    
    
# class Order(models.Model):
#     ORDER_TYPES = [
#         ('BUY', 'Buy'),
#         ('SELL', 'Sell'),
#     ]

#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     stock = models.CharField(max_length=10)  # Stock symbol (e.g., AAPL)
#     order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
#     quantity = models.PositiveIntegerField()
#     price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at which the order was executed
#     timestamp = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user.username} - {self.order_type} {self.quantity} {self.stock} at {self.price}"






from django.db import models
from django.contrib.auth.models import User

class StockDetail(models.Model):
    stock = models.CharField(max_length=255, unique=True)
    user = models.ManyToManyField(User)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)  # Initial balance

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Order(models.Model):
    ORDER_TYPES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.CharField(max_length=10)  # Stock symbol (e.g., AAPL)
    order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at which the order was executed
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.order_type} {self.quantity} {self.stock} at {self.price}"