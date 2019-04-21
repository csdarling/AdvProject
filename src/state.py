import meas_operators as mo
import numpy as np
import math
import shared_fns


class NQubitState:

    def __init__(self, state):
        # The state is stored as a vector of coefficients (in the standard basis).
        # E.g. state = [a,b,c,d] <--> a|00> + b|01> + c|10> + d|11>

        # The state must be a numpy array of floats.
        state = np.array(state, dtype=float)
        # Check that the given state is not the zero vector.
        if np.allclose(state, np.zeros(state.shape)):
            raise ValueError(("The state of NQubitState can't be equal to the "
                              "zero vector."))
        # Check that the size of the given state is a positive power of 2.
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
        distinct_evalues = np.unique(eigenvalues)
        number_of_subspaces = distinct_evalues.size
        prob_distr = [0] * number_of_subspaces
        projections = np.zeros((shape[0], number_of_subspaces))

        # For each subspace, calculate the probability that the state collapses
        # onto the subspace and the projection of the state onto the subspace.
        for i, distinct_evalue in enumerate(distinct_evalues):
            # The total probability and projection for the subspace is obtained
            # by summing over all the (not necessarily distinct) eigenvectors.
            for j, eigenvalue in enumerate(eigenvalues):
                if eigenvalue == distinct_evalue:
                    evector = eigenvectors[:, j]
                    # Calculate the probability that the state will collapse
                    # to this eigenvector.
                    probability = abs(evector.dot(psi)) ** 2
                    # Add it to the total probability for the subspace.
                    prob_distr[i] += probability
                    # Calculate the component of psi in the direction of this
                    # eigenvector.
                    projection = evector.dot(psi) * evector
                    # Add it to the total for the subspace.
                    projections[:, i] += projection

            # Normalise the projected vector.
            projections[:, i] = shared_fns.normalise(projections[:, i])

        # Choose an subspace according to the probability distribution.
        subspace = np.random.choice(number_of_subspaces, p=prob_distr)
        # The measured value is the eigenvalue associated with this subspace.
        measured_value = distinct_evalues[subspace]
        # The new state is the projection of psi onto this subspace.
        self.state = projections[:, subspace]
        return measured_value


class EntangledQubit:

    def __init__(self, nqubitstate, position):
        self.nqubitstate = nqubitstate
        self.position = position

    def measure(self, operator):
        # Convert operator to 2-qubit version
        num_qubits = int(math.log(self.nqubitstate.state.size, 2))

        new_evalues = (
            ([0] * (2 ** self.position) +
             [1] * (2 ** self.position))
            * (2 ** (num_qubits - self.position - 1))
        )

        operator_evectors = np.linalg.eigh(operator)[1]

        new_evectors = np.kron(
            np.eye(2 ** (num_qubits - self.position - 1)),
            np.kron(operator_evectors, np.eye(2 ** self.position))
        )

        new_operator = shared_fns.get_measurement_operator(new_evalues, new_evectors)
        return self.nqubitstate.measure(new_operator)

