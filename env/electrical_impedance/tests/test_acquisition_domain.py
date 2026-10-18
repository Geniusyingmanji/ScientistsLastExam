import pytest
from env.electrical_impedance.acquisition_domain import AcquisitionDomain
S={'frequencies_hz':[2.,10.],'source_ohm':500.,'load_ohm':5000.,'amplitude_v':1.}

def test_public_domain_and_subset():
    d=AcquisitionDomain([2,10],[(500,5000)],1)
    assert d.validate(dict(S,frequencies_hz=[2]))['frequencies_hz']==[2.]
    for q in [dict(S,frequencies_hz=[7]),dict(S,source_ohm=1000),dict(S,amplitude_v=2)]:
        with pytest.raises(ValueError):d.validate(q)
    assert d.describe()['frequencies_hz']==[2.,10.]

def test_reserved_rows_must_all_be_inaccessible():
    d=AcquisitionDomain([2,10],[(500,5000)],1)
    assert d.verify_reserved([dict(S,frequencies_hz=[7])])['reserved_rows']==1
    assert d.verify_reserved([dict(S,source_ohm=1000)])['exact_disjoint']
    with pytest.raises(ValueError):d.verify_reserved([dict(S,frequencies_hz=[2,7])])
    with pytest.raises(ValueError):d.verify_reserved([])
