import asyncio
import logging

class FirebaseWriter:
    def __init__(self):
        self.queue = asyncio.Queue()
        self._start_worker()

    def _start_worker(self):
        asyncio.create_task(self._worker())

    async def _worker(self):
        while True:
            func, args, kwargs = await self.queue.get()
            try:
                await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                logging.error(f"Firestore write failed: {e}")
            finally:
                self.queue.task_done()

    async def submit(self, func, *args, **kwargs):
        await self.queue.put((func, args, kwargs))
