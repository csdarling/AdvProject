import meas_operators as mo
import numpy as np
import math
import shared_fns


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
        self.state = shared_fns.normalise(state)

    def measure(self, operator):
        '''Measure the state using the given measurement operator.'''
        # Check that the operator is square.
        shape = operator.shape
        if shape[0] != shape[1]:
            raise Exception("Attempted to measure state with a non-square operator.")

        # Rename the state variable (just for convenience).
        psi = self.state

        # Calculate the eigenvalues and eigenvectors of the given operator.
        eigh = np.linalg.eigh(operator)
        eigenvalues = [int(round(eigh[0][i])) for i in range(eigh[0].size)]
        eigenvalues = np.array(eigenvalues)
        eigenvectors = eigh[1]

        # The number of subspaces that the state can be projected onto is
        # given by the number of distinct eigenvalues.
        distinct_evalues, idxs, multiplicities = np.unique(eigenvalues,
                                                           return_index=True,
                                                           return_counts=True)
        number_of_subspaces = distinct_evalues.size
        prob_distr = [0] * number_of_subspaces
        projections = np.zeros((shape[0], number_of_subspaces))

        # Calculate the probability and projected vector for each subspace.
        for i, evalue in enumerate(distinct_evalues):
            multiplicity = multiplicities[i]
            evector = eigenvectors[idxs[i]]
            # Calculate the probability that psi collapses onto this subspace.
            probability = abs(evector.dot(psi)) ** 2
            prob_distr[i] = probability * multiplicity
            # Calculate the projection of psi onto this subspace.
            projection = evector.dot(psi) * evector
            projections[:, i] = shared_fns.normalise(projection * multiplicity)

        # Choose an subspace according to the probability distribution.
        subspace = np.random.choice(number_of_subspaces, p=prob_distr)
        # The measured value is the eigenvalue associated with this subspace.
        measured_value = distinct_evalues[subspace]
        # The new state is the projection of psi onto this subspace.
        self.state = projections[:, subspace]
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

