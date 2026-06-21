import asyncio
import aiohttp
import random

async def send_request(url, proxy):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy) as response:
                return await response.text()
    except Exception as e:
        print(f"Erreur avec le proxy {proxy}: {e}")
        return None

async def run_requests(mode='basique', num_requests=5, delay=1.0):
    url = "https://httpbin.org/ip"
    
    if mode == 'basique':
        for _ in range(num_requests):
            proxy = f"http://{random.randint(10, 20)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}:8080"
            await send_request(url, proxy)
            await asyncio.sleep(delay)

    elif mode == 'rapide':
        tasks = []
        for _ in range(num_requests):
            proxy = f"http://{random.randint(10, 20)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}:8080"
            task = send_request(url, proxy)
            tasks.append(task)
        results = await asyncio.gather(*tasks)

    elif mode == 'extreme':
        while True:
            proxy = f"http://{random.randint(10, 20)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}:8080"
            await send_request(url, proxy)
            await asyncio.sleep(delay)

# Exemple d'utilisation
asyncio.run(run_requests('basique', num_requests=3))
