from math import gcd
from sympy.ntheory.factor_ import totient as phi
import random
import primefac


def prime_factors(n):
    return primefac.primefac(n, rho_rounds=30000)

def generators(order):
    last_g = None
    order_phi = phi(order)
    primes = prime_factors(order_phi)
    for g in range(1, order):
        if random.random() < 0.0000001:
            break
        for prime in primes:
            print(prime)
            if pow(g, order_phi//prime, order) == 1:
                break
        else:
            last_g = g
    return last_g


if __name__ == "__main__":
    order = int(input("prime order: "))
    print(f"random generator: {generators(order)}")
