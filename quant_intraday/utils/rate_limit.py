import time, threading
class TokenBucket:
    def __init__(self, capacity:int, rate:float):
        self.capacity=capacity; self.tokens=capacity; self.rate=rate
        self.lock=threading.Lock(); self.ts=time.monotonic()
    def take(self, n:int=1):
        with self.lock:
            now=time.monotonic(); delta=now-self.ts
            self.tokens=min(self.capacity, self.tokens+delta*self.rate); self.ts=now
            if self.tokens>=n: self.tokens-=n; return True
            return False
    def wait(self, n:int=1):
        while not self.take(n): time.sleep(0.05)
