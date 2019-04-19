import networkx as nx
import numpy as np
import random
import string
import time
import copy
import math

import components
import shared_fns
import consts

from pprint import pprint

party_names = string.ascii_uppercase[:4] + string.ascii_uppercase[5:]

class UIComponent:

    def __init__(self):
        self.reset()
        self.ui_in_replay_mode = True

    def reset(self):
        self.ui_timestep = 0
        self.ui_stored_data = {}

    def ui_tick(self, data={}):
        '''Store the data and progress to the next timestep.'''
        if not self.ui_in_replay_mode:
            self.ui_stored_data[self.ui_timestep] = data

        next_timestep = self.ui_timestep + 1
        if next_timestep not in self.ui_stored_data:
            self.log[next_timestep] = {}
            self.ui_in_replay_mode = False

        self.ui_timestep += 1

    def ui_toggle_replay(self):
        self.ui_in_replay_mode = not self.ui_in_replay_mode

    def ui_rewind_to_timestep(self, timestep):
        if timestep in self.ui_stored_data:
            # If not in replay mode, then only keep the stored data up to the
            # specified timestep.
            if not self.ui_in_replay_mode:
                ui_stored_data = {}
                for t in range(timestep):
                    ui_stored_data[t] = self.ui_stored_data[t]
                self.ui_stored_data = ui_stored_data
            self.ui_timestep = timestep


class KPartyBB84:

    def __init__(self, k=None, edges=None, protocol=2, animation=True, check_bit_prob=0.2):
        self.cchl = ClassicalChannel()
        self.set_protocol(protocol, k, edges, animation, check_bit_prob)
        self.timestep = 0

    def reset(self):
        self.network_manager.reset()
        self.cchl.reset()
        self.timestep = 0
        self.running_protocol = True

    def set_protocol(self, protocol, k=None, edges=None, animation=True, check_bit_prob=0.2):
        '''Choose which protocol to run.'''
        if k is None and edges is None:
            # TODO Raise a more precise type of exception.
            raise Exception("Either k or edges must be specified.")

        # If k is not set then it defaults to the maximum node uid in edges.
        if k is None:
            k = max([max((a, b) for a, b in edges)])

        # Chained BB84 Protocol
        if protocol == 0:
            self.protocol = self.chained_protocol
            # If edges has not been specified, then set it to default chain.
            if edges is None:
                edges = [(i, i + 1) for i in range(k - 1)]

        # Star Graph BB84 Protocol 1
        elif protocol == 1:
            self.protocol = self.star_graph_protocol_1
            # If edges has not been specified, then set it to default star.
            if edges is None:
                edges = [(0, i + 1) for i in range(k - 1)]

        # Star Graph BB84 Protocol 2
        elif protocol == 2:
            self.protocol = self.star_graph_protocol_2
            # If edges has not been specified, then set it to default star.
            if edges is None:
                edges = [(0, i + 1) for i in range(k - 1)]

        else:
            # TODO Add an error message.
            raise NotImplementedError()

        self.network_manager = NetworkManager(self.cchl, edges)
        self.protocol_params = {"animation": animation,
                                "check_bit_prob": check_bit_prob}
        self.running_protocol = True

    def chained_protocol(self, animation=True, check_bit_prob=0.2):
        '''Run the chained BB84 protocol.'''
        # TODO Check that the given network is actually a chain, i.e. that
        # every party has exactly one predecessor (except for the party at the
        # start of the chain, which has none) and one successor (except for
        # the party at the end of the chain, which has none).
        protocol_secure = True
        parties = self.network_manager.get_parties()

        # Find the uid of the first party in the chain.
        first_party_uid = None
        for uid in parties:
            predecessors = self.network_manager.get_predecessors(uid)
            if not predecessors:
                first_party_uid = uid
                break

        if first_party_uid is None:
            # TODO Raise a more precise type of exception.
            raise Exception("The chain must have a first party.")

        # Set a random measurement basis for each receiving party
        # (i.e. every party except the first party in the chain).
        for uid in parties:
            if uid != first_party_uid:
                # Choose randomly between the standard and Hadamard bases.
                basis = random.choice([consts.STANDARD_BASIS,
                                       consts.HADAMARD_BASIS])
                # Record that the next qubit received by this party should be
                # measured w.r.t. this basis.
                predecessor_uid = self.network_manager.get_predecessors(uid)[0]
                parties[uid].next_qubit_is_from(predecessor_uid)
                parties[uid].measure_next_qubit_wrt(basis)
                # After measurement, the qubit should be forwarded to the next
                # party in the chain.
                successors = self.network_manager.get_successors(uid)
                if successors:
                    successor_uid = successors[0]
                    parties[uid].forward_qubits_to(successor_uid)

        # The first party in the chain generates a qubit using a random bit
        # and a random basis, and transmits it to the next party in the chain.
        first_party = parties[first_party_uid]
        bit = random.choice([0, 1])
        basis = random.choice([consts.STANDARD_BASIS, consts.HADAMARD_BASIS])
        successors = self.network_manager.get_successors(first_party_uid)
        if not successors:
            # TODO Raise a more precise type of exception.
            raise Exception("The first party in the chain doesn't have a successor.")
        successor_uid = successors[0]
        first_party.send_qubit(successor_uid, bit, basis)

        # Each party publicly announces the basis it used.
        first_party.broadcast_tx_bases(self.timestep)
        for uid in parties:
            if uid != first_party_uid:
                parties[uid].broadcast_rx_bases(self.timestep)

        # Check whether all the parties used the same basis.
        tx_bases = self.cchl.get_tx_bases(self.timestep)
        rx_bases = self.cchl.get_rx_bases(self.timestep)
        first_party_tx_basis = tx_bases[first_party_uid][successor_uid]

        bases_match = True
        for rx_uid in rx_bases:
            measurement_bases = rx_bases[rx_uid]
            for tx_uid in measurement_bases:
                meas_basis = measurement_bases[tx_uid]
                if not np.allclose(meas_basis, first_party_tx_basis):
                    bases_match = False
                    break
            if not bases_match:
                break

        # If all the bases match, then add the bit to the sifted key.
        if bases_match:
            for uid in parties:
                parties[uid].add_all_bits_to_keys()

            # If running as an animation, then the sifted key bits from this
            # timestep are used as check bits with probability check_bit_prob.
            if animation:
                random_num = random.random()
                if random_num < check_bit_prob:
                    # Add the current bit to the check bits.
                    for uid in parties:
                        successors = self.network_manager.get_successors(uid)
                        predecessors = self.network_manager.get_predecessors(uid)
                        if predecessors:
                            parties[uid].add_check_bit(predecessors[0])
                        if successors:
                            parties[uid].add_check_bit(successors[0])

                    # Each party broadcasts all of their check bits and tests
                    # for eavesdropping.
                    for uid in parties:
                        # This party broadcasts its check bits.
                        parties[uid].broadcast_check_bits()
                        predecessors = self.network_manager.get_predecessors(uid)
                        if predecessors:
                            predecessor_uid = predecessors[0]
                            # This party retrieves its predecessor's check bits
                            # from the cchl and tests for eavesdropping.
                            parties[uid].receive_check_bits(predecessor_uid)
                            # The predecessor retrieves this party's check bits
                            # from the cchl and tests for eavesdropping.
                            parties[predecessor_uid].receive_check_bits(uid)

                        # If the party has detected eavesdropping, then abort
                        # the run of the protocol.
                        if parties[uid].detected_eavesdropping:
                            print("\nEavesdropping detected!\n")
                            protocol_secure = False
                            return protocol_secure

        # Remove all check bits from the secret keys.
        for uid in parties:
            parties[uid].synch_sifted_and_secret_keys()
            parties[uid].remove_check_bits_from_secret_keys()

        return protocol_secure

    def star_graph_protocol_1(self, animation=True, check_bit_prob=0.2):
        '''Run BB84 Star Graph Protocol 1.'''
        # TODO Check that the given network is a star graph.
        protocol_secure = True
        parties = self.network_manager.get_parties()

        # Find the uid of the protocol leader.
        leader_uid = None
        for uid in parties:
            is_leader = True
            successors = self.network_manager.get_successors(uid)
            for other_uid in parties:
                if other_uid != uid:
                    if other_uid not in successors:
                        is_leader = False
                        break
            if is_leader:
                leader_uid = uid

        if leader_uid is None:
            # Raise a more precise type of exception.
            raise Exception("The given network doesn't have a leader.")

        # Set a random measurement basis for each receiving party
        # (i.e. every party except the leader).
        for uid in parties:
            if uid != leader_uid:
                basis = random.choice([consts.STANDARD_BASIS,
                                       consts.HADAMARD_BASIS])
                parties[uid].next_qubit_is_from(leader_uid)
                parties[uid].measure_next_qubit_wrt(basis)

        # The leader generates and transmits a qubit for each of the other
        # parties using different random bits and bases.
        leader = parties[leader_uid]
        successors = self.network_manager.get_successors(leader_uid)
        for successor_uid in successors:
            bit = random.choice([0, 1])
            basis = random.choice([consts.STANDARD_BASIS,
                                   consts.HADAMARD_BASIS])
            leader.send_qubit(successor_uid, bit, basis)

        # Each party publicly announces the basis it used.
        leader.broadcast_tx_bases(self.timestep)
        for uid in parties:
            if uid != leader_uid:
                parties[uid].broadcast_rx_bases(self.timestep)

        # Check whether each party measured w.r.t. the same basis that the
        # leader used in the generation of its qubit.
        tx_bases = self.cchl.get_tx_bases(self.timestep)
        rx_bases = self.cchl.get_rx_bases(self.timestep)

        bases_match = True
        for rx_uid in tx_bases[leader_uid]:
            tx_basis = tx_bases[leader_uid][rx_uid]
            rx_basis = rx_bases[rx_uid][leader_uid]
            if not np.allclose(tx_basis, rx_basis):
                bases_match = False
                break

        # If all the bases pairs match, then add the bit to the sifted key.
        if bases_match:
            for uid in parties:
                parties[uid].add_all_bits_to_keys()

            # If running as an animation, then the sifted key bits from this
            # timestep are used as check bits with probability check_bit_prob.
            if animation:
                random_num = random.random()
                if random_num < check_bit_prob:
                    # Add the current bit to the check bits.
                    for uid in successors:
                        leader.add_check_bit(uid)
                        parties[uid].add_check_bit(leader_uid)

                    # The parties with matching bases broadcast all of their
                    # check bits and test for eavesdropping.
                    leader.broadcast_check_bits()
                    for uid in successors:
                        parties[uid].receive_check_bits(leader_uid)
                        parties[uid].broadcast_check_bits()
                        leader.receive_check_bits(uid)
                        if leader.detected_eavesdropping:
                            print("\nEavesdropping detected!\n")
                            protocol_secure = False
                            return protocol_secure

        # Remove all check bits from the secret keys.
        for uid in parties:
            parties[uid].remove_check_bits_from_secret_keys()

        # The protocol leader, who knows all of the secret keys, broadcasts
        # instructions about which bits of which keys need to be flipped so
        # that all of the parties share the same secret key.
        leader.broadcast_flip_bit_instructions(successors[0])
        for uid in successors:
            parties[uid].receive_flip_bit_instructions(leader_uid)

        return protocol_secure

    def star_graph_protocol_2(self, animation=True, check_bit_prob=0.2):
        '''Run BB84 Star Graph Protocol 2.'''
        # TODO Check that the given network is a star graph.
        protocol_secure = True
        parties = self.network_manager.get_parties()

        # Find the uid of the protocol leader.
        leader_uid = None
        for uid in parties:
            is_leader = True
            successors = self.network_manager.get_successors(uid)
            for other_uid in parties:
                if other_uid != uid:
                    if other_uid not in successors:
                        is_leader = False
                        break
            if is_leader:
                leader_uid = uid

        if leader_uid is None:
            # Raise a more precise type of exception.
            raise Exception("The given network doesn't have a leader.")

        # Set a random measurement basis for each receiving party
        # (i.e. every party except the leader).
        for uid in parties:
            if uid != leader_uid:
                basis = random.choice([consts.STANDARD_BASIS,
                                       consts.HADAMARD_BASIS])
                parties[uid].next_qubit_is_from(leader_uid)
                parties[uid].measure_next_qubit_wrt(basis)

        # The leader generates and transmits a qubit for each of the other
        # parties using different random bits and bases.
        leader = parties[leader_uid]
        successors = self.network_manager.get_successors(leader_uid)
        for uid in successors:
            bit = random.choice([0, 1])
            basis = random.choice([consts.STANDARD_BASIS,
                                   consts.HADAMARD_BASIS])
            leader.send_qubit(uid, bit, basis)

        # Each party publicly announces the basis it used.
        leader.broadcast_tx_bases(self.timestep)
        for uid in successors:
            parties[uid].broadcast_rx_bases(self.timestep)

        # Check whether each party measured w.r.t. the same basis that the
        # leader used in the generation of its qubit.
        tx_bases = self.cchl.get_tx_bases(self.timestep)
        rx_bases = self.cchl.get_rx_bases(self.timestep)
        rx_uids_with_correct_basis = []
        for rx_uid in tx_bases[leader_uid]:
            tx_basis = tx_bases[leader_uid][rx_uid]
            rx_basis = rx_bases[rx_uid][leader_uid]
            if np.allclose(tx_basis, rx_basis):
                rx_uids_with_correct_basis.append(rx_uid)

        # If any of the basis pairs match, then add the bit to the sifted key.
        if rx_uids_with_correct_basis:
            for uid in successors:
                if uid in rx_uids_with_correct_basis:
                    leader.add_bit_to_keys(uid)
                    parties[uid].add_bit_to_keys(leader_uid)
                else:
                    parties[uid].synch_sifted_and_secret_keys()

        # If running as an animation, then the sifted key bits from this
        # timestep are used as check bits with probability check_bit_prob.
        if animation:
            random_num = random.random()
            if random_num < check_bit_prob:
                # Add the current bit to the check bits.
                for uid in rx_uids_with_correct_basis:
                    leader.add_check_bit(uid)
                    parties[uid].add_check_bit(leader_uid)

                # The parties with matching bases broadcast all of their check
                # bits and test for eavesdropping.
                if rx_uids_with_correct_basis:
                    leader.broadcast_check_bits()
                for uid in rx_uids_with_correct_basis:
                    parties[uid].receive_check_bits(leader_uid)
                    parties[uid].broadcast_check_bits()
                    leader.receive_check_bits(uid)
                    if leader.detected_eavesdropping:
                        print("\nEavesdropping detected!\n")
                        protocol_secure = False
                        return protocol_secure

        # Remove all check bits from the secret keys.
        for uid in parties:
            parties[uid].remove_check_bits_from_secret_keys()

        # The protocol leader, who knows all of the secret keys, broadcasts
        # instructions about which bits of which keys need to be flipped so
        # that all of the parties share the same secret key.
        leader.broadcast_flip_bit_instructions(successors[0])
        for uid in successors:
            parties[uid].receive_flip_bit_instructions(leader_uid)

        # Currently, the secret keys for each party may be different lengths.
        # The protocol leader broadcasts the shortest of these lengths and all
        # parties truncate their secret keys to this length.
        leader.broadcast_key_length()
        for uid in successors:
            parties[uid].receive_msg_key_length(leader_uid)

        return protocol_secure

    def run_one_step(self, display_data=True):
        '''Run one iteration of the protocol.'''
        if self.running_protocol:
            protocol_secure = self.protocol(**self.protocol_params)
            self.running_protocol = protocol_secure

            if display_data:
                self.display_data()

            if protocol_secure:
                self.timestep += 1
                self.cchl.timestep += 1
                parties = self.network_manager.get_parties()
                for uid in parties:
                    parties[uid].timestep += 1

    def run_n_steps(self, n, display_bits=True):
        '''Run n iterations of the protocol.'''
        count = 0
        while self.running_protocol and count < n:
            self.run_one_step(display_data=False)
            count += 1
        self.display_data(display_bits)

    def run(self):
        pass

    def calculate_qubit_counts(self):
        '''
        Sum the qubit counts for all the parties in the network.

        Calculate how many qubits have been generated, transmitted and
        received in total across the entire network.

        :return: a tuple of the three qubit totals
        '''
        total_qubits_generated = 0
        total_qubits_transmitted = 0
        total_qubits_received = 0

        parties = self.network_manager.get_parties()
        for party_uid in parties:
            party = parties[party_uid]
            total_qubits_generated += party.total_qubits_generated
            total_qubits_transmitted += party.total_qubits_transmitted
            total_qubits_received += party.total_qubits_received

        return (total_qubits_generated,
                total_qubits_transmitted,
                total_qubits_received)

    def display_data(self, display_bits=True):
        '''Print the protocol data to the terminal.'''
        parties = self.network_manager.get_parties()
        qubit_counts = self.calculate_qubit_counts()

        print("Protocol iterations: {}".format(self.timestep))
        print("Generated qubits:    {}".format(qubit_counts[0]))
        print("Transmitted qubits:  {}".format(qubit_counts[1]))
        print("Received qubits:     {}".format(qubit_counts[2]))

        min_key_length = math.inf
        for uidA in parties:
            partyA = parties[uidA]
            secret_keys = partyA.secret_keys
            if not secret_keys:
                min_key_length = 0
                break
            secret_keys_by_uid = shared_fns.reorder_by_uid(secret_keys)
            for uidB in secret_keys_by_uid:
                key_length = len(list(secret_keys_by_uid[uidB]))
                if key_length < min_key_length:
                    min_key_length = key_length

        print("Secret key length:   {}".format(min_key_length))

        if not display_bits:
            return

        # Display the tx/rx bits & bases for each party.
        for uidA in parties:
            partyA = parties[uidA]
            # Display the tx bits & bases, if they exist.
            if partyA.tx_bits:
                print("\nParty {} (tx)".format(partyA.name))
                tx_bits = shared_fns.reorder_by_uid(partyA.tx_bits)
                tx_bases = shared_fns.reorder_by_uid(partyA.tx_bases)
                tx_bits_str = shared_fns.convert_dod_to_dos(tx_bits)
                tx_bases_chars = shared_fns.represent_bases_by_chars(tx_bases)
                tx_bases_str = shared_fns.convert_dod_to_dos(tx_bases_chars)

                for uidB in tx_bits:
                    partyB = parties[uidB]
                    partyB_tx_bits_str = tx_bits_str[uidB]
                    partyB_tx_bases_str = tx_bases_str[uidB]

                    print("    {} -> {}:  {}".format(partyA.name,
                                                     partyB.name,
                                                     partyB_tx_bits_str))

                    print("             {}".format(partyB_tx_bases_str))

            # Display the rx bits & bases, if they exist.
            if partyA.rx_bits:
                print("\nParty {} (rx)".format(partyA.name))
                rx_bits = shared_fns.reorder_by_uid(partyA.rx_bits)
                rx_bases = shared_fns.reorder_by_uid(partyA.rx_bases)
                rx_bits_str = shared_fns.convert_dod_to_dos(rx_bits)
                rx_bases_chars = shared_fns.represent_bases_by_chars(rx_bases)
                rx_bases_str = shared_fns.convert_dod_to_dos(rx_bases_chars)

                for uidB in rx_bits:
                    partyB = parties[uidB]
                    partyB_rx_bits_str = rx_bits_str[uidB]
                    partyB_rx_bases_str = rx_bases_str[uidB]

                    print("    {} -> {}:  {}".format(partyB.name,
                                                     partyA.name,
                                                     partyB_rx_bits_str))

                    print("             {}".format(partyB_rx_bases_str))

        # Display the sifted keys.
        print("\n")
        for uidA in parties:
            partyA = parties[uidA]
            sifted_keys = partyA.sifted_keys
            sifted_keys_by_uid = shared_fns.reorder_by_uid(sifted_keys)
            sifted_key_strs = shared_fns.convert_dod_to_dos(sifted_keys_by_uid)
            for uidB in sifted_keys_by_uid:
                partyB = parties[uidB]
                print("{} <-> {} key: {}".format(partyA.name,
                                                 partyB.name,
                                                 sifted_key_strs[uidB]))

        # Display the check bits.
        first_line = True
        for uidA in parties:
            partyA = parties[uidA]
            check_bits = partyA.check_bits
            check_bits_by_uid = shared_fns.reorder_by_uid(check_bits)
            check_bits_strs = shared_fns.convert_dod_to_dos(check_bits_by_uid)
            for uidB in check_bits_by_uid:
                check_bits_exist = True
                partyB = parties[uidB]
                if first_line:
                    print()
                    first_line = False
                print("{} <-> {} CBs: {}".format(partyA.name,
                                                 partyB.name,
                                                 check_bits_strs[uidB]))

        # Display the secret keys.
        first_line = True
        for uidA in parties:
            partyA = parties[uidA]
            secret_keys = partyA.secret_keys
            secret_keys_by_uid = shared_fns.reorder_by_uid(secret_keys)
            secret_key_strs = shared_fns.convert_dod_to_dos(secret_keys_by_uid)
            for uidB in secret_keys_by_uid:
                partyB = parties[uidB]
                if first_line:
                    print()
                    first_line = False
                print("{} <-> {} key: {}".format(partyA.name,
                                                 partyB.name,
                                                 secret_key_strs[uidB]))


