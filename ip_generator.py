import random

def generate_random_ip():
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"

if __name__ == "__main__":
    print(generate_random_ip())

