import numpy as np
import random
import time
import warnings
import math
import copy

import shared_fns
import state
import consts


class UIComponent:

    def next_timestep(self):
        '''Store the data from this timestep and set up for the next timestep.'''
        # Store the data from this timestep.
        self.store_timestep_data()
        # Reset all fields that should not persist between timesteps.
        self.reset_tstep_fields()
        # Increment the timestep counter.
        self.timestep += 1

    def get_stored_data_for_timestep(self, timestep):
        '''Retrieve the stored data for the given timestep.'''
        stored_data = {}
        if timestep in self.stored_data:
            stored_data = copy.deepcopy(self.stored_data[timestep])
        return stored_data


class QuantumChannel(UIComponent):

    def __init__(self):
        self.tx_device = None
        self.rx_device = None
        self.rx_device_socket_id = None
        self.intercepted = False
        self.reset()

    def reset(self):
        '''Reset the quantum channel to its configuration at timestep 0.'''
        self.timestep = 0
        self.tstep_state = None
        self.stored_data = {}

    def next_timestep(self):
        '''Store the data from this timestep and increment the timestep counter.'''
        # Store the state that was transmitted in this timestep.
        self.store_timestep_data()
        # Reset the current state field.
        self.reset_tstep_fields()
        # Increment the timestep counter.
        self.timestep += 1

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.stored_data[self.timestep] = {
            "state": self.tstep_state
        }

    def reset_tstep_fields(self):
        '''Reset all fields that should not persist past the current timestep.'''
        self.tstep_state = None

    def connect_tx_device(self, party):
        '''Connect a party to the transmitting end of the quantum channel.'''
        if self.tx_device is not None:
            raise ValueError("Transmitting party tx_device is already set.")
        self.tx_device = party

    def connect_rx_device(self, party, socket_id):
        '''Connect a party to the receiving end of the quantum channel.'''
        if self.rx_device is not None:
            raise ValueError("Receiving party rx_device is already set.")
        self.rx_device = party
        self.rx_device_socket_id = socket_id

    def disconnect_tx_device(self):
        '''Disconnect the current tx_device.'''
        self.tx_device = None

    def disconnect_rx_device(self):
        '''Disconnect the current rx_device.'''
        self.rx_device = None
        self.rx_device_socket_id = None

    def get_rx_device_socket_id(self):
        '''Retrieve the ID of the socket that the rx end of this qchl is connected to.'''
        return self.rx_device_socket_id

    def transmit(self, quantum_state):
        '''Transmit a quantum state from sender to target via the quantum channel.'''
        if not (isinstance(quantum_state, state.Qubit) or
                isinstance(quantum_state, state.NQubitState)):
            raise TypeError(("Can't transmit an object of type {} across a "
                             "quantum channel.").format(type(quantum_state)))
        # Save a copy of the quantum state as it is during transmission through
        # the quantum channel. (This is just so I can display it in the UI -
        # would not be possible in the real world!)
        self.tstep_state = state.NQubitState(quantum_state.coefficients)
        # Pass the quantum state to the intended recipient.
        if self.rx_device is not None:
            self.rx_device.receive(quantum_state, self.rx_device_socket_id)


