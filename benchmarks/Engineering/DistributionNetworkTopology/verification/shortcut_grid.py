def grid_candidate(n, threshold, consume_initial=True, rounding='floor'):
    def recover(problem, probe, budget):
        routes = problem['routes']
        keys = sorted(routes, key=lambda key:(len(routes[key]),key))
        index = round if rounding == 'nearest' else int
        selected = [keys[index(i*(len(keys)-1)/(n-1))] for i in range(n)]
        reports = list(problem['initial_reports']) if consume_initial else []
        reports += [probe(key) for key in selected[:budget]]
        failures = dict.fromkeys(problem['pipe_ids'],0)
        totals = failures.copy()
        for report in reports:
            for pipe in routes[report['route_id']]:
                totals[pipe] += 1
                failures[pipe] += not report['arrived']
        rates = {p: failures[p]/totals[p] for p in totals if totals[p]}
        chosen = sorted((p for p in rates if rates[p]>=threshold),key=lambda p:-rates[p])[:3]
        return {'broken_pipes':chosen or None,'abstain':not chosen,'confidence':.8}
    return recover

recover_network = grid_candidate(25,0.85,False,'floor')
