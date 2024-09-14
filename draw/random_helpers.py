import random

LOW_CHANCE = 7
FAIR_CHANCE = 1

def low_chance():
    return random.randint(0, LOW_CHANCE) == 0

def fair_chance():
    return random.randint(0, FAIR_CHANCE) == 0
