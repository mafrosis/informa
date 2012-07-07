import memcache

class MemcacheWrapper():
    def __init__(self):
        self.mc = memcache.Client(['127.0.0.1:11211'], debug=0)

    def get(self, key):
        return self.mc.get(key)

    def set(self, key, value, expire=3600):
        return self.mc.set(key, value)

cache = MemcacheWrapper()