class QuantumDevice:

    def __init__(self, uid):
        self.uid = uid
        self.tx_sockets = {}
        self.rx_sockets = {}
        self.rx_actions = {}

    def connect_tx_qchl(self, qchl, rx_uid):
        '''Connect this device to the tx end of the given qchl, which is (believed to be) connected to rx_uid.'''
        # Connect to the tx end of the qchl.
        qchl.connect_tx_device(self)
        # Store the qchl with the UID of the device that it is thought to
        # connect to (this may be inaccurate if the qchl is intercepted).
        self.tx_sockets[rx_uid] = qchl

    def connect_rx_qchl(self, qchl, tx_uid, actions=None):
        '''Connect this device to the rx end of the given qchl, which is (believed to be) connected to tx_uid.'''
        # Connect to the rx end of the qchl.
        qchl.connect_rx_device(self, tx_uid)
        # Store the qchl with the UID of the device that it is thought to
        # connect to (this may be inaccurate if the qchl is intercepted).
        self.rx_sockets[tx_uid] = qchl
        # Configure the default action that should be carried out when a state
        # is received at this socket.
        self.rx_actions[tx_uid] = {
            "measure": True,
            "meas_basis": consts.STD_BASIS,
            "forward": False,
            "forward_uid": None  # Socket ID
        }
        if actions is not None:
            self.rx_actions[tx_uid] = actions

    def update_rx_action(self, socket_id, action, value):
        self.rx_actions[socket_id][action] = value

    def generate_state(self, coeffs):
        '''Create a new state with the given coefficients.'''
        return state.NQubitState(coeffs)

    def generate_qubits(self, state_coeffs):
        '''Create a state and split it into its individual qubits.'''
        n_qubit_state = self.generate_state(state_coeffs)
        return n_qubit_state.split_into_qubits()

    def measure(self, quantum_state, operator):
        '''Measure the state using the given operator.'''
        return quantum_state.measure(operator)

    def transmit(self, quantum_state, rx_uid):
        '''Transmit the quantum state to rx_uid via a quantum channel.'''
        if rx_uid not in self.tx_sockets:
            raise KeyError(("Transmission from QKD device {} to QKD device {}"
                            " failed: the devices are not connected via a "
                            "quantum channel.").format(self.uid, rx_uid))

        self.tx_sockets[rx_uid].transmit(quantum_state)

    def receive(self, quantum_state, tx_uid):
        '''Receive a quantum state from the specified quantum channel.'''
        # Check that the socket ID is valid.
        if tx_uid not in self.rx_sockets:
            raise ValueError(("Quantum device {} received a quantum state "
                              "with an invalid socket ID."
                              ).format(self.uid))
        # Execute the actions that are configured for the socket ID
        # (i.e. measure and/or forward the state, or discard it).
        if self.rx_actions[tx_uid]["measure"]:
            meas_basis = self.rx_actions[tx_uid]["meas_basis"]
            self.measure(quantum_state, meas_basis)
        if self.rx_actions[tx_uid]["forward"]:
            forward_uid = self.rx_actions[tx_uid]["forward_uid"]
            self.transmit(quantum_state, forward_uid)


