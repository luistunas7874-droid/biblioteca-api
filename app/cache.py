import json

import redis

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


def cache_get(clave: str):
    try:
        valor = redis_client.get(clave)
        return json.loads(valor) if valor else None
    except redis.RedisError:
        return None


def cache_set(clave: str, valor, ttl: int = 60):
    try:
        redis_client.setex(clave, ttl, json.dumps(valor))
    except redis.RedisError:
        pass


def invalidar_ranking():
    try:
        for clave in redis_client.scan_iter("ranking:*"):
            redis_client.delete(clave)
    except redis.RedisError:
        pass