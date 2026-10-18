import math
import pytest
from env.microecology_context.contrast_uncertainty import summarize


def test_paired_common_offset_cancels_and_noise_is_retained():
    # Common offsets cancel within each block; AB contrasts are 0, 2, 4.
    r=summarize([[1,2,3,4],[11,12,13,16],[21,22,23,28]])
    ab=r['effects']['AB_interaction']
    assert ab['replicate_effects']==[0,2,4]
    assert ab['mean']==2
    assert ab['standard_error']==pytest.approx(2/math.sqrt(3))
    assert r['effects']['A_at_B_low']['standard_error']==0
    assert r['discovery_score'] is None


def test_insufficient_or_nonfinite_blocks_rejected():
    for x in [[[1,2,3,4]],[[1,2],[3,4]],[[1,2,3,4],[0,0,0,float('nan')]]]:
        with pytest.raises(ValueError):summarize(x)