class Party(QuantumDevice, UIComponent):

    def __init__(self, uid, name, network_manager, cchl, is_eve=False):
        super().__init__(uid)
        self.name = name
        self.network_manager = network_manager
        self.cchl = cchl
        self.is_eve = is_eve
        self.reset()

    def reset(self):
        '''Reset the party to its configuration at timestep 0.'''
        self.timestep = 0

        # Record every interaction with a qubit.
        self.total_qstates_generated = 0
        self.total_qstates_transmitted = 0
        self.total_qstates_received = 0
        self.total_qstates_measured = 0
        self.total_qstates_forwarded = 0
        # Specify what the party should do when it receives a qubit state.
        self.measure_received_qstates = True
        self.forward_received_qstates = False

        # Store all the bases used for encoding and measurement of qubits.
        # Format: {time0: {uidA: basis, uidB: basis}, time1: {uidA: basis}, ...}
        # E.g. {0: {4: HAD, 7: STD}, 1: {}, 2: {4: STD}}
        self.tx_bases = {0: {}}
        self.rx_bases = {0: {}}

        # Store all the transmitted and received bits.
        # Format: {t0: {uidA: bit, uidB: bit}, t1: {uidA: bit}, ...}
        self.tx_bits = {0: {}}
        self.rx_bits = {0: {}}

        # Store the bits that are used in the keys. (Format same as tx_bits.)
        self.sifted_keys = {}
        self.check_bits  = {}
        self.secret_keys = {}

        # Track which channels of communication are known to be compromised.
        self.compromised_chls = []

        # Store the entire configuration of the party at each timestep.
        self.stored_data = {}

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.stored_data[self.timestep] = {
            # From quantum device
            "total_qstates_generated": self.total_qstates_generated,
            "total_qstates_transmitted": self.total_qstates_transmitted,
            "total_qstates_received": self.total_qstates_received,
            "total_qstates_measured": self.total_qstates_measured,
            "total_qstates_forwarded": self.total_qstates_forwarded,
            "measure_received_qstates": self.measure_received_qstates,
            "forward_received_qstates": self.forward_received_qstates,
            # From classical computer
            "tx_bases": copy.deepcopy(self.tx_bases),
            "rx_bases": copy.deepcopy(self.rx_bases),
            "tx_bits": copy.deepcopy(self.tx_bits),
            "rx_bits": copy.deepcopy(self.rx_bits),
            "sifted_keys": copy.deepcopy(self.sifted_keys),
            "check_bits": copy.deepcopy(self.check_bits),
            "secret_keys": copy.deepcopy(self.secret_keys),
            "compromised_chls": copy.deepcopy(self.compromised_chls)
        }

    def reset_tstep_fields(self):
        '''Reset all fields that should not persist past the current timestep.'''
        pass

    def choose_from(self, options):
        return random.choice(options)


    def generate_state(self, coeffs):
        '''Create a new state with the given coefficients.'''
        state = super().generate_state(coeffs)
        self.total_qstates_generated += 1
        return state

    def transmit(self, quantum_state, rx_uid):
        '''Transmit the quantum state to rx_uid via a quantum channel.'''
        super().transmit(quantum_state, rx_uid)
        self.total_qstates_transmitted += 1

    def send_state(self, bit, basis, rx_uid):
        '''Encode the given bit w.r.t. the given basis to generate a new state
        and transmit this state to the party with the specified uid.'''
        # Generate the state using the given bit and basis.
        state = self.generate_state(basis[bit])

        # Keep a record of the bit and basis used to generate the state.
        self.store_value_in_dict(self.tx_bases, rx_uid, basis)
        self.store_value_in_dict(self.tx_bits, rx_uid, bit)

        # Transmit the state to the target party.
        self.transmit(state, rx_uid)

    def measure(self, quantum_state, operator):
        '''Measure the state using the given operator.'''
        measured_value = super().measure(quantum_state, operator)
        self.total_qstates_measured += 1
        return measured_value

    def receive(self, qstate, tx_uid):
        '''Handle a received quantum state (measure it and/or forward it).'''
        bit, basis = (None, None)
        # Measure the quantum state.
        if self.rx_actions[tx_uid]["measure"]:
            basis = self.rx_actions[tx_uid]["meas_basis"]

            if basis is None:
                raise TypeError(("The measurement basis is set to None for "
                                 "Party {} (\"{}\"), so the received quantum "
                                 "state can't be measured.").format(self.uid,
                                                                    self.name))

            operator = shared_fns.get_measurement_operator([0, 1], basis)
            bit = self.measure(qstate, operator)

            # Keep a record of the measurement basis and the measured bit.
            self.store_value_in_dict(self.rx_bases, tx_uid, basis)
            self.store_value_in_dict(self.rx_bits, tx_uid, bit)

        # Forward the quantum state to the forwarding UID.
        # if self.forward_received_qstates:
        if self.rx_actions[tx_uid]["forward"]:
            # Store the basis and bit in the dictionary of tx_bases.
            # Note: If forwarding without measuring, then the basis and the
            # bit are both stored as None.
            forward_uid = self.rx_actions[tx_uid]["forward_uid"]
            self.store_value_in_dict(self.tx_bases, forward_uid, basis)
            self.store_value_in_dict(self.tx_bits, forward_uid, bit)
            # Forward the quantum state to the forward_uid.
            self.transmit(qstate, forward_uid)
            self.total_qstates_forwarded += 1

        self.total_qstates_received += 1

    def set_basis(self, tx_uid, basis):
        '''Measure the next quantum state from tx_uid w.r.t. the given basis.'''
        self.rx_actions[tx_uid]["measure"] = True
        self.rx_actions[tx_uid]["meas_basis"] = basis

    def forward(self, tx_uid, forward_uid):
        '''Forward received states from tx_uid to forward_uid.'''
        self.rx_actions[tx_uid]["forward"] = True
        self.rx_actions[tx_uid]["forward_uid"] = forward_uid

    def store_value_in_dict(self, d, key, val):
        '''Store the key, val pair in dictionary d[self.timestep].'''
        if self.timestep not in d:
            d[self.timestep] = {}

        d[self.timestep][key] = val

    ###########################################################################
    # CLASSICAL LOGIC
    ###########################################################################

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
        '''Update the secret keys to match the sifted keys.'''
        self.secret_keys = copy.deepcopy(self.sifted_keys)

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

        # Check for eavesdropping by testing whether the sender's check bits
        # match this party's check bits for every timestep.
        sender_check_bits = shared_fns.reorder_by_uid(sender_check_bits)
        own_check_bits = shared_fns.reorder_by_uid(self.check_bits)
        compromised = (
            self.uid in sender_check_bits and sender_uid in own_check_bits
            and sender_check_bits[self.uid] != own_check_bits[sender_uid]
        )
        if compromised:
            self.compromised_chls.append(sender_uid)


