import engine as E
DEV = {
    "age4_x": E.AgeTable(4, 4, [0, 0, 1, 1], 3),
    "age4_y": E.AgeTable(4, 4, [0, 0, 0, 1], 2, age_all=False),
    "perm4_a": E.random_permutation_policy(4, 101),
    "ins2_4": E.lip_like(4, 2, 6),
    "lru4": E.LRU(4),
    "ins0_6b": E.lip_like(6, 0, 1),
    "plru8": E.PLRU(8),
    "switch4": E.Switch(4, 4),
    "agemiss4": E.AgeOnMiss(4, 4, [0, 0, 1, 1], 1),
    "bip4_64": E.BIP(4, 1 / 64),
    "plru4_fb32": E.PLRUFallback(4, 1 / 32),
    "srrip_rtie4": E.AgeTable(4, 4, [0, 0, 0, 0], 2, tie="random"),
}
HELD = {
    "age4_z": E.AgeTable(4, 4, [0, 1, 1, 2], 1),
    "perm4_c": E.random_permutation_policy(4, 606),
    "ins0_6": E.lip_like(6, 0, 9),
    "agemiss4_b": E.AgeOnMiss(4, 4, [0, 1, 1, 2], 2),
    "bip4_32": E.BIP(4, 1 / 32),
    "plru4_fb16": E.PLRUFallback(4, 1 / 16),
}
if __name__ == "__main__":
    for name, p in {**DEV, **HELD}.items():
        print(name, "randomized" if p.randomized else E.machine(p, cap=10 ** 6)[0])
