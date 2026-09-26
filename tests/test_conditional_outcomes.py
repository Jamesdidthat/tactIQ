import unittest
import numpy as np
from src.analysis.conditional_outcomes import _fit

class MatchedPairLikelihoodTests(unittest.TestCase):
    def test_recovers_positive_and_negative_synthetic_signs(self):
        rng=np.random.default_rng(3); x=rng.normal(size=(1000,2)); beta=np.array([1.0,-0.8])
        # Construct case-control deltas with a known positive likelihood tilt.
        accepted=[]
        while len(accepted)<400:
            candidate=rng.normal(size=2)
            if rng.random()<1/(1+np.exp(-candidate@beta)): accepted.append(candidate)
        fitted,_,converged,_,_,_,_=_fit(np.asarray(accepted))
        self.assertTrue(converged)
        self.assertGreater(fitted[0],0)
        self.assertLess(fitted[1],0)

if __name__ == "__main__": unittest.main()
