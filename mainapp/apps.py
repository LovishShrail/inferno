from django.apps import AppConfig
import redis
from django.db.models.signals import post_migrate

def reset_user_stocks(sender, **kwargs):
    from .models import UserStock ,UserProfile

    """Clear the UserStock table when the app starts."""
    
    try:
        UserStock.objects.all().delete()
        print("UserStock table cleared on startup!")
        # Reset UserProfile balance
        UserProfile.objects.all().update(balance=10000.00)  # Set default balance
        print("UserProfile balance reset on startup!")
    except Exception as e:
        print(f"Error clearing UserStock table: {e}")
        

class MainappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mainapp'

    def ready(self):
        """Flush Redis and reset UserStock table when the app starts."""
        try:
            # Flush Redis
            redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
            redis_client.flushdb()
            print("Redis database cleared on startup!")
        except Exception as e:
            print(f"Error clearing Redis: {e}")

        # Reset UserStock table
        reset_user_stocks(sender=self)