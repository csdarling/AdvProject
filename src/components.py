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
            "forward_id": None  # Socket ID
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
            forward_id = self.rx_actions[tx_uid]["forward_id"]
            self.transmit(quantum_state, forward_id)


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
        self.qstate_forwarding_uid = None

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

        # Fields that don't persist between timesteps.
        self.tstep_rx_bases = {}  # E.g. {uidA: HAD, uidB: STD}
        self.tstep_tx_uid = None

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
            "qstate_forwarding_uid": self.qstate_forwarding_uid,
            # From classical computer
            "tx_bases": copy.deepcopy(self.tx_bases),
            "rx_bases": copy.deepcopy(self.rx_bases),
            "tx_bits": copy.deepcopy(self.tx_bits),
            "rx_bits": copy.deepcopy(self.rx_bits),
            "sifted_keys": copy.deepcopy(self.sifted_keys),
            "check_bits": copy.deepcopy(self.check_bits),
            "secret_keys": copy.deepcopy(self.secret_keys),
            "compromised_chls": copy.deepcopy(self.compromised_chls),
            "tstep_rx_bases": copy.deepcopy(self.tstep_rx_bases),
            "tstep_tx_uid": self.tstep_tx_uid,
        }

    def reset_tstep_fields(self):
        '''Reset all fields that should not persist past the current timestep.'''
        self.tstep_rx_bases = {}
        self.tstep_tx_uid = None

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
        if self.measure_received_qstates:
            sender_uid = self.tstep_tx_uid
            basis = self.tstep_rx_bases[sender_uid]
            self.tstep_rx_bases[sender_uid] = None

            if basis is None:
                raise TypeError(("The measurement basis is set to None for "
                                 "Party {} (\"{}\"), so the received quantum "
                                 "state can't be measured.").format(self.uid,
                                                                    self.name))

            operator = shared_fns.get_measurement_operator([0, 1], basis)
            bit = self.measure(qstate, operator)

            # Keep a record of the measurement basis and the measured bit.
            self.store_value_in_dict(self.rx_bases, sender_uid, basis)
            self.store_value_in_dict(self.rx_bits, sender_uid, bit)

        # Forward the quantum state to the qstate_forwarding_uid.
        # if self.forward_received_qstates:
        if self.rx_actions[tx_uid]["forward"]:
            # Store the basis and bit in the dictionary of tx_bases.
            # Note: If forwarding without measuring, then the basis and the
            # bit are both stored as None.
            forward_id = self.rx_actions[tx_uid]["forward_id"]
            self.store_value_in_dict(self.tx_bases,
                                     # self.qstate_forwarding_uid,
                                     forward_id,
                                     basis)
            self.store_value_in_dict(self.tx_bits,
                                     # self.qstate_forwarding_uid,
                                     forward_id,
                                     bit)
            # Forward the quantum state to the qstate_forwarding_uid.
            # self.transmit(qstate, self.qstate_forwarding_uid)
            self.transmit(qstate, forward_id)
            self.total_qstates_forwarded += 1

        self.total_qstates_received += 1


    def expect_tx_from(self, tx_uid):
        '''Note that tx_uid is about to send a quantum state to this party.'''
        self.tstep_tx_uid = tx_uid

    def measure_wrt(self, basis):
        '''Measure the next quantum state from tstep_tx_uid w.r.t. the given basis.'''
        sender_uid = self.tstep_tx_uid
        self.tstep_rx_bases[sender_uid] = basis
        self.measure_received_qstates = True

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

    def broadcast_TODO_unused(self, msg, *args):
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