class NetworkManager:

    def __init__(self, cchl, edges):
        network = nx.DiGraph(edges)

        parties = {}
        for node_uid in network:
            party_name = party_names[node_uid]
            parties[node_uid] = components.Party(node_uid, party_name, self, cchl)

        qchls = {}
        for edge in network.edges:
            qchl = components.QuantumChannel()
            u_uid, v_uid = edge

            party_u = parties[u_uid]
            party_v = parties[v_uid]

            # qchl.add_socket(u_uid, party_u.socket)
            # qchl.add_socket(v_uid, party_v.socket)

            party_u.connect_to_qchl(v_uid, qchl)
            party_v.connect_to_qchl(u_uid, qchl)

            qchls[edge] = qchl

        nx.set_node_attributes(network, parties, "party")
        nx.set_edge_attributes(network, qchls, "qchl")

        self.network = network
        self.reset()

    def reset(self):
        parties = self.get_parties()
        for uid in parties:
            parties[uid].reset()

    def get_successors(self, party_uid):
        return list(self.network.successors(party_uid))

    def get_predecessors(self, party_uid):
        return list(self.network.predecessors(party_uid))

    def get_legitimate_party_uids(self):
        return list(self.get_parties().keys())

    def get_parties(self):
        return nx.get_node_attributes(self.network, "party")

    def get_party(self, uid):
        return self.get_parties()[uid]


