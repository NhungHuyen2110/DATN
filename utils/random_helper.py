import random

def random_choice(data):
    return random.choice(data)

def random_price():
    return random.randint(1000000,20000000)

def random_stock():
    return random.randint(5,100)

def random_weight():
    return round(random.uniform(1.5,15),2)