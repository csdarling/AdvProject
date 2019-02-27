import meas_operators as mo
import numpy as np
import math


class NQubitState:

    def __init__(self, state):
        # State is vector of coefficients:
        # e.g. state = [a,b,c,d]
        self.state = state

    def measure(self, operator):
        shape = operator.shape
        if shape[0] != shape[1]:
            raise Exception("Attempted to measure state with a non-square operator.")

        # print("State prior to measurement: {}\n".format(self.state))

        psi = self.state
        prob_distr = []

        eigh = np.linalg.eigh(operator)
        e_values = eigh[0].astype(int)
        e_vectors = eigh[1]

        distinct_e_values = np.unique(e_values)
        prob_distr = [0] * distinct_e_values.size
        projections = np.zeros((shape[0], distinct_e_values.size))

        for i in range(distinct_e_values.size):

            for j in range(e_values.size):
                if e_values[j] == distinct_e_values[i]:
                    p_j = abs(e_vectors[:, j].dot(psi)) ** 2
                    prob_distr[i] += p_j
                    projections[:, i] += e_vectors[:, j].dot(psi) * e_vectors[:, j]

            # Normalise the projected vector
            norm = math.sqrt(projections[:, i].dot(projections[:, i]))
            if norm:
                projections[:, i] /= norm
            # print("Measure {} and collapse state to {} with probability {:.3f}".format(
                # distinct_e_values[i], projections[:, i], prob_distr[i]))

        idx = np.random.choice(distinct_e_values.size, p=prob_distr)
        meas_result = distinct_e_values[idx]
        new_state = projections[:, idx]

        # print("\nState collapsed to {}".format(new_state))
        # print("Measure bit value: {}\n\n".format(meas_result))

        self.state = new_state
        return meas_result

        # print("e_values: {}".format(e_values))
        # print("e_vectors:\n{}\n".format(e_vectors))

        # for i in range(e_values.size):
        #     p_i = abs(e_vectors[:, i].dot(psi)) ** 2
        #     print("Measure {} and collapse state to {} with probability {:.3f}".format(int(e_values[i]), e_vectors[:, i], p_i))
        #     prob_distr.append(p_i)

        # idx = np.random.choice(shape[0], p=prob_distr)
        # eigen_value = eigh[0][idx]
        # eigen_vector = eigh[1][:, idx]

        # self.state = eigen_vector
        # return int(eigen_value)


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

