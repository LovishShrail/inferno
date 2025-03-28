from decimal import Decimal
from .models import UserStock, UserProfile

def buy_stock(user, stock_symbol, quantity, price, order_type='MARKET'):
    """Handle buying stocks."""
    user_profile = UserProfile.objects.get(user=user)
    total_cost = price * quantity

    if user_profile.balance < total_cost:
        return {"error": "Insufficient balance"}

    # Deduct balance and add stock to user's portfolio
    user_profile.balance -= total_cost
    user_profile.save() # Save the updated balance

    # Add stock to user's portfolio
    #get_or_create is used to get the object if it exists or create a new object if it does not exist
    user_stock, created = UserStock.objects.get_or_create(
        user=user,
        stock=stock_symbol,
        defaults={"quantity": quantity, "average_price": price, "order_type": order_type} # default values for the fields if the object is created
    )

    if not created:
        # Update existing stock entry
        total_quantity = user_stock.quantity + quantity
        user_stock.average_price = (
            (user_stock.average_price * user_stock.quantity) + (price * quantity)
        ) / total_quantity
        user_stock.quantity = total_quantity
        user_stock.order_type = order_type  # Update order type
        user_stock.save()

    return {
        "success": True,
        "balance": float(user_profile.balance),
        "stock": stock_symbol,
        "quantity": quantity,
        "price": float(price),
    }


def sell_stock(user, stock_symbol, quantity, price, order_type='MARKET'):
    """Handle selling stocks with accurate profit tracking"""
    try:
        user_profile = UserProfile.objects.get(user=user)
        user_stock = UserStock.objects.get(user=user, stock=stock_symbol)
        
        if user_stock.quantity < quantity:
            return {"error": "Insufficient quantity to sell"}
        
        # Calculate exact profit for this sale
        sale_profit = (Decimal(str(price)) - user_stock.average_price) * Decimal(str(quantity))
        
        # Update cumulative profit BEFORE modifying balance
        user_profile.cumulative_profit += sale_profit
        user_profile.balance += Decimal(str(price)) * Decimal(str(quantity))
        user_profile.save()

        # Update stock holdings
        if user_stock.quantity == quantity:
            user_stock.delete()
        else:
            user_stock.quantity -= quantity
            user_stock.save()

        return {
            "success": True,
            "balance": float(user_profile.balance),
            "cumulative_profit": float(user_profile.cumulative_profit),
            "stock": stock_symbol,
            "quantity": quantity,
            "price": float(price),
            "sale_profit": float(sale_profit)
        }
        
    except UserStock.DoesNotExist:
        return {"error": "You do not own this stock"}
    except Exception as e:
        return {"error": str(e)}