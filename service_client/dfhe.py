from secrets import randbelow


def generate_privkey(domain_params):
    return randbelow(domain_params['order'])


def dfhe_create_pubkey(domain_params, privkey):
    return pow(domain_params['generator'], privkey, domain_params['order'])


def dfhe_create_sharedkey(domain_params, pubkey, privkey):
    return pow(pubkey, privkey, domain_params['order'])
