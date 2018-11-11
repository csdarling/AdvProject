#!/bin/python3

import numpy as np
import sympy.physics.quantum as spq
import sympy.physics.quantum.qubit as spqq

class QuantumState:

    def __init__(self, name, state):
        self.name = name
        self.repr = spq.Ket(self.name)
        self.basis = state.keys()
        self.state = sum([state[q] * q for q in self.basis])

    def __repr__(self):
        return(self.repr.__repr__())

    def __mul__(self, other):
        if hasattr(other, 'state'):
            mul = sum([self.state.coeff(q) * other.state.coeff(q) for q in self.basis])
        else:
            mul = self.state * other
        return mul

    def __rmul__(self, other):
        return other * self

    def adjoint(self):
        '''Handle the spq.Dagger operation.'''

        adj = self
        adj.repr = spq.Dagger(adj.repr)
        adj.state = spq.Dagger(adj.state)
        return(adj)


class NQubitSystem:

    def __init__(self, n): # basis=np.identity(2)):

        # Check type is np array? try-except with AttributeError?

        # if basis[:, 0].dot(basis[:, 1]) != 0:
        #     raise ValueError()

        self.qubits = [spqq.Qubit(format(i, '#0{}b'.format(n + 2))[2:]) for i in range(2**n)]
        self.state = self.qubits[0]
        self.n = n

    def update_state(self, coeffs):
        self.state = sum([coeffs[i] * self.qubits[i] for i in range(2 ** self.n)])
        self.coeffs = coeffs

    def measure_qubit(self, basis):
        self.state.dual * basis
        prob_distr = [coeff ** 2 for coeff in self.coeffs]
        self.state = np.random.choice(2, 1, p=prob_distr)[0]

