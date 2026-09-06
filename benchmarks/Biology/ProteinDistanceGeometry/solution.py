def build_conformation(problem):
    n = len(problem["atom_ids"])
    return {"coordinates": [[3.8*(i-(n-1)/2), 0., 0.] for i in range(n)]}
