import numpy as np
import random
import time
import warnings
import math
import copy

import consts
import shared_fns
import state


class Party:

    def __init__(self, uid, name, network_manager, cchl, is_eve=False):
        self.uid = uid
        self.name = name
        self.network_manager = network_manager
        self.cchl = cchl
        self.is_eve = is_eve
        self.sockets = {}

        self.reset()

    def reset(self):
        self.timestep = 0

        self.tx_bits  = {}  # Format: {time0: {uidA: bit, uidB: bit}, time1: {uidA: bit}, ...}
        self.rx_bits  = {}  # Old format was {uidA: [bit_t0, bit_t1, ...], uidB: [bit_t0, bit_t1, ...], ...}
                            # e.g. {2: [1, 0, 1], 5: [0, 0, 1], 6: [1, 1, 0]}

        self.tx_bases = {}  # Format: {time0: {uidA: basis, uidB: basis}, time1: {uidA: basis}, ...}
        self.rx_bases = {}  # E.g. {0: {4: HAD, 7: STD}, 1: {}, 2: {4: STD}}
                            # Old format was {uidA: [basis_t0, basis_t1, ...], uidB: [basis_t0, basis_t1...]}
                            # e.g. {3: [HAD, STD], 5: [STD, STD]}

        self.next_measurement_bases = {}  # E.g. {uidA: HAD, uidB: STD}
        self.next_tx_uid = None

        self.measure_received_qubits = True
        self.forward_received_qubits = False
        self.qubit_forwarding_uid = None

        self.sifted_keys = {}  # Format is the same as for tx_bits and rx_bits, e.g.
        self.check_bits  = {}  # {t0: {uidA: bit, uidB: bit}, t3: {uidA: bit, uidB: bit}, ...}
        self.secret_keys = {}

        self.total_qubits_generated = 0
        self.total_qubits_transmitted = 0
        self.total_qubits_received = 0

        self.detected_eavesdropping = False

    def add_socket(self, uid):
        self.sockets[uid] = Socket(self)

    def connect_to_qchl(self, uid, qchl):
        self.add_socket(uid)
        self.sockets[uid].connect_to_qchl(qchl)

    def store_value_in_dict(self, d, key, val):
        '''Store the key, val pair in dictionary d[self.timestep].'''
        if self.timestep not in d:
            d[self.timestep] = {}

        d[self.timestep][key] = val

    def next_qubit_is_from(self, tx_uid):
        '''Note that party tx_uid is about to send a qubit to this party.'''
        self.next_tx_uid = tx_uid

    def measure_next_qubit_wrt(self, basis):
        '''Measure the next qubit from next_tx_uid w.r.t. the given basis.'''
        sender_uid = self.next_tx_uid
        self.next_measurement_bases[sender_uid] = basis
        self.measure_received_qubits = True

    def forward_qubits_to(self, uid):
        '''Forward received qubits to the given UID.'''
        self.qubit_forwarding_uid = uid
        self.forward_received_qubits = True

    def generate_qubit(self, bit, basis):
        '''Create a new qubit representing the given bit and basis.'''

        initial_state = np.linalg.eigh(basis)[1][bit]
        qubit = state.NQubitState(initial_state)
        # print("New qubit state = {}".format(qubit.state))
        self.total_qubits_generated += 1
        return qubit

    def measure_qubit(self, qubit, basis):
        '''Measure the qubit w.r.t. the given basis.'''
        qubit_state = qubit.measure(basis)
        return qubit_state

    def transmit_qubit(self, target_uid, qubit):
        '''Transmit the qubit to the target_uid via a quantum channel.'''
        socket = None
        try:
            socket = self.sockets[target_uid]
        except KeyError:
            raise KeyError(("Socket {} of Party {} (\"{}\") doesn't exist.\n"
                            "Valid sockets: {}"
                            ).format(target_uid, self.uid, self.name,
                                     list(self.sockets.keys())))

        socket.send(qubit, self.uid, target_uid)
        self.total_qubits_transmitted += 1

    def send_qubit(self, target_uid, bit, basis):
        '''Encode the given bit w.r.t. the given basis to generate a new qubit
        and transmit this qubit to the party with the specified uid.'''
        # Generate the qubit using the given bit and basis.
        qubit = self.generate_qubit(bit, basis)

        # Keep a record of the bit and basis used to generate the qubit.
        self.store_value_in_dict(self.tx_bases, target_uid, basis)
        self.store_value_in_dict(self.tx_bits, target_uid, bit)

        # Transmit the qubit to the target party.
        self.transmit_qubit(target_uid, qubit)

    def receive_qubit(self, qubit):
        '''Handle a received qubit (measure it and/or forward it).'''
        bit = None
        basis = None
        # Measure the qubit.
        if self.measure_received_qubits:
            sender_uid = self.next_tx_uid
            basis = self.next_measurement_bases[sender_uid]
            self.next_measurement_bases[sender_uid] = None

            if basis is None:
                raise TypeError(("The measurement basis is set to None for "
                                 "Party {} (\"{}\"), so the received qubit "
                                 "can't be measured.").format(self.uid,
                                                              self.name))

            bit = self.measure_qubit(qubit, basis)
            self.total_qubits_received += 1

            # Keep a record of the measurement basis and the measured bit.
            self.store_value_in_dict(self.rx_bases, sender_uid, basis)
            self.store_value_in_dict(self.rx_bits, sender_uid, bit)

        # Forward the qubit to the qubit_forwarding_uid.
        if self.forward_received_qubits:
            # Store the basis and bit in the dictionary of tx_bases.
            # Note: If forwarding without measuring, then the basis and the
            # bit are both stored as None.
            self.store_value_in_dict(self.tx_bases,
                                     self.qubit_forwarding_uid,
                                     basis)
            self.store_value_in_dict(self.tx_bits,
                                     self.qubit_forwarding_uid,
                                     bit)
            # Forward the qubit to the qubit_forwarding_uid.
            self.transmit_qubit(self.qubit_forwarding_uid, qubit)

    def broadcast_tx_bases(self, timestep):
        '''Broadcast the tx_bases on the classical channel.'''
        msg_data = {}
        if timestep in self.tx_bases:
            msg_data = self.tx_bases[timestep]

        message = {"timestep": timestep,
                   "type": "broadcast_tx_bases",
                   "data": msg_data}

        # self.broadcast("add_message", self.uid, message)
        self.cchl.add_message(self.uid, message)

    def broadcast_rx_bases(self, timestep):
        '''Broadcast the rx_bases on the classical channel.'''
        msg_data = {}
        if timestep in self.rx_bases:
            msg_data = self.rx_bases[timestep]

        message = {"timestep": self.timestep,
                   "type": "broadcast_rx_bases",
                   "data": msg_data}

        # self.broadcast("add_message", self.uid, message)
        self.cchl.add_message(self.uid, message)

    def add_bit_to_keys(self, uid):
        '''Add the bit from the current timestep to the keys for the given uid.'''
        # If the uid is in the rx_bits dictionary, then store the rx_bit value.
        if self.timestep in self.rx_bits:
            if uid in self.rx_bits[self.timestep]:
                bit = self.rx_bits[self.timestep][uid]
                self.store_value_in_dict(self.sifted_keys, uid, bit)

        # If the uid is contained in both rx_bits and tx_bits, then the rx bit
        # is overwritten by the tx bit.
        if self.timestep in self.tx_bits:
            if uid in self.tx_bits[self.timestep]:
                bit = self.tx_bits[self.timestep][uid]
                self.store_value_in_dict(self.sifted_keys, uid, bit)

        self.synch_sifted_and_secret_keys()

    def add_all_bits_to_keys(self):
        '''Extend the keys using the tx bits or rx bits from this timestep.'''
        # Update the secret key for each uid in the rx_bits dictionary.
        if self.timestep in self.rx_bits:
            for uid in self.rx_bits[self.timestep]:
                bit = self.rx_bits[self.timestep][uid]
                self.store_value_in_dict(self.sifted_keys, uid, bit)

        # If a uid is contained in both rx_bits and tx_bits, then the rx_bits
        # are overwritten by the tx_bits.
        if self.timestep in self.tx_bits:
            for uid in self.tx_bits[self.timestep]:
                bit = self.tx_bits[self.timestep][uid]
                self.store_value_in_dict(self.sifted_keys, uid, bit)

        self.synch_sifted_and_secret_keys()

    def synch_sifted_and_secret_keys(self):
        self.secret_keys = copy.deepcopy(self.sifted_keys)

    def broadcast(self, msg, *args):
        msg_func = getattr(self.cchl, msg)
        # print("{} broadcasting message {}".format(self.name, msg))
        return msg_func(*args)

    def add_check_bit(self, uid):
        '''If there is a bit in the current timestep of the sifted key for the
        party with the given UID, then use this bit as a check bit.'''
        if uid in self.sifted_keys[self.timestep]:
            # Use the bit from this timestep as a check bit.
            check_bit = self.sifted_keys[self.timestep][uid]
            # Store this bit in the check_bits dictionary.
            self.store_value_in_dict(self.check_bits, uid, check_bit)

    def remove_check_bits_from_secret_keys(self):
        '''Remove all check bits from the secret keys.'''
        # Remove check bits from the secret keys.
        for timestep in self.check_bits:
            if timestep in self.secret_keys:
                for uid in self.check_bits[timestep]:
                    if uid in self.secret_keys[timestep]:
                        self.secret_keys[timestep].pop(uid)

        # Remove any timesteps of the secret keys that are now empty.
        for timestep in list(self.secret_keys):
            if not self.secret_keys[timestep]:
                self.secret_keys.pop(timestep)

    def broadcast_check_bits(self):
        '''Broadcast all the check bits for every party and timestep.'''
        check_bits = copy.deepcopy(self.check_bits)
        message = {
            "timestep": self.timestep,
            "type": "broadcast_check_bits",
            "data": check_bits
        }
        self.cchl.add_message(self.uid, message)

    def receive_check_bits(self, sender_uid):
        '''Test for eavesdropping using the check bits.'''
        sender_check_bits = self.cchl.get_msg_check_bits(self.timestep,
                                                         sender_uid)

        # Check for eavesdropping by testing whether the check bits match for
        # every timestep.
        sender_check_bits_by_uid = shared_fns.reorder_by_uid(sender_check_bits)
        check_bits_by_uid = shared_fns.reorder_by_uid(self.check_bits)

        if (self.uid in sender_check_bits_by_uid and sender_uid in check_bits_by_uid
            and sender_check_bits_by_uid[self.uid] != check_bits_by_uid[sender_uid]):
            self.detected_eavesdropping = True

    def generate_flip_bit_instructions(self, comparison_uid):
        '''Work out which bits of the secret keys for each uid need to be
        flipped to match the secret key of the given uid.'''
        sks_by_uid = shared_fns.reorder_by_uid(self.secret_keys)
        comparison_sk = {}
        if comparison_uid in sks_by_uid:
            comparison_sk = sks_by_uid[comparison_uid]

        comparison_sk_timesteps = sorted(comparison_sk.keys())

        counts = {}
        flip_bit_instructions = {}
        for timestep in sorted(self.secret_keys):
            flip_bit_instructions[timestep] = {}
            for uid in self.secret_keys[timestep]:

                if uid not in counts:
                    counts[uid] = 0

                uid_sk_bit = self.secret_keys[timestep][uid]

                flip_bit_instr = False
                if counts[uid] < len(comparison_sk):
                    comparison_timestep = comparison_sk_timesteps[counts[uid]]
                    if uid_sk_bit != comparison_sk[comparison_timestep]:
                        flip_bit_instr = True

                flip_bit_instructions[timestep][uid] = flip_bit_instr
                counts[uid] += 1

        return flip_bit_instructions

    def broadcast_flip_bit_instructions(self, comparison_uid):
        '''Broadcast the flip bit instructions to match all the secret keys
        to the secret key corresponding to comparison_uid.'''
        # Work out which bits of the secret keys need to be flipped.
        flip_bit_instrs = self.generate_flip_bit_instructions(comparison_uid)
        # Flip the corresponding bits in this party's secret keys.
        self.flip_bits_of_secret_keys(flip_bit_instrs, self.uid)
        # Broadcast the flip bit instructions to the other parties.
        message = {
            "timestep": self.timestep,
            "type": "broadcast_flip_bit_instructions",
            "data": flip_bit_instrs
        }
        self.cchl.add_message(self.uid, message)

    def receive_flip_bit_instructions(self, sender_uid):
        '''Flip the bits of the secret key corresponding to sender_uid
        according to instructions retrieved from the classical channel.'''
        # Retrieve the flip bit instructions from the classical channel.
        flip_bit_instrs = self.cchl.get_flip_bit_instructions(self.timestep,
                                                              sender_uid)
        # Flip the bits of the sender's secret key as per the instructions.
        self.flip_bits_of_secret_keys(flip_bit_instrs, sender_uid)

    def flip_bits_of_secret_keys(self, flip_bit_instrs, sender_uid):
        '''Flip the bits of the secret keys according to the instructions sent
        by the party with UID sender_uid.'''
        for timestep in flip_bit_instrs:
            # If the instructions originate from this party, then apply them
            # to all of the secret keys for all the other parties.
            if sender_uid == self.uid:
                for uid in flip_bit_instrs[timestep]:
                    flip_bit = flip_bit_instrs[timestep][uid]
                    if flip_bit:
                        self.secret_keys[timestep][uid] ^= 1
            # If the instructions were sent by a different party, then extract
            # the instructions for this party (if they exist) and apply those.
            elif self.uid in flip_bit_instrs[timestep]:
                flip_bit = flip_bit_instrs[timestep][self.uid]
                if flip_bit and (sender_uid in self.secret_keys[timestep]):
                    self.secret_keys[timestep][sender_uid] ^= 1

    def get_minimum_key_length(self):
        '''Calculate the length of the shortest secret key.'''
        secret_keys_by_uid = shared_fns.reorder_by_uid(self.secret_keys)

        successors = self.network_manager.get_successors(self.uid)
        for successor in successors:
            if successor not in secret_keys_by_uid:
                return 0

        min_key_length = math.inf
        for uid in secret_keys_by_uid:
            secret_key_bits = list(secret_keys_by_uid[uid])
            key_length = len(secret_key_bits)
            if key_length < min_key_length:
                min_key_length = key_length

        return min_key_length

    def broadcast_key_length(self):
        '''Broadcast the length of the shortest secret key.'''
        key_length = self.get_minimum_key_length()
        self.truncate_secret_keys(key_length)
        message = {
            "timestep": self.timestep,
            "type": "broadcast_key_length",
            "data": key_length
        }
        self.cchl.add_message(self.uid, message)

    def receive_msg_key_length(self, sender_uid):
        '''Truncate the key corresponding to sender_uid to match the length
        specified in a message retrieved from the classical channel.'''
        secret_keys_by_uid = shared_fns.reorder_by_uid(self.secret_keys)
        if sender_uid in secret_keys_by_uid:
            # Retrieve the required key length from the classical channel.
            key_length = self.cchl.get_msg_key_length(self.timestep, sender_uid)
            # Truncate the secret key to the required key length.
            self.truncate_secret_keys(key_length, sender_uid)

    def truncate_secret_keys(self, key_length, sender_uid=None):
        '''Truncate all the secret keys to the given length.'''
        secret_keys_by_uid = shared_fns.reorder_by_uid(self.secret_keys)

        # If a sender_uid is given, then only truncate the key corresponding
        # to that UID.
        if sender_uid is not None:
            if sender_uid in secret_keys_by_uid:
                secret_keys_by_uid = {
                    sender_uid: secret_keys_by_uid[sender_uid]
                }
            else:
                raise KeyError(
                    ("Can't apply truncate_secret_keys: sender_uid {} is not "
                     "a valid key in the secret_keys dictionary for party {} "
                     "(\"{}\").").format(sender_uid, self.uid, self.name)
                )

        # Truncate the secret key(s).
        for uid in secret_keys_by_uid:
            # Work out which bits should be included in the secret key.
            included_timesteps = sorted(list(secret_keys_by_uid[uid]))
            if len(included_timesteps) > key_length:
                included_timesteps = included_timesteps[:key_length]
            # Truncate the secret key to the required key length.
            for timestep in self.secret_keys:
                if uid in self.secret_keys[timestep]:
                    if timestep not in included_timesteps:
                        self.secret_keys[timestep].pop(uid)

        # Clear any timesteps that are now empty.
        for timestep in list(self.secret_keys):
            if not self.secret_keys[timestep]:
                self.secret_keys.pop(timestep)


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
        initial_state = 1 / math.sqrt(2) * np.array([1] + [0] * (2**n - 2) + [1])
        return state.NQubitState(initial_state)

    def send_qubit(self, socket0, socket1):
        n_qubit_state = self.create_state()
        qubit0 = state.EntangledQubit(n_qubit_state, 0)
        qubit1 = state.EntangledQubit(n_qubit_state, 1)

        self.total_sent += 1

        socket0.receive(qubit0)
        # time.sleep(0.05)
        socket1.receive(qubit1)

