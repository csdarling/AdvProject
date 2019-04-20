import unittest
import math
import numpy as np
import meas_operators as mo
from state import NQubitState

class TestNQubitState(unittest.TestCase):

    def setUp(self):
        self.measured_value = None   # integer
        self.collapsed_state = None  # numpy array
        self.outcome_counter = {}    # {measured_value: count}

    def measure(self, initial_state, operator):
        '''Create a known state and measure it using the given operator.'''
        # Create the qubit in a known initial state.
        psi = NQubitState(initial_state)
        # Measure the qubit w.r.t. a basis that is pi/4 out.
        self.measured_value = psi.measure(operator)
        self.collapsed_state = psi.state
        # Record the outcome of the measurement.
        if self.measured_value not in self.outcome_counter:
            self.outcome_counter[self.measured_value] = 0
        self.outcome_counter[self.measured_value] += 1

    def repeatedly_measure(self, initial_state, operator, expected_results, num_iterations=2000, tolerance=0.05):
        '''Repeatedly execute the measurement procedure on the given state and operator.'''
        for outcome in expected_results:
            self.outcome_counter[outcome] = 0

        for i in range(num_iterations):
            self.measure(initial_state, operator)
            self.check_measured_value_is_valid(expected_results)
            self.check_collapsed_state_is_valid(expected_results)
            self.check_measured_value_matches_collapsed_state(expected_results)

        self.check_outcome_counter_matches_expected_results(expected_results,
                                                            num_iterations,
                                                            tolerance)

    def check_measured_value_is_valid(self, expected_results):
        '''Check that the measured value is a valid outcome.'''
        self.assertTrue(
            self.measured_value in expected_results,
            msg=("The measured value ({}) is not a valid outcome."
                 "\nValid outcomes: {}"
                ).format(self.measured_value, expected_results.keys())
        )

    def check_collapsed_state_is_valid(self, expected_results):
        '''Check that the collapsed_state is valid.'''
        valid_states = []
        for outcome in expected_results:
            valid_state = expected_results[outcome]["state"]
            valid_states.append(valid_state)
            valid_states.append(-valid_state)

        self.assertTrue(
            any([np.allclose(self.collapsed_state, valid_state)
                 for valid_state in valid_states]),
            msg=("NQubitState has collapsed to an invalid state."
                 "\nCollapsed state: {}"
                 "\nValid states: {}"
                ).format(self.collapsed_state, valid_states)
        )

    def check_measured_value_matches_collapsed_state(self, expected_results):
        '''Check that the measured value matches up with the collapsed state.'''
        valid_states = [ expected_results[self.measured_value]["state"],
                        -expected_results[self.measured_value]["state"]]
        self.assertTrue(
            any([np.allclose(self.collapsed_state, valid_state)
                 for valid_state in valid_states]),
            msg=("The state that the NQubitState has collapsed to does "
                 "not correspond to the measured value."
                 "\nMeasured value:  {}"
                 "\nCollapsed state: {}"
                 "\nExpected state: ±{}"
                ).format(self.measured_value, self.collapsed_state, valid_states[0])
        )

    def check_outcome_counter_matches_expected_results(self, expected_results, num_iterations, tolerance):
        '''Check that the observed counts are satisfactorily close to the theoretical predictions.'''
        # Calculate the expected counts for each outcome using the theoretical
        # probabilities.
        expected_counts = {}
        for outcome in expected_results:
            outcome_probability = expected_results[outcome]["probability"]
            expected_counts[outcome] = num_iterations * outcome_probability

        # Calculate lower and upper bounds for how far the observed count for
        # each outcome can deviate from the theoretical count while staying
        # within the given tolerance.
        allowed_error = num_iterations * tolerance
        lower_bounds = {}
        upper_bounds = {}
        for outcome in expected_results:
            lower_bound = math.ceil(expected_counts[outcome] - allowed_error)
            upper_bound = math.floor(expected_counts[outcome] + allowed_error) + 1
            lower_bounds[outcome] = lower_bound
            upper_bounds[outcome] = upper_bound

        # Check that the observed counts for each outcome lie within the
        # permitted range.
        failure_message = (
            "\n  Observed counts: {}"
            "\n  Expected counts: {}"
            "\n  Tolerance is currently set to {} (±{})"
        ).format(self.outcome_counter, expected_counts, tolerance, allowed_error)

        for outcome in expected_results:
            observed_count = self.outcome_counter[outcome]
            lower_bound = lower_bounds[outcome]
            upper_bound = upper_bounds[outcome]
            self.assertTrue(
                observed_count in range(lower_bound, upper_bound),
                msg=failure_message
            )

    def test_1QubitState_InitialStateSTD_MeasurementOperatorSTD(self):
        '''Create a 1-qubit state in the standard basis and measure it w.r.t.
        the standard basis.'''
        expected_results = {
            0: {"state": NQubitState([1, 0]).state,
                "probability": 1.0},
            1: {"state": NQubitState([0, 1]).state,
                "probability": 0.0}
        }
        self.repeatedly_measure([1, 0], mo.M_STD1, expected_results,
                                num_iterations=100,
                                tolerance=0.0)

        expected_results = {
            0: {"state": NQubitState([1, 0]).state,
                "probability": 0.0},
            1: {"state": NQubitState([0, 1]).state,
                "probability": 1.0}
        }
        self.repeatedly_measure([0, 1], mo.M_STD1, expected_results,
                                num_iterations=100,
                                tolerance=0.0)

    def test_1QubitState_InitialStateHAD_MeasurementOperatorHAD(self):
        '''Create a 1-qubit state in the Hadamard basis and measure it w.r.t.
        the Hadamard basis.'''
        expected_results = {
            0: {"state": NQubitState([1,  1]).state,
                "probability": 1.0},
            1: {"state": NQubitState([1, -1]).state,
                "probability": 0.0}
        }
        self.repeatedly_measure([1,  1], mo.M_HAD1, expected_results,
                                num_iterations=100,
                                tolerance=0.0)

        expected_results = {
            0: {"state": NQubitState([1,  1]).state,
                "probability": 0.0},
            1: {"state": NQubitState([1, -1]).state,
                "probability": 1.0}
        }
        self.repeatedly_measure([1, -1], mo.M_HAD1, expected_results,
                                num_iterations=100,
                                tolerance=0.0)

    def test_1QubitState_InitialStateSTD_MeasurementOperatorHAD(self):
        '''Create a 1-qubit state in the standard basis and measure it w.r.t.
        the Hadamard basis.'''
        expected_results = {
            0: {"state": NQubitState([1,  1]).state,
                "probability": 0.5},
            1: {"state": NQubitState([1, -1]).state,
                "probability": 0.5}
        }
        self.repeatedly_measure([1, 0], mo.M_HAD1, expected_results)
        self.repeatedly_measure([0, 1], mo.M_HAD1, expected_results)

    def test_1QubitState_InitialStateHAD_MeasurementOperatorSTD(self):
        '''Create a 1-qubit state in the Hadamard basis and measure it w.r.t.
        the standard basis.'''
        expected_results = {
            0: {"state": NQubitState([1, 0]).state,
                "probability": 0.5},
            1: {"state": NQubitState([0, 1]).state,
                "probability": 0.5}
        }
        self.repeatedly_measure([1,  1], mo.M_STD1, expected_results)
        self.repeatedly_measure([1, -1], mo.M_STD1, expected_results)


if __name__ == '__main__':
    unittest.main()