class PartyTODODelete(UIComponent, QuantumDevice):

    def __init__(self, uid, name, network_manager, cchl, is_eve=False):
        self.uid = uid
        self.name = name
        self.network_manager = network_manager
        self.cchl = cchl
        # self.is_eve = is_eve
        self.tx_qchls = {}
        self.rx_qchls = {}
        self.reset()
        super().__init__()

    def reset(self):
        '''Reset the party to its configuration at timestep 0.'''
        self.timestep = 0

        # Record every interaction with a qubit.
        # self.total_qubits_generated = 0
        self.total_states_generated = 0
        self.total_qubits_transmitted = 0
        self.total_qubits_received = 0
        self.total_qubits_measured = 0
        self.total_qubits_forwarded = 0
        # Specify what the party should do when it receives a qubit state.
        self.measure_received_qubits = True
        self.forward_received_qubits = False
        self.qubit_forwarding_uid = None

        # Store all the bases used for encoding and measurement of qubits.
        # Format: {time0: {uidA: basis, uidB: basis}, time1: {uidA: basis}, ...}
        # E.g. {0: {4: HAD, 7: STD}, 1: {}, 2: {4: STD}}
        self.tx_bases = {}
        self.rx_bases = {}
        # Store all the transmitted and received bits.
        # Format: {t0: {uidA: bit, uidB: bit}, t1: {uidA: bit}, ...}
        self.tx_bits = {}
        self.rx_bits = {}
        # Store the bits that are used in the keys. (Format same as tx_bits.)
        self.sifted_keys = {}
        self.check_bits  = {}
        self.secret_keys = {}
        # Track which channels of communication are known to be compromised.
        self.compromised_chls = []
        # Fields that don't persist between timesteps.
        self.tstep_rx_bases = {}  # E.g. {uidA: HAD, uidB: STD}
        self.tstep_tx_uid = None
        # Store the entire configuration of the party at each timestep.
        self.stored_data = {}

    ###########################################################################
    # UICOMPONENT METHODS
    ###########################################################################

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.stored_data[self.timestep] = {
            # From quantum device
            # "total_qubits_generated": self.total_qubits_generated,
            "total_qubits_transmitted": self.total_qubits_transmitted,
            "total_qubits_received": self.total_qubits_received,
            "measure_received_qubits": self.measure_received_qubits,
            "forward_received_qubits": self.forward_received_qubits,
            "qubit_forwarding_uid": self.qubit_forwarding_uid,
            # From classical computer
            "tx_bases": copy.deepcopy(self.tx_bases),
            "rx_bases": copy.deepcopy(self.rx_bases),
            "tx_bits": copy.deepcopy(self.tx_bits),
            "rx_bits": copy.deepcopy(self.rx_bits),
            "sifted_keys": copy.deepcopy(self.sifted_keys),
            "check_bits": copy.deepcopy(self.check_bits),
            "secret_keys": copy.deepcopy(self.secret_keys),
            "compromised_chls": copy.deepcopy(self.compromised_chls),
            "tstep_rx_bases": copy.deepcopy(self.tstep_rx_bases),
            "tstep_tx_uid": self.tstep_tx_uid,
        }

    def reset_tstep_fields(self):
        '''Reset all fields that should not persist past the current timestep.'''
        self.tstep_rx_bases = {}
        self.tstep_tx_uid = None

    ###########################################################################
    # QUANTUM LOGIC
    ###########################################################################

    def connect_tx_qchl(self, qchl, rx_uid):
        '''Connect this party to the tx end of the given qchl, which is (believed to be) connected to rx_uid.'''
        # Connect to the tx end of the qchl.
        qchl.connect_tx_party(self)
        # Store the qchl with the UID of the party that it is thought to
        # connect to (this may be inaccurate if the qchl is intercepted).
        self.tx_qchls[rx_uid] = qchl

    def connect_rx_qchl(self, qchl, tx_uid):
        '''Connect this party to the rx end of the given qchl, which is (believed to be) connected to tx_uid.'''
        # Connect to the rx end of the qchl.
        qchl.connect_rx_party(self)
        # Store the qchl with the UID of the party that it is thought to
        # connect to (this may be inaccurate if the qchl is intercepted).
        self.rx_qchls[tx_uid] = qchl

    def generate_qubit(self, bit, basis):
        '''Create a new qubit representing the given bit and basis.'''
        initial_state = np.linalg.eigh(basis)[1][bit]
        qubit = state.NQubitState(initial_state)
        self.total_qubits_generated += 1
        return qubit

    def measure_qubit(self, qubit_state, basis):
        '''Measure the state w.r.t. the given basis.'''
        measured_value = qubit_state.measure(basis)
        self.total_qubits_measured += 1
        return measured_value

    def transmit_qubit(self, target_uid, qubit_state):
        '''Transmit the qubit to the target_uid via a quantum channel.'''
        if target_uid not in self.tx_qchls:
            raise KeyError(("Qubit transmission from party {} to party {} "
                            "failed: the parties are not connected via a "
                            "quantum channel.").format(self.uid, target_uid))

        self.tx_qchls[target_uid].transmit(qubit_state)
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
        bit, basis = (None, None)
        # Measure the qubit.
        if self.measure_received_qubits:
            sender_uid = self.tstep_tx_uid
            basis = self.tstep_rx_bases[sender_uid]
            self.tstep_rx_bases[sender_uid] = None

            if basis is None:
                raise TypeError(("The measurement basis is set to None for "
                                 "Party {} (\"{}\"), so the received qubit "
                                 "can't be measured.").format(self.uid,
                                                              self.name))

            bit = self.measure_qubit(qubit, basis)

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
            self.total_qubits_forwarded += 1

        self.total_qubits_received += 1

    def next_qubit_is_from(self, tx_uid):
        '''Note that party tx_uid is about to send a qubit to this party.'''
        self.tstep_tx_uid = tx_uid

    def measure_next_qubit_wrt(self, basis):
        '''Measure the next qubit from tstep_tx_uid w.r.t. the given basis.'''
        sender_uid = self.tstep_tx_uid
        self.tstep_rx_bases[sender_uid] = basis
        self.measure_received_qubits = True

    def forward_qubits_to(self, uid):
        '''Forward received qubits to the given UID.'''
        self.qubit_forwarding_uid = uid
        self.forward_received_qubits = True

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

    def broadcast_TODO_unused(self, msg, *args):
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

    ###########################################################################
    # OTHER METHODS
    ###########################################################################

    def store_value_in_dict(self, d, key, val):
        '''Store the key, val pair in dictionary d[self.timestep].'''
        if self.timestep not in d:
            d[self.timestep] = {}

        d[self.timestep][key] = val


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


# class EPRPairSource:

#     def __init__(self):
#         self.reset()

#     def reset(self):
#         self.total_sent = 0

#     def create_state(self, n=2):
#         initial_state = 1 / math.sqrt(2) * np.array([1] + [0] * (2**n - 2) + [1])
#         return state.NQubitState(initial_state)

#     def send_qubit(self, party0, party1):
#         n_qubit_state = self.create_state()
#         qubit0 = state.EntangledQubit(n_qubit_state, 0)
#         qubit1 = state.EntangledQubit(n_qubit_state, 1)

#         self.total_sent += 1

#         party0.receive_qubit(qubit0)
#         party1.receive_qubit(qubit1)