class ClassicalChannel(UIComponent):

    def __init__(self):
        self.reset()

    def reset(self):
        '''Reset the classical channel to its configuration at timestep 0.'''
        self.timestep = 0
        self.tstep_messages = {}
        self.stored_data = {}

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.stored_data = {
            "tstep_messages": copy.deepcopy(self.tstep_messages)
        }

    def reset_tstep_fields(self):
        '''Reset all fields that should not persist past the current timestep.'''
        self.tstep_messages = {}

    ###########################################################################
    # MESSAGE PROCESSING METHODS
    ###########################################################################

    # TODO make a single, generic message retrieval method
    # Note that get_tx_bases and get_rx_bases are currently structured slightly
    # differently from the other message retrieval methods. Is this necessary?

    def get_tx_bases(self, timestep):
        '''Retrieve all messages of type "broadcast_tx_bases" for the given timestep.'''
        tx_bases = {}
        for tx_uid in self.tstep_messages:
            for msg in self.tstep_messages[tx_uid]:
                if msg["type"] == "broadcast_tx_bases":
                    if msg["timestep"] == timestep:
                        tx_bases[tx_uid] = msg["data"]
        return tx_bases

    def get_rx_bases(self, timestep):
        '''Retrieve all messages of type "broadcast_rx_bases" for the given timestep.'''
        rx_bases = {}
        for rx_uid in self.tstep_messages:
            for msg in self.tstep_messages[rx_uid]:
                if msg["type"] == "broadcast_rx_bases":
                    if msg["timestep"] == timestep:
                        rx_bases[rx_uid] = msg["data"]
        return rx_bases

    def get_msg_check_bits(self, timestep, sender_uid):
        '''Retrieve all messages of type "broadcast_check_bits" for the given timestep.'''
        check_bits = {}
        if sender_uid in self.tstep_messages:
            for msg in self.tstep_messages[sender_uid]:
                if msg["type"] == "broadcast_check_bits":
                    if msg["timestep"] == timestep:
                        check_bits = msg["data"]
        return check_bits

    def get_flip_bit_instructions(self, timestep, sender_uid):
        '''Retrieve a message from sender_uid of type "broadcast_flip_bit_instructions" for the given timestep.'''
        flip_bit_instrs = {}
        if sender_uid in self.tstep_messages:
            for msg in self.tstep_messages[sender_uid]:
                if msg["type"] == "broadcast_flip_bit_instructions":
                    if msg["timestep"] == timestep:
                        flip_bit_instrs = msg["data"]
        return flip_bit_instrs

    def get_msg_key_length(self, timestep, sender_uid):
        key_length = math.inf
        if sender_uid in self.tstep_messages:
            for msg in self.tstep_messages[sender_uid]:
                if msg["type"] == "broadcast_key_length":
                    if msg["timestep"] == timestep:
                        key_length = msg["data"]
        return key_length

    ###########################################################################
    # CLASSICAL COMMUNICATION METHODS
    ###########################################################################

    def add_message(self, sender_uid, message):
        '''Add a message from sender_uid to the classical channel.'''
        if sender_uid not in self.tstep_messages:
            self.tstep_messages[sender_uid] = []
        self.tstep_messages[sender_uid].append(message)

