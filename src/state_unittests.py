import unittest
from math import floor, ceil, cos, sin, pi, sqrt
import numpy as np

from state import NQubitState
from shared_fns import get_measurement_operator

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
        self.collapsed_state = psi.coefficients
        # Record the outcome of the measurement.
        if self.measured_value not in self.outcome_counter:
            self.outcome_counter[self.measured_value] = 0
        self.outcome_counter[self.measured_value] += 1

    def repeatedly_measure(self, initial_state, operator, expected_results, num_iterations=1000, tolerance=0.1):
        '''Repeatedly execute the measurement procedure on the given state and operator.'''
        self.outcome_counter.clear()
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
            lower_bound = ceil(expected_counts[outcome] - allowed_error)
            upper_bound = floor(expected_counts[outcome] + allowed_error) + 1
            lower_bounds[outcome] = lower_bound
            upper_bounds[outcome] = upper_bound

        # Check that the observed counts for each outcome lie within the
        # permitted range.
        failure_message = (
            "\n  Observed counts: {}"
            "\n  Expected counts: {}"
            "\n  Tolerance is currently set at {} (±{})"
        ).format(self.outcome_counter, expected_counts, tolerance, allowed_error)

        for outcome in expected_results:
            observed_count = self.outcome_counter[outcome]
            lower_bound = lower_bounds[outcome]
            upper_bound = upper_bounds[outcome]
            self.assertTrue(
                observed_count in range(lower_bound, upper_bound),
                msg=failure_message
            )

    def run_1QubitState_tests(self, initial_states, collapsed_states, probabilities, num_iterations, tolerance):
        '''Run the measurements for the given 1-qubit states and probabilities.'''
        outcomes = [0, 1]  # [i for i in range(len(initial_states))]
        operator = get_measurement_operator(outcomes, collapsed_states)
        expected_results = {}
        for outcome in outcomes:
            expected_results[outcome] = {
                "state": NQubitState(collapsed_states[outcome]).coefficients,
                "probability": probabilities[outcome]
            }
        self.repeatedly_measure(initial_states[0], operator, expected_results,
                                num_iterations, tolerance)
        expected_results[0]["probability"] = probabilities[1]
        expected_results[1]["probability"] = probabilities[0]
        self.repeatedly_measure(initial_states[1], operator, expected_results,
                                num_iterations, tolerance)

    def test_1QubitState_InitialStateSTD_MeasurementOperatorSTD(self):
        '''Measure the standard basis vectors w.r.t. the standard basis.'''
        num_iterations = 100
        tolerance = 0.0

        initial_states = [[1, 0], [0, 1]]
        collapsed_states = initial_states
        probabilities = [1.0, 0.0]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialStateHAD_MeasurementOperatorHAD(self):
        '''Measure the Hadamard basis vectors w.r.t. the Hadamard basis.'''
        num_iterations = 100
        tolerance = 0.0

        initial_states = [[1, 1], [1, -1]]
        collapsed_states = initial_states
        probabilities = [1.0, 0.0]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialStateSTD_MeasurementOperatorHAD(self):
        '''Measure the standard basis vectors w.r.t. the Hadamard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[1, 0], [0, 1]]
        collapsed_states = [[1, 1], [1, -1]]
        probabilities = [0.5, 0.5]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialStateHAD_MeasurementOperatorSTD(self):
        '''Measure the Hadamard basis vectors w.r.t. the standard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[1, 1], [1, -1]]
        collapsed_states = [[1, 0], [0, 1]]
        probabilities = [0.5, 0.5]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState30_MeasurementOperatorSTD(self):
        '''Measure angle pi/6 (30 degrees) w.r.t. the standard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[cos(pi/6), sin(pi/6)], [- sin(pi/6), cos(pi/6)]]
        collapsed_states = [[1, 0], [0, 1]]
        probabilities = [0.75, 0.25]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState30_MeasurementOperatorHAD(self):
        '''Measure angle pi/6 (30 degrees) w.r.t. the Hadamard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[cos(pi/6), sin(pi/6)], [- sin(pi/6), cos(pi/6)]]
        collapsed_states = [[1, 1], [1, -1]]
        probabilities = [( cos(pi/6) * sqrt(1/2) + sin(pi/6) * sqrt(1/2)) ** 2,
                         (-sin(pi/6) * sqrt(1/2) + cos(pi/6) * sqrt(1/2)) ** 2]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState60_MeasurementOperatorSTD(self):
        '''Measure angle pi/3 (60 degrees) w.r.t. the standard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[cos(pi/3), sin(pi/3)], [- sin(pi/3), cos(pi/3)]]
        collapsed_states = [[1, 0], [0, 1]]
        probabilities = [0.25, 0.75]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState60_MeasurementOperatorHAD(self):
        '''Measure angle pi/3 (60 degrees) w.r.t. the Hadamard basis.'''
        num_iterations = 1000
        tolerance = 0.1

        initial_states = [[cos(pi/3), sin(pi/3)], [- sin(pi/3), cos(pi/3)]]
        collapsed_states = [[1, 1], [1, -1]]
        probabilities = [( cos(pi/3) * sqrt(1/2) + sin(pi/3) * sqrt(1/2)) ** 2,
                         (-sin(pi/3) * sqrt(1/2) + cos(pi/3) * sqrt(1/2)) ** 2]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState30_MeasurementOperator30(self):
        '''Measure angle pi/6 (30 degrees) w.r.t. angle pi/6 (30 degrees).'''
        num_iterations = 100
        tolerance = 0.0

        initial_states = [[cos(pi/6), sin(pi/6)], [- sin(pi/6), cos(pi/6)]]
        collapsed_states = initial_states
        probabilities = [1.0, 0.0]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState60_MeasurementOperator60(self):
        '''Measure angle pi/3 (60 degrees) w.r.t. angle pi/3 (60 degrees).'''
        num_iterations = 100
        tolerance = 0.0

        initial_states = [[cos(pi/3), sin(pi/3)], [- sin(pi/3), cos(pi/3)]]
        collapsed_states = initial_states
        probabilities = [1.0, 0.0]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState30_MeasurementOperator75(self):
        '''Measure angle pi/6 (30 degrees) w.r.t. angle 5pi/12 (75 degrees).'''
        num_iterations = 1000
        tolerance = 0.1

        theta = pi/6 + pi/4
        initial_states = [[cos(pi/6), sin(pi/6)], [-sin(pi/6), cos(pi/6)]]
        collapsed_states = [[cos(theta), sin(theta)], [-sin(theta), cos(theta)]]
        probabilities = [0.5, 0.5]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState60_MeasurementOperator105(self):
        '''Measure angle pi/3 (60 degrees) w.r.t. angle 7pi/12 (105 degrees).'''
        num_iterations = 1000
        tolerance = 0.1

        theta = pi/3 + pi/4
        initial_states = [[cos(pi/3), sin(pi/3)], [-sin(pi/3), cos(pi/3)]]
        collapsed_states = [[cos(theta), sin(theta)], [-sin(theta), cos(theta)]]
        probabilities = [0.5, 0.5]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def test_1QubitState_InitialState60_MeasurementOperator15(self):
        '''Measure angle pi/3 (60 degrees) w.r.t. angle pi/12 (15 degrees).'''
        num_iterations = 1000
        tolerance = 0.1

        theta = pi/3 - pi/4
        initial_states = [[cos(pi/3), sin(pi/3)], [-sin(pi/3), cos(pi/3)]]
        collapsed_states = [[cos(theta), sin(theta)], [-sin(theta), cos(theta)]]
        probabilities = [0.5, 0.5]

        self.run_1QubitState_tests(initial_states, collapsed_states, probabilities,
                                  num_iterations, tolerance)

    def run_2QubitState_tests(self, initial_states, collapsed_states, probabilities, num_iterations, tolerance):
        pass

    def test_2QubitState_InitialStateSTD_MeasurementOperatorSTD(self):
        '''Create a 2-qubit state in the standard basis and measure it w.r.t. the standard basis.'''
        num_iterations = 100
        tolerance = 0.0

        initial_states = [[1, 0, 0, 0],
                          [0, 1, 0, 0],
                          [0, 0, 1, 0],
                          [0, 0, 0, 1]]

        collapsed_states = initial_states
        operator = get_measurement_operator([0, 1, 2, 3], collapsed_states)

        expected_results = {
            0: {"state": NQubitState(collapsed_states[0]).coefficients,
                "probability": 1.0},
            1: {"state": NQubitState(collapsed_states[1]).coefficients,
                "probability": 0.0},
            2: {"state": NQubitState(collapsed_states[2]).coefficients,
                "probability": 0.0},
            3: {"state": NQubitState(collapsed_states[3]).coefficients,
                "probability": 0.0}
        }
        self.repeatedly_measure(initial_states[0], operator, expected_results,
                                num_iterations, tolerance)

        expected_results[0]["probability"] = 0.0
        expected_results[1]["probability"] = 1.0
        self.repeatedly_measure(initial_states[1], operator, expected_results,
                                num_iterations, tolerance)

        expected_results[1]["probability"] = 0.0
        expected_results[2]["probability"] = 1.0
        self.repeatedly_measure(initial_states[2], operator, expected_results,
                                num_iterations, tolerance)

        expected_results[2]["probability"] = 0.0
        expected_results[3]["probability"] = 1.0
        self.repeatedly_measure(initial_states[3], operator, expected_results,
                                num_iterations, tolerance)


if __name__ == '__main__':
    unittest.main()
