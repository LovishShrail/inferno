from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)  # Default balance

    def __str__(self):
        return f"{self.user.username}'s Profile"

class StockDetail(models.Model):
    stock = models.CharField(max_length=10)
    user = models.ManyToManyField(User)

    def __str__(self):
        return self.stock

class UserStock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.CharField(max_length=10)
    quantity = models.PositiveIntegerField(default=0)
    average_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} - {self.stock} ({self.quantity} shares)"

    @property
    def total_value(self):
        """Calculate the total value of the stock holding."""
        return self.quantity * self.average_price