from env.electrical_impedance.observation_overlap import classify_rows

S={'frequencies_hz':[2.,10.],'source_ohm':500.,'load_ohm':5000.,'amplitude_v':1.}


def test_mixed_panel_not_pure_apparatus():
    q=dict(S,frequencies_hz=[2.,7.],source_ohm=1500.)
    r=classify_rows([S],q)
    assert r['counts']=={'apparatus_only':1,'joint':1}
    assert r['all_exact_disjoint']


def test_overlap_frequency_and_known_amplitude_law():
    assert classify_rows([S],S)['counts']=={'observed':2}
    assert classify_rows([S],dict(S,frequencies_hz=[7.]))['counts']=={'frequency_only':1}
    assert classify_rows([S],dict(S,amplitude_v=2.))['counts']=={'amplitude_only':2}
    assert classify_rows([S],dict(S,amplitude_v=2.,frequencies_hz=[7.]))['counts']=={'amplitude_confounded':1}


def test_crossed_known_factors_and_duplicate_acquisitions():
    other=dict(S,frequencies_hz=[7.],source_ohm=1500.)
    q=dict(S,frequencies_hz=[7.])
    assert classify_rows([S,S,other],q)['counts']=={'new_combination':1}
