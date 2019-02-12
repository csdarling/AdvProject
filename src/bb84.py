import sys
import random
import numpy as np
import time

from math import pi, sin, cos, log, floor, ceil, sqrt
from qubit import Qubit


class BB84:

    def __init__(self, eve=False, min_key_length=0):
        self.min_key_length = min_key_length
        alice = Party(0, "Alice", cchl=self)
        bob = Party(1, "Bob", cchl=self)
        qchl = QuantumChannel()

        qchl.add_socket(alice.uid, alice.socket)
        alice.connect_to_qchl(qchl)
        qchl.add_socket(bob.uid, bob.socket)
        bob.connect_to_qchl(qchl)
        qchl.add_edge(alice.uid, bob.uid)
        alice.set_target(bob.uid)

        self.alice = alice
        self.bob = bob
        self.qchl = qchl

        self.eve = None
        if eve:
            self.add_eve()

        self.eve_check_complete = False
        self.secret_key = ""

    def reset(self):
        self.alice.reset()
        self.bob.reset()

        if self.eve is not None:
            self.eve.reset()

        self.eve_check_complete = False
        self.secret_key = ""

    def display_data(self):
        alice = self.alice
        bob = self.bob
        eve = self.eve

        print()
        print("Total qubits sent:  {}".format(alice.total_qubits_sent))
        print("Sifted key length:  {}".format(bob.sifted_key_length))
        print()
        print("Alice's bits:       {}".format(alice.bits))
        print("Alice's bases:      {}".format(alice.bases))

        if eve is not None:
            print()
            print("Eve's bits:         {}".format(eve.bits))
            print("Eve's bases:        {}".format(eve.bases))

        print()
        print("Bob's bits:         {}".format(bob.bits))
        print("Bob's bases:        {}".format(bob.bases))

        print()
        print("Alice's sifted key: {}".format(alice.format_sifted_key()))
        print("Bob's sifted key:   {}".format(bob.format_sifted_key()))
        print()

    def send_qubit(self, display_data=True):
        if self.eve_check_complete:
            self.eve_check_complete = False

        self.alice.send_qubit()

        if display_data:
            self.display_data()

    def send_qubits(self, n, display_data=True):
        if self.eve_check_complete:
            self.eve_check_complete = False

        for i in range(n):
            self.alice.send_qubit()

        if display_data:
            self.display_data()

    def establish_key(self, length, security):
        self.reset()
        num_eve_check_bits = self.calculate_num_eve_check_bits(security)
        required_sifted_key_length = length + num_eve_check_bits

        while self.alice.sifted_key_length < required_sifted_key_length:
            self.send_qubit(display_data=False)

        self.display_data()
        self.check_for_eve(security)

    def dynamically_establish_key(self, check_rate=5, security=0.95):
        self.reset()
        required_num_check_bits = self.calculate_num_eve_check_bits(security)
        num_check_bits = 0
        while num_check_bits < required_num_check_bits:
            self.send_qubit(display_data=False)
            bases_match = lambda : self.alice.bases[-1] == self.bob.bases[-1]

            if (self.alice.sifted_key_length and bases_match()
                and self.alice.sifted_key_length % check_rate == 0):

                num_check_bits += 1
                self.alice.add_check_bit()
                self.bob.add_check_bit()

            self.display_data()
            print("Alice's check bits: {}".format(self.alice.format_check_bits()))
            print("Bob's check bits:   {}".format(self.bob.format_check_bits()))
            print("\nAlice's secret key: {}".format(self.alice.format_secret_key()))
            print("Bob's secret key:   {}".format(self.bob.format_secret_key()))

            # Compare Alice and Bob's check bits
            if (self.alice.check_bits and self.bob.check_bits and
                self.alice.check_bits[-1] != self.bob.check_bits[-1]):

                print("\nEavesdropping detected! Aborting this run of the protocol.\n")
                self.reset()
                break

            current_security = self.calculate_eve_prob(num_check_bits)
            print("\nKey security: {:.3f}%.\n".format(current_security * 100))

            time.sleep(0.2)

    def add_eve(self):
        eve = Party(2, "Eve", cchl=self, is_eve=True)
        self.qchl.add_socket(eve.uid, eve.socket)
        eve.connect_to_qchl(self.qchl)
        self.qchl.intercept_edge((self.alice.uid, self.bob.uid), eve.uid)
        eve.set_target(self.bob.uid)
        self.eve = eve

    def remove_eve(self):
        # TODO
        pass

    def calculate_num_eve_check_bits(self, security):
        return ceil(log(1 - security) / log(0.75))

    def calculate_eve_prob(self, num_check_bits):
        # Given n matching check bits, calculate the least upper bound for the
        # probability that Eve has gotten away with eavesdropping.

        value = 0
        upper_bound = 1

        while upper_bound - value > 0.0001:
            value_attempt = value + (upper_bound - value) / 2
            n = self.calculate_num_eve_check_bits(value_attempt)
            if n > num_check_bits:
                upper_bound = value_attempt
            elif n <= num_check_bits:
                value = value_attempt

        return value

    def check_for_eve(self, security=0.95):
        if self.eve_check_complete:
            return

        num_bits = self.calculate_num_eve_check_bits(security)
        sifted_key_length = self.alice.sifted_key_length

        if sifted_key_length - num_bits < self.min_key_length:
            print("Not enough bits to run eavesdropping test.\n")

        else:
            idxs = sorted(random.sample(self.alice.sifted_key_idxs, num_bits))
            self.alice.add_check_bits(idxs)
            self.bob.add_check_bits(idxs)

            print("Alice's check bits: {}".format(self.alice.format_check_bits()))
            print("Bob's check bits:   {}".format(self.bob.format_check_bits()))

            if self.alice.check_bits == self.bob.check_bits:
                print("\nKey security: {:.3f}%.\n".format(security * 100))
                print("Secret key:         {}\n".format(self.alice.format_secret_key()))
                self.eve_check_complete = True
                self.secret_key = self.alice.secret_key

            else:
                print("\nEavesdropping detected! Aborting this run of the protocol.\n")
                self.reset()

    def compare_bases(self):
        match = False
        if self.alice.bases[-1] == self.bob.bases[-1]:
            match = True

        self.alice.update_sifted_key(match)
        self.bob.update_sifted_key(match)


