import numpy as np
import math
import shared_fns


class NQubitState:

    def __init__(self, coefficients):
        # The state is represented by a vector of coefficients in the
        # standard basis; e.g. coeffs [a, b] <--> state a|0> + b|1> and
        # coeffs [a, b, c, d] <--> state a|00> + b|01> + c|10> + d|11>.

        # The vector of coefficients must be stored as a numpy array of
        # floats.
        coefficients = np.array(coefficients, dtype=float)

        # Check that the given coefficients are not all zero.
        if np.allclose(coefficients, np.zeros(coefficients.shape)):
            raise ValueError(("At least one of the coefficients of an "
                              "NQubitState must be non-zero."))

        # Check that the length of the vector of coefficients is a
        # positive power of 2.
        if (coefficients.size == 0 or (coefficients.size &
                                      (coefficients.size - 1)) != 0):
            raise ValueError(("The length of the vector of coefficients"
                              " associated with an NQubitState must be "
                              "a positive power of 2."))

        # The state must be normalised.
        coefficients = shared_fns.normalise(coefficients)
        self.coefficients = coefficients

        # Create the qubits that constitute the state.
        self.num_qubits = int(math.log(coefficients.size, 2))
        qubits = []
        for i in range(self.num_qubits):
            qubit = Qubit(self, i)
            qubits.append(qubit)

        self.qubits = qubits

    def __repr__(self):
        coeffs_string = ""
        num_coeffs = self.coefficients.size

        # Special representation for certain 1-qubit states.
        if num_coeffs == 2:
            qubit_0 = NQubitState([1, 0])
            qubit_1 = NQubitState([0, 1])
            qubit_plus = NQubitState([1, 1])
            qubit_minus = NQubitState([1, -1])
            if shared_fns.equal_coefficients(self, qubit_0):
                coeffs_string = "|0>"
            elif shared_fns.equal_coefficients(self, qubit_1):
                coeffs_string = "|1>"
            elif shared_fns.equal_coefficients(self, qubit_plus):
                coeffs_string = "|+>"
            elif shared_fns.equal_coefficients(self, qubit_minus):
                coeffs_string = "|->"

        # Generic linear combination representation for all other states.
        else:
            count = 0
            for i, coeff in enumerate(self.coefficients):
                coeffs_string += "%.2f" % coeff + "|{}>".format(i)
                if count < num_coeffs - 1:
                    coeffs_string += " + "
                count += 1

        return coeffs_string

    def get_qubit(self, position):
        '''Retrieve the qubit at the specified position.'''
        return self.qubits[position]

    def measure(self, operator):
        '''Measure the state using the given operator.'''
        # Check that the operator is square.
        shape = operator.shape
        if shape[0] != shape[1]:
            raise ValueError(("Attempted to measure NQubitState with a "
                              "non-square operator."))

        # Rename the coefficients variable (just for convenience).
        psi = self.coefficients

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
        self.coefficients = projections[:, subspace]
        return measured_value


class Qubit:

    def __init__(self, state, position):
        # Check that the given state is an instance of NQubitState.
        if not isinstance(state, NQubitState):
            raise TypeError(
                ("Attempted to initialise a Qubit with an invalid state: "
                 "expected an instance of NQubitState; received an instance "
                 "of {}.").format(type(state))
            )

        self.state = state

        # Check that the position is an integer.
        if type(position) != int:
            raise TypeError(("Attempted to initialise a Qubit with "
                             "a position of type {}. The position field must "
                             "be an integer.").format(type(position)))

        # Check that the position is within the valid range of values.
        num_qubits = self.state.num_qubits
        if position < 0 or position > num_qubits - 1:
            raise ValueError(("The given position ({}) is outside the valid "
                              "range [0, {}].").format(position,
                                                       num_qubits - 1))

        self.position = position

    def measure(self, operator):
        '''Measure a single qubit of a multi-qubit state.'''
        n = self.state.num_qubits
        pos = self.position

        # Measurement of a single qubit of the state can only result in a bit,
        # so the eigenvalues are 0 and 1, each with multiplicity 2^(n-1).
        # The following is a convenient ordering of the 2^(n-1) 0's and 1's.
        state_evalues = (([0] * (2 ** pos) + [1] * (2 ** pos))
                         * (2 ** ((n - 1) - pos)))

        # Calculate the eigenvectors for the measurement of the 1-qubit state
        # consisting of just this qubit.
        qubit_evectors = np.linalg.eigh(operator)[1]

        # Calculate the eigenvectors for the measurement of the n-qubit state
        # using the qubit eigenvectors and the Kronecker product.
        # (The appearance of the identity matrix stems from the use of the
        # standard basis when representing the state by its coefficients.)
        state_evectors = np.kron(np.eye(2 ** ((n - 1) - pos)),
                                 np.kron(qubit_evectors, np.eye(2 ** pos)))

        # Use these eigenvalues and eigenvectors to generate a measurement
        # operator which acts on the whole state.
        state_operator = shared_fns.get_measurement_operator(state_evalues,
                                                             state_evectors)

        return self.state.measure(state_operator)