class ClassicalChannel(UIComponent):

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.timestep = 0
        self.messages = {}
        super().reset()

    ###########################################################################
    # MESSAGE PROCESSING METHODS
    ###########################################################################

    # TODO make one message retrieval method
    # Note that get_tx_bases and get_rx_bases are currently structured slightly
    # differently from the other message retrieval methods. Is this necessary?

    def get_tx_bases(self, timestep):
        '''Retrieve all messages of type "broadcast_tx_bases" for the given timestep.'''
        tx_bases = {}
        for tx_uid in self.messages:
            for msg in self.messages[tx_uid]:
                if msg["type"] == "broadcast_tx_bases":
                    if msg["timestep"] == timestep:
                        tx_bases[tx_uid] = msg["data"]
        return tx_bases

    def get_rx_bases(self, timestep):
        '''Retrieve all messages of type "broadcast_rx_bases" for the given timestep.'''
        rx_bases = {}
        for rx_uid in self.messages:
            for msg in self.messages[rx_uid]:
                if msg["type"] == "broadcast_rx_bases":
                    if msg["timestep"] == timestep:
                        rx_bases[rx_uid] = msg["data"]
        return rx_bases

    def get_msg_check_bits(self, timestep, sender_uid):
        '''Retrieve all messages of type "broadcast_check_bits" for the given timestep.'''
        check_bits = {}
        if sender_uid in self.messages:
            for msg in self.messages[sender_uid]:
                if msg["type"] == "broadcast_check_bits":
                    if msg["timestep"] == timestep:
                        check_bits = msg["data"]
        return check_bits

    def get_flip_bit_instructions(self, timestep, sender_uid):
        '''Retrieve a message from sender_uid of type "broadcast_flip_bit_instructions" for the given timestep.'''
        flip_bit_instrs = {}
        if sender_uid in self.messages:
            for msg in self.messages[sender_uid]:
                if msg["type"] == "broadcast_flip_bit_instructions":
                    if msg["timestep"] == timestep:
                        flip_bit_instrs = msg["data"]
        return flip_bit_instrs

    def get_msg_key_length(self, timestep, sender_uid):
        key_length = math.inf
        if sender_uid in self.messages:
            for msg in self.messages[sender_uid]:
                if msg["type"] == "broadcast_key_length":
                    if msg["timestep"] == timestep:
                        key_length = msg["data"]
        return key_length

    ###########################################################################
    # UI METHODS
    ###########################################################################

    def ui_tick(self):
        '''Progress to the next timestep.'''
        data = {"messages": copy.deepcopy(self.messages)}
        super().ui_tick(data)

    ###########################################################################
    # CLASSICAL COMMUNICATION METHODS
    ###########################################################################

    def add_message(self, sender_uid, message):
        '''Add a message from sender_uid to the classical channel.'''
        if sender_uid not in self.messages:
            self.messages[sender_uid] = []
        self.messages[sender_uid].append(message)

