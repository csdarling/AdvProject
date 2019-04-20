import meas_operators as mo
import numpy as np
import math


class NQubitState:

    def __init__(self, state):
        # The state is stored as a vector of coefficients.
        # E.g. state = [a,b,c,d] <--> a|00> + b|01> + c|10> + d|11>

        # The state must be a numpy array of floats.
        state = np.array(state, dtype=float)
        # Check that the given state is not the zero vector.
        if np.allclose(state, np.zeros(state.shape)):
            raise ValueError(("The state of NQubitState can't be equal to the "
                              "zero vector."))
        # Check that the size of the given state is a positive power of 2.
        if state.size == 0 or ((state.size & (state.size - 1)) != 0):
            raise ValueError(("The size of the state of NQubitState must be a "
                              "positive power of 2."))
        # Normalise the state.
        norm = math.sqrt(state.dot(state))
        self.state = state / norm

    def measure(self, operator):
        '''Measure the state using the given measurement operator.'''
        # Check that the operator is square.
        shape = operator.shape
        if shape[0] != shape[1]:
            raise Exception("Attempted to measure state with a non-square operator.")

        psi = self.state
        prob_distr = []

        # Calculate the eigenvalues and eigenvectors of the given operator.
        eigh = np.linalg.eigh(operator)
        e_values = [int(round(eigh[0][i])) for i in range(eigh[0].size)]
        e_values = np.array(e_values)
        e_vectors = eigh[1]

        # The number of subspaces that the state can be projected onto is
        # given by the number of distinct eigenvalues.
        distinct_e_values = np.unique(e_values)
        number_of_eigenspaces = distinct_e_values.size
        prob_distr = [0] * number_of_eigenspaces
        projections = np.zeros((shape[0], number_of_eigenspaces))

        # For each subspace...
        for i in range(number_of_eigenspaces):
            for j in range(e_values.size):
                if e_values[j] == distinct_e_values[i]:
                    prob_j = abs(e_vectors[:, j].dot(psi)) ** 2
                    prob_distr[i] += prob_j
                    projections[:, i] += e_vectors[:, j].dot(psi) * e_vectors[:, j]

            # Normalise the projected vector.
            norm = math.sqrt(projections[:, i].dot(projections[:, i]))
            if norm:
                projections[:, i] /= norm

        # Choose an subspace according to the probability distribution.
        idx = np.random.choice(number_of_eigenspaces, p=prob_distr)
        # The new state is the eigenvector.
        self.state = projections[:, idx]
        # The output of the measurement is the eigenvalue.
        measured_value = distinct_e_values[idx]
        return measured_value


class EntangledQubit:

    def __init__(self, state, position):
        self.state = state
        self.position = position

    def measure(self, operator):
        # Convert operator to 2-qubit version
        # TODO: Fix this hack! It needs to work for any operator.
        new_operator = None

        if np.allclose(operator, mo.M_S1):
            if self.position == 0:
                # print("STANDARD POSITION 0")
                new_operator = mo.M_S2_0
            elif self.position == 1:
                # print("STANDARD POSITION 1")
                new_operator = mo.M_S2_1

        elif np.allclose(operator, mo.M_H1):
            if self.position == 0:
                # print("HADAMARD POSITION 0")
                new_operator = mo.M_H2_0
            elif self.position == 1:
                # print("HADAMARD POSITION 1")
                new_operator = mo.M_H2_1

        return self.state.measure(new_operator)

