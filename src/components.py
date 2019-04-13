import numpy as np
import random
import time
import warnings

import consts
import shared_fns
import state

from math import sqrt


class Party:

    def __init__(self, uid, name, network_manager, cchl, is_eve=False):
        self.uid = uid
        self.name = name
        self.network_manager = network_manager
        self.cchl = cchl
        self.is_eve = is_eve
        # self.socket = Socket(self)
        self.sockets = {}
        self.transmitting = False
        self.receiving = False

        self.reset()

    def reset(self):
        # self.tx_bits = ""
        # self.rx_bits = ""
        # self.bases = ""

        self.tx_bits  = {}  # E.g. {0: [1, 0], 1: [0, 0]}
        self.rx_bits  = {}  # E.g. {0: [1, 0], 1: [0, 0]}
        self.tx_bases = {}  # E.g. {0: [HAD, STD], 1: [STD, STD]}
        self.rx_bases = {}  # E.g. {0: [HAD, STD], 1: [STD, STD]}
        self.next_measurement_bases = {}  # E.g. {0: HAD, 1: STD}
        self.next_sender_uid = None

        # self.sifted_key = ""
        # self.sifted_key_idxs = []
        # self.sifted_key_length = 0

        # self.check_bits = ""
        # self.check_bits_idxs = []

        self.secret_keys = {}
        self.secret_keys_idxs = {}
        self.secret_keys_lengths = {}

        self.total_qubits_sent = 0
        self.total_qubits_received = 0

        self.flip_bits = {}

    def add_socket(self, uid):
        self.sockets[uid] = Socket(self)

    def connect_to_qchl(self, uid, qchl):
        self.add_socket(uid)
        self.sockets[uid].connect_to_qchl(qchl)

    def set_target(self, target_uid):
        self.target_uid = target_uid

    def update_network(self):
        self.successors = self.network_manager.get_successors(self.uid)
        self.predecessors = self.network_manager.get_predecessors(self.uid)

        self.transmitting = True if self.successors else False
        self.receiving = True if self.predecessors else False

    def get_basis_from_char(self, char):
        basis = None
        if char == 'S':
            basis = consts.STANDARD_BASIS
        elif char == 'H':
            basis = consts.HADAMARD_BASIS
        return basis

    def generate_qubit(self, bit, basis):
        # bit = self.generate_random_bit()
        # basis = self.generate_random_basis()
        initial_state = np.linalg.eigh(basis)[1][bit]
        qubit = state.NQubitState(initial_state)
        # print("New qubit state = {}".format(qubit.state))
        return qubit

    def measure_qubit(self, qubit, basis):
        qubit_state = qubit.measure(basis)
        return qubit_state

    def send_qubit(self, target_uid, bit, basis):
        ### EDITED ############################################################
        # basis = Party.STANDARD_BASIS
        # if self.bases and self.total_qubits_sent == self.total_qubits_received - 1:
        #     basis = self.get_basis_from_char(self.bases[-1])
        # else:
        #     basis = self.generate_random_basis()

        qubit = self.generate_qubit(bit, basis)
        socket = None

        try:
            socket = self.sockets[target_uid]
        except KeyError:
            raise KeyError(("Socket {} of Party {} (\"{}\") doesn't exist.\n"
                            "Valid sockets: {}"
                            ).format(target_uid, self.uid, self.name,
                                     list(self.sockets.keys())))

        socket.send(qubit, self.uid, target_uid)
        self.total_qubits_sent += 1

        # self.tx_bits[target_uid].append(bit)
        # self.tx_bases[target_uid].append(basis)
        shared_fns.append_to_dol(self.tx_bits, target_uid, bit)
        shared_fns.append_to_dol(self.tx_bases, target_uid, basis)

        # TODO Move this: it's protocol-specific logic.
        # if not self.receiving:
        #     basis_idx = len(self.bases) - 1
        #     self.broadcast("msg_ready_to_compare_basis",
        #                    self.uid, basis_idx)

    def set_next_sender_uid(self, sender_uid):
        self.next_sender_uid = sender_uid

    def set_next_measurement_basis(self, basis, sender_uid):
        self.next_measurement_bases[sender_uid] = basis

    def receive_qubit(self, qubit, forward=False):
        ### EDITED ############################################################
        # Old version:
        # basis = self.generate_random_basis()

        # basis = Party.STANDARD_BASIS
        # if self.total_qubits_received == self.total_qubits_sent:
        #     basis = self.get_basis_from_char(self.bases[-1])
        # else:
        #     basis = self.generate_random_basis()

        sender_uid = self.next_sender_uid
        basis = self.next_measurement_bases[sender_uid]
        self.next_measurement_bases[sender_uid] = None

        if basis is None:
            raise TypeError(("The measurement basis is set to None for Party "
                             "{} (\"{}\"), so the received qubit can't be "
                             "measured.").format(self.uid, self.name))

        bit = self.measure_qubit(qubit, basis)
        self.total_qubits_received += 1

        shared_fns.append_to_dol(self.rx_bits, sender_uid, bit)
        shared_fns.append_to_dol(self.rx_bases, sender_uid, basis)

        # basis_idx = len(self.bases) - 1
        # ready_msgs = self.broadcast("msg_ready_to_compare_basis",
        #                             self.uid, basis_idx)
        # legit_party_uids = self.network_manager.get_legitimate_party_uids()

        # all_parties_ready_to_compare_bases = True
        # for uid in legit_party_uids:
        #     if (uid not in ready_msgs) or (basis_idx not in ready_msgs[uid]):
        #         all_parties_ready_to_compare_bases = False
        #         break

        # if all_parties_ready_to_compare_bases:
        #     self.broadcast("msg_compare_bases", basis_idx)

    def broadcast_tx_bases(self, basis_idx):
        tx_bases = []
        for uid in self.tx_bases:
            tx_bases.append(self.tx_bases[uid][basis_idx])
        self.broadcast("msg_broadcast_bases", basis_idx, tx_bases)

    def broadcast_rx_bases(self, basis_idx):
        rx_bases = []
        for uid in self.rx_bases:
            rx_bases.append(self.rx_bases[uid][basis_idx])
        self.broadcast("msg_broadcast_bases", basis_idx, rx_bases)

    def broadcast_flip_instruction(self, target_uid, bit_idx, flip_bool):
        # for successor_uid in self.successors:
            # flip = False

            # if (successor_uid in self.tx_bits and
            #     successor_uid in self.rx_bits):

            #     tx_bit = self.tx_bits[successor_uid][bit_idx]
            #     rx_bit = self.rx_bits[successor_uid][bit_idx]

            #     if tx_bit != rx_bit:
            #         flip = True

        self.broadcast("msg_broadcast_flip_instructions",
                       self.uid, target_uid, bit_idx, flip_bool)

    def retrieve_flip_instruction(self, bit_idx):
        sender_uid, bit_needs_flipping = self.cchl.get_flip_instructions(self.uid, bit_idx)
        # print("Retrieved instruction: sender_uid={}, bit_needs_flipping={}".format(sender_uid, bit_needs_flipping))
        if bit_needs_flipping:
            # print("Bit needs flipping!")
            self.flip_bit(sender_uid, bit_idx)

    def compare_bases(self, bases):
        if bases == [bases[0]] * len(bases):
            self.update_sifted_key()

            # If the party is simultaneously transmitting and receiving, and
            # if it transmitted the opposite bit value to the value it received
            # then it must inform its targets to flip their received bit value.
            if self.transmitting and self.receiving and len(self.tx_bits) == len(self.rx_bits):
                if self.tx_bits[-1] != self.rx_bits[-1]:
                    self.broadcast("msg_flip_bit", self.target_uid, len(self.tx_bits) - 1)

    def update_sifted_key_TODO_DELETE(self):
        bits = self.rx_bits if self.rx_bits else self.tx_bits
        bit_idx = len(bits) - 1
        bit = bits[bit_idx]

        if bit_idx in self.flip_bits:
            bit ^= 1
            self.flip_bits.remove(bit_idx)

        # Append the bit to the sifted key
        self.sifted_key += bit
        self.sifted_key_idxs.append(bit_idx)

        # Also append the bit to the secret key
        self.secret_key.append(bit)
        self.secret_key_idxs.append(bit_idx)

        self.secret_key_length += 1

    def extend_secret_key(self, other_party_uid, bits):
        # if other_party_uid in self.secret_keys:
            # print("Old secret key: {}".format(self.secret_keys[other_party_uid]))
        bit_idx = len(bits) - 1
        bit = bits[bit_idx]

        # Check for any bits that need to be flipped.
        if other_party_uid in self.flip_bits:
            # print("flip_bits[{}]: {}\n".format(other_party_uid, self.flip_bits[other_party_uid]))
            if bit_idx in self.flip_bits[other_party_uid]:
                bit ^= 1
                self.flip_bits[other_party_uid].remove(bit_idx)

        shared_fns.append_to_dol(self.secret_keys, other_party_uid, bit)
        shared_fns.append_to_dol(self.secret_keys_idxs, other_party_uid, bit_idx)
        self.secret_keys_lengths[other_party_uid] = len(self.secret_keys[other_party_uid])
        # print("New secret key: {}".format(self.secret_keys[other_party_uid]))

    def extend_secret_keys(self):
        # print("Predecessors: {}".format(self.predecessors))
        for predecessor_uid in self.predecessors:
            bits = self.rx_bits[predecessor_uid]
            self.extend_secret_key(predecessor_uid, bits)

        # print("Successors: {}".format(self.successors))
        for successor_uid in self.successors:
            if successor_uid not in self.predecessors:
                bits = self.tx_bits[successor_uid]
                self.extend_secret_key(successor_uid, bits)

    def broadcast(self, msg, *args):
        msg_func = getattr(self.cchl, msg)
        # print("{} broadcasting message {}".format(self.name, msg))
        return msg_func(*args)

    def flip_bit_char(self, bit_char):
        return str(int(bit_char) ^ 1)

    def flip_bit(self, sender_uid, bit_position):
        # if bit_position < len(self.sifted_key):
        #     # If the specified bit to flip is already in the sifted key,
        #     # then flip the bit of the sifted key immediately.
        #     self.flip_sifted_key_bit(bit_position)
        # else:
        #     # Otherwise, make a note that the bit should be flipped as soon as
        #     # it is received.
        #     self.flip_bits.append(bit_position)
        shared_fns.append_to_dol(self.flip_bits, sender_uid, bit_position)

    def flip_sifted_key_bit(self, bit_position):
        bit_char = ''
        try:
            bit_char = self.sifted_key[bit_position]
        except IndexError:
            raise IndexError((
                "Invalid bit position passed to flip_bit method."
                "\nSifted key length:  {}"
                "\nGiven bit position: {}"
                ).format(len(self.sifted_key), bit_position))

        # bit_char = self.sifted_key[bit_position]

        if bit_char not in ['0', '1']:
            raise ValueError((
                "Party flip_bit method only works on bit values.\n"
                "Attempted to apply flip_bit to character '{}' (sifted key index {})."
                ).format(bit_char, bit_position))

        flipped_bit = int(bit_char) ^ 1
        self.sifted_key = (self.sifted_key[:bit_position] + str(flipped_bit) +
                           self.sifted_key[bit_position + 1:])

    def flip_sifted_key_bits(self, flip_bits_str):
        # TODO Remove? Currently not used!

        if len(flip_bits_str) < len(self.sifted_key):
            warnings.warn(("Passed a string to the Party flip_bits method that "
                           "is shorter than the sifted key: only applying the "
                           "given flip bits string to the first {} bits of the "
                           "sifted key.").format(len(self.sifted_key)))

        elif len(flip_bits_str) > len(self.sifted_key):
            warnings.warn(("Passed a string to the Party flip_bits method that "
                           "is longer than the sifted key: only applying the "
                           "first {} characters of the given flip bits string."
                           ).format(len(self.sifted_key)))

        # if flip_bits_str != len(flip_bits_str) * '0':
        for i, char in enumerate(flip_bits_str):
            if char == "1" and i < len(self.sifted_key):
                self.flip_bit(i)

    def add_check_bit(self, idx=-1):
        # Default: use the most recent bit in the bitstring as a check bit.
        if idx == -1:
            idx = len(self.rx_bits) - 1

        if idx in self.sifted_key_idxs:
            # Record the value and index of the check bit
            self.check_bits += self.rx_bits[idx]
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
        bits = self.rx_bits if self.rx_bits else self.tx_bits
        return shared_fns.add_spaces_to_bitstring(self.sifted_key,
                                                  self.sifted_key_idxs,
                                                  len(bits))

    def format_check_bits(self):
        return shared_fns.add_spaces_to_bitstring(self.check_bits,
                                                  self.check_bits_idxs,
                                                  len(self.rx_bits))

    def format_secret_key(self):
        return shared_fns.add_spaces_to_bitstring(self.secret_key,
                                                  self.secret_key_idxs,
                                                  len(self.rx_bits))


class Socket:

    def __init__(self, party):
        self.party = party

    def connect_to_qchl(self, qchl):
        qchl.add_socket(self.party.uid, self)
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
        self.sockets[target_uid].receive(qubit)

        # print("qchl send method: ({}, {})".format(sender_uid, target_uid))
        # print("qchl sockets: {}".format(self.sockets))
        # if target_uid in self.sockets:
        #     edge = (sender_uid, target_uid)
        #     if edge in self.intercepted_edges:
        #         eve_uid = self.intercepted_edges[edge]
        #         self.sockets[eve_uid].receive(qubit)
        #     else:
        #         self.sockets[target_uid].receive(qubit)


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

