from decimal import Decimal
from .models import UserStock, UserProfile

def buy_stock(user, stock_symbol, quantity, price):
    """Handle buying stocks."""
    user_profile = UserProfile.objects.get(user=user)
    total_cost = price * quantity

    if user_profile.balance < total_cost:
        return {"error": "Insufficient balance"}

    # Deduct balance and add stock to user's portfolio
    user_profile.balance -= total_cost
    user_profile.save()

    # Add stock to user's portfolio
    user_stock, created = UserStock.objects.get_or_create(
        user=user,
        stock=stock_symbol,
        defaults={"quantity": quantity, "average_price": price}
    )

    if not created:
        # Update existing stock entry
        total_quantity = user_stock.quantity + quantity
        user_stock.average_price = (
            (user_stock.average_price * user_stock.quantity) + (price * quantity)
        ) / total_quantity
        user_stock.quantity = total_quantity
        user_stock.save()

    return {
        "success": True,
        "balance": float(user_profile.balance),
        "stock": stock_symbol,
        "quantity": quantity,
        "price": float(price),
    }


def sell_stock(user, stock_symbol, quantity, price):
    """Handle selling stocks."""
    user_profile = UserProfile.objects.get(user=user)
    user_stock = UserStock.objects.filter(user=user, stock=stock_symbol).first()

    if not user_stock:
        return {"error": "You do not own this stock"}

    if user_stock.quantity < quantity:
        return {"error": "Insufficient quantity to sell"}

    # Calculate total sale value
    total_sale_value = price * quantity

    # Update user balance
    user_profile.balance += total_sale_value
    user_profile.save()

    # Update or delete the user's stock holding
    if user_stock.quantity == quantity:
        user_stock.delete()  # Delete the stock if all shares are sold
    else:
        user_stock.quantity -= quantity
        user_stock.save()

    return {
        "success": True,
        "balance": float(user_profile.balance),
        "stock": stock_symbol,
        "quantity": quantity,
        "price": float(price),
    }