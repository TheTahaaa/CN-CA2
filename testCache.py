import collections


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return -1

    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value


cacheTest = LRUCache(3)
cacheTest.set(1, 'fuck')
print(cacheTest.cache)
cacheTest.set(2, {'user: kir', 'OS: mac'})
print(cacheTest.cache)
cacheTest.set(2, 'kos')
print(cacheTest.cache)
# cacheTest.set(4, 'goh')
# print(cacheTest.cache)
# cacheTest.set(5, 'goh')
# print(cacheTest.cache)
# print(cacheTest.get(3))