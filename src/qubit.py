import numpy as np

# class Qubit:

#     def __init__(self, theta):
#         self.theta = theta

#     def measure(self, basis):
#         # phton_state = sin(theta)|0> + cos(theta)|1>
#         # basis_state =   sin(phi)|0> +   cos(phi)|1>
#         # bdual_state =   cos(phi)|0> -   sin(phi)|1>
#         theta = self.theta
#         phi = basis[0]

#         coeffs = [sin(theta) * sin(phi) + cos(theta) * cos(phi),
#                   sin(theta) * cos(phi) - cos(theta) * sin(phi)]

#         prob_distr = [coeff ** 2 for coeff in coeffs]

#         idx = np.random.choice(2, p=prob_distr)
#         self.theta = basis[idx]
#         return self.theta


class Qubit:

    def __init__(self, state):
        # State is vector of coefficients:
        # e.g. state = [a,b,c,d]
        self.state = state

    def measure(self, H):
        shape = H.shape
        if shape[0] != shape[1]:
            raise Exception("Attempted to measure state with a non-square operator.")

        psi = self.state
        # Ms = []
        prob_distr = []

        # print()

        # for i in range(shape[0]):
        #     M = np.zeros(shape)
        #     M[:, i] = H[:, i]
        #     Ms.append(M)
        #     print("M_{}:\n{}\n".format(i, M))
        #     # <psi| M.T.conj() M |psi>
        #     p = psi.dot(M.T.conj() @ M @ psi)
        #     print("p_{}: {}\n".format(i, p))
        #     prob_distr.append(p)

        eigh = np.linalg.eigh(H)
        e_values = eigh[0]
        e_vectors = eigh[1]

        # print("e_values = {}".format(e_values))
        # print("e_vectors = {}".format(e_vectors))

        for i in range(len(e_values)):
            p_i = abs(e_vectors[i].dot(psi)) ** 2
            # print("i = {},  p_i = {}".format(i, p_i))
            prob_distr.append(p_i)

        # Check the measurement operators satisfy the completeness axiom
        # if not np.allclose(sum([M.T.conj() @ M for M in Ms]), np.eye(shape[0])):
        #     raise Exception("Measurement operators do not satisfy the completeness axiom.")

        idx = np.random.choice(shape[0], p=prob_distr)

        # print("Random idx = {}\n".format(idx))

        # self.state = H[:, idx]
        # return self.state

        eigen_value = eigh[0][idx]
        eigen_vector = eigh[1][:, idx]

        # print("New state  = {}".format(eigen_vector))
        # print("Return val = {}".format(eigen_value))

        self.state = eigen_vector
        return int(eigen_value)

