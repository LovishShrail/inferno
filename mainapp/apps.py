from django.apps import AppConfig
import redis

class MainappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mainapp'

    def ready(self):
        """Flush Redis when the app starts"""
        try:
            redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
            redis_client.flushdb()
            print("Redis database cleared on startup!")
        except Exception as e:
            print(f"Error clearing Redis: {e}")
