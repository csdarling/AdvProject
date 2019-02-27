import numpy as np
import random
import time
import state

from math import sqrt


class Party:

    STANDARD_BASIS = np.array([[0, 0], [0, 1]])
    HADAMARD_BASIS = np.array([[1, -1], [-1, 1]]) * 1 / 2

    def __init__(self, uid, name, cchl, is_eve=False):
        self.uid = uid
        self.name = name
        self.cchl = cchl
        self.is_eve = is_eve
        self.socket = Socket(self)

        self.reset()

    def reset(self):
        self.bits = ""
        self.bases = ""

        self.sifted_key = ""
        self.sifted_key_idxs = []
        self.sifted_key_length = 0

        self.check_bits = ""
        self.check_bits_idxs = []

        self.secret_key = ""
        self.secret_key_idxs = []

        self.total_qubits_sent = 0
        self.total_qubits_received = 0

    def connect_to_qchl(self, qchl):
        self.socket.connect_to_qchl(qchl)

    def set_target(self, target_uid):
        self.target_uid = target_uid

    def generate_random_bit(self):
        bit = random.choice([0, 1])
        self.bits += "{}".format(bit)
        return bit

    def generate_random_basis(self):
        idx = random.choice([0, 1])
        basis = Party.STANDARD_BASIS

        if idx:
            basis = Party.HADAMARD_BASIS
            self.bases += "H"

        else:
            self.bases += "S"

        return basis

    def generate_qubit(self):
        bit = self.generate_random_bit()
        basis = self.generate_random_basis()

        initial_state = np.linalg.eigh(basis)[1][bit]
        qubit = state.NQubitState(initial_state)
        # print("New qubit state = {}".format(qubit.state))
        return qubit

    def send_qubit(self):
        qubit = self.generate_qubit()
        self.socket.send(qubit, self.uid, self.target_uid)
        self.total_qubits_sent += 1

    def receive_qubit(self, qubit):
        self.total_qubits_received += 1
        basis = self.generate_random_basis()
        bit = self.measure_qubit(qubit, basis)
        self.bits += "{}".format(bit)

        if self.is_eve:
            self.socket.send(qubit, self.uid, self.target_uid)
            self.total_qubits_sent += 1

        else:
            self.cchl.compare_bases()

    def measure_qubit(self, qubit, basis):
        qubit_state = qubit.measure(basis)
        return qubit_state

    def update_sifted_key(self, bases_match):
        if bases_match:
            bit_idx = len(self.bits) - 1

            # Append the bit to the sifted key
            self.sifted_key += self.bits[bit_idx]
            self.sifted_key_idxs.append(bit_idx)

            # Also append the bit to the secret key
            self.secret_key += self.bits[bit_idx]
            self.secret_key_idxs.append(bit_idx)

            self.sifted_key_length += 1

    def add_check_bit(self, idx=-1):
        # Default: use the most recent bit in the bitstring as a check bit.
        if idx == -1:
            idx = len(self.bits) - 1

        if idx in self.sifted_key_idxs:
            # Record the value and index of the check bit
            self.check_bits += self.bits[idx]
            self.check_bits_idxs.append(idx)

            # Remove the check bit from the secret key
            sk_idx = self.secret_key_idxs.index(idx)
            self.secret_key = self.secret_key[:sk_idx] + self.secret_key[(sk_idx + 1):]
            self.secret_key_idxs.remove(idx)

        else:
            raise IndexError("Check bit is not contained in the sifted key.")

    def add_check_bits(self, idxs):
        for idx in idxs:
            self.add_check_bit(idx)

    def format_sifted_key(self):
        return add_spaces_to_bitstring(self.sifted_key, self.sifted_key_idxs, len(self.bits))

    def format_check_bits(self):
        return add_spaces_to_bitstring(self.check_bits, self.check_bits_idxs, len(self.bits))

    def format_secret_key(self):
        return add_spaces_to_bitstring(self.secret_key, self.secret_key_idxs, len(self.bits))


class Socket:

    def __init__(self, party):
        self.party = party

    def connect_to_qchl(self, qchl):
        self.qchl = qchl

    def send(self, qubit, sender_uid, target_uid):
        self.qchl.send(qubit, sender_uid, target_uid)

    def receive(self, qubit):
        self.party.receive_qubit(qubit)


class QuantumChannel:

    def __init__(self):
        self.sockets = {}
        self.network = {}
        self.intercepted_edges = {}

    def add_socket(self, uid, socket):
        self.sockets[uid] = socket
        self.network[uid] = []

    def add_edge(self, uid1, uid2):
        self.network[uid1].append(uid2)
        self.network[uid2].append(uid1)

    def intercept_edge(self, edge, eve_uid):
        uid1, uid2 = edge
        if uid2 in self.network[uid1] and uid1 in self.network[uid2]:
            self.intercepted_edges[edge] = eve_uid

    def send(self, qubit, sender_uid, target_uid):
        if target_uid in self.sockets:
            edge = (sender_uid, target_uid)
            if edge in self.intercepted_edges:
                eve_uid = self.intercepted_edges[edge]
                self.sockets[eve_uid].receive(qubit)

            else:
                self.sockets[target_uid].receive(qubit)


class EPRPairSource:

    def __init__(self):
        self.reset()

    def reset(self):
        self.total_sent = 0

    def create_state(self, n=2):
        initial_state = 1 / sqrt(2) * np.array([1] + [0] * (2**n - 2) + [1])
        return state.NQubitState(initial_state)

    def send_qubit(self, socket0, socket1):
        n_qubit_state = self.create_state()
        qubit0 = state.EntangledQubit(n_qubit_state, 0)
        qubit1 = state.EntangledQubit(n_qubit_state, 1)

        self.total_sent += 1

        socket0.receive(qubit0)
        # time.sleep(0.05)
        socket1.receive(qubit1)


def add_spaces_to_bitstring(bitstr, idxs, str_len):
    padded_bitstr = ""
    i = 0

    for count in range(str_len):
        if count in idxs:
            padded_bitstr += bitstr[i]
            i += 1
        else:
            padded_bitstr += " "

    return padded_bitstr