class Party:

    # STANDARD_BASIS = (0, pi / 2)
    # HADAMARD_BASIS = (pi / 4, 3 * (pi / 4))
    # STANDARD_BASIS = np.array([[1, 0], [0, 1]])
    # HADAMARD_BASIS = 1 / sqrt(2) * np.array([[1, 1], [1, -1]])

    # STANDARD_BASIS = np.array([[0, 0], [0, 1]])
    # HADAMARD_BASIS = np.array([[0, 1], [1, 0]])

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
        # return Qubit(basis[bit])
        # return Qubit(basis[:, bit])
        initial_state = np.linalg.eigh(basis)[1][bit]
        qubit = Qubit(initial_state)
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
        # bit = 0 if result == basis[0] else 1
        # return bit

        # print("Measured qubit state: {}".format(qubit_state))
        # print("Measurement basis 0:  {}".format(basis[:, 0]))
        # print("Measurement basis 1:  {}".format(basis[:, 1]))
        # bit = 0 if np.allclose(qubit_state, basis[:, 0]) else 1
        # return bit

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

# def symbolise(value):
#     utf_8 = (sys.getdefaultencoding() == "utf-8")
#     pi_str = "\u03C0" if utf_8 else "pi"

#     if value == pi:
#         value = pi_str

#     elif value == 3 * pi / 4:
#         value = "3{}/4".format(pi_str)

#     elif value == pi / 2:
#         value = "{}/2".format(pi_str)

#     elif value == pi / 4:
#         value = "{}/4".format(pi_str)

#     return value

# def is_unitary(M):
#     shape = M.shape
#     if shape[0] != shape[1]:
#         return False

#     dim = shape[0]
#     return np.allclose(np.eye(dim), M @ M.T.conj())
