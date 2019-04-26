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

party_names = string.ascii_uppercase[:4] + string.ascii_uppercase[5:]


class QKDProtocol:

    def __init__(self, k=None, edges=None, protocol=0, animation=True, check_bit_prob=0.2):
        self.cchl = components.ClassicalChannel()
        self.set_protocol(protocol, k, edges, animation, check_bit_prob)
        self.eavesdropping = False

    def reset(self):
        '''Reset the protocol to its configuration at timestep 0.'''
        self.timestep = 0
        self.num_iterations = 0
        self.security = 0.0
        self.cchl.reset()
        self.network_manager.reset()
        self.protocol_secure = True
        self.next_timestep()

    def set_protocol(self, protocol, k=None, edges=None, animation=True, check_bit_prob=0.2):
        '''Set the protocol to run when run_one_step or run_n_steps is called.'''
        if protocol == 0:
            self.protocol = self.bb84
            edges = [(0, 1)]

        elif protocol == 1:
            self.protocol = self.bbm92
            edges = [(0, 1)]

        elif k is None and edges is None:
            # TODO Raise a more precise type of exception.
            raise Exception("Either k or edges must be specified.")

        # If k is not set then it defaults to the maximum node uid in edges.
        elif k is None:
            k = max([max((a, b) for a, b in edges)])

        # Chained BB84 Protocol
        elif protocol == 2:
            self.protocol = self.chained_protocol
            # If edges has not been specified, then set it to default chain.
            if edges is None:
                edges = [(i, i + 1) for i in range(k - 1)]

        # Star Graph BB84 Protocol 1
        elif protocol == 3:
            self.protocol = self.star_graph_protocol_1
            # If edges has not been specified, then set it to default star.
            if edges is None:
                edges = [(0, i + 1) for i in range(k - 1)]

        # Star Graph BB84 Protocol 2
        elif protocol == 4:
            self.protocol = self.star_graph_protocol_2
            # If edges has not been specified, then set it to default star.
            if edges is None:
                edges = [(0, i + 1) for i in range(k - 1)]

        else:
            raise ValueError(("Protocol {} does not exist. Valid protocols:\n"
                              "  0: 2-party BB84\n"
                              "  1: 2-party BBM92\n"
                              "  2: Chained BB84\n"
                              "  3: Star Graph BB84 (Protocol 1)\n"
                              "  4: Star Graph BB84 (Protocol 2)"
                              ).format(protocol))

        self.network_manager = NetworkManager(self.cchl, edges)
        self.protocol_params = {"animation": animation,
                                "check_bit_prob": check_bit_prob}
        self.reset()

    def add_eavesdropping(self, edges):
        '''Add eavesdropping to the specified edges.'''
        self.network_manager.intercept_edges(edges, self.cchl)
        self.eavesdropping = True

    def next_timestep(self):
        '''Store the data from this timestep and set up for the next timestep.'''
        self.cchl.next_timestep()
        self.network_manager.next_timestep()
        self.timestep += 1

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.cchl.store_timestep_data()
        self.network_manager.store_timestep_data()

    def get_stored_data_for_timestep(self, timestep):
        '''Retrieve all of the stored data for a given timestep.'''
        stored_data = {
            "cchl": self.cchl.get_stored_data_for_timestep(timestep),
            "parties": self.network_manager.get_party_stored_data_for_timestep(timestep),
            "qchls": self.network_manager.get_qchl_stored_data_for_timestep(timestep)
        }
        return stored_data

    def bb84(self, animation=True, check_bit_prob=0.2):
        '''Run 2-party BB84.'''
        protocol_secure = True
        alice = self.network_manager.get_party(0)
        bob = self.network_manager.get_party(1)

        eve = None
        if self.eavesdropping:
            eve = self.network_manager.get_party(2)

        valid_bits = [0, 1]
        valid_bases = [consts.STD_BASIS, consts.HAD_BASIS]

        # Bob randomly picks a basis.
        # bob.choose_rx_basis(valid_bases)
        bob_basis = bob.choose_from(valid_bases)
        bob.expect_tx_from(alice.uid)
        bob.measure_wrt(bob_basis)

        eve_basis = None
        if self.eavesdropping:
            # eve.choose_rx_basis(valid_bases)
            eve_basis = eve.choose_from(valid_bases)
            eve.expect_tx_from(alice.uid)
            eve.measure_wrt(eve_basis)
            eve.forward_qubits_to(bob.uid)

        # Alice randomly picks a bit and basis
        # alice.choose_tx_bit(valid_bits)
        # alice.choose_tx_basis(valid_bases)
        bit = alice.choose_from(valid_bits)
        alice_basis = alice.choose_from(valid_bases)
        alice.send_state(bit, alice_basis, bob.uid)

        # Alice and Bob publicly announce their bases.
        alice.broadcast_tx_bases(self.timestep)
        bob.broadcast_rx_bases(self.timestep)


        # alice.compare_bases(bob.uid)
        # bob.compare_bases(alice.uid)
        # if self.eavesdropping:
        #     eve.compare_bases(alice.uid, bob.uid)


        # Retrieve the bases.
        tx_bases = self.cchl.get_tx_bases(self.timestep)
        rx_bases = self.cchl.get_rx_bases(self.timestep)

        # Check whether Alice and Bob used the same basis.
        bases_match = False
        if np.allclose(rx_bases[bob.uid][alice.uid], tx_bases[alice.uid][bob.uid]):
            bases_match = True

        # If all the bases match, then add the bit to the sifted key.
        if bases_match:
            alice.add_all_bits_to_keys()
            bob.add_all_bits_to_keys()

            if self.eavesdropping:
                eve.add_all_bits_to_keys()

            # If running as an animation, then the sifted key bits from this
            # timestep are used as check bits with probability check_bit_prob.
            if animation:
                random_num = random.random()
                if random_num < check_bit_prob:
                    # Add the current bit to the check bits.
                    alice.add_check_bit(bob.uid)
                    bob.add_check_bit(alice.uid)

                    if self.eavesdropping:
                        eve.add_check_bit(alice.uid)
                        eve.add_check_bit(bob.uid)

                    # Each party broadcasts all of their check bits and tests
                    # for eavesdropping.
                    alice.broadcast_check_bits()
                    bob.receive_check_bits(alice.uid)
                    bob.broadcast_check_bits()
                    alice.receive_check_bits(bob.uid)

                    # If the party detects eavesdropping on any channel,
                    # then abort the run of the protocol.
                    if alice.compromised_chls or bob.compromised_chls:
                        print("\nEavesdropping detected!\n")
                        protocol_secure = False
                        return protocol_secure

        # Remove all check bits from the secret keys.
        alice.synch_sifted_and_secret_keys()
        alice.remove_check_bits_from_secret_keys()
        bob.synch_sifted_and_secret_keys()
        bob.remove_check_bits_from_secret_keys()

        if self.eavesdropping:
            eve.synch_sifted_and_secret_keys()
            eve.remove_check_bits_from_secret_keys()

        return protocol_secure

    def bbm92(self, animation=True, check_bit_prob=0.2):
        '''Run 2-party BBM92.'''
        alice = self.network_manager.get_party(0)
        bob = self.network_manager.get_party(1)

        # TODO

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
                basis = random.choice([consts.STD_BASIS,
                                       consts.HAD_BASIS])
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
        successors = self.network_manager.get_successors(first_party_uid)
        if not successors:
            # TODO Raise a more precise type of exception.
            raise Exception("The first party in the chain doesn't have a successor.")
        successor_uid = successors[0]

        bit = random.choice([0, 1])
        basis = random.choice([consts.STD_BASIS, consts.HAD_BASIS])
        # first_party.send_qubit(successor_uid, bit, basis)
        coeffs = basis[bit]
        state = first_party.generate_state(coeffs)
        first_party.transmit(state, successor_uid)

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

                        # If the party detects eavesdropping on any channel,
                        # then abort the run of the protocol.
                        if parties[uid].compromised_chls:
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
                basis = random.choice([consts.STD_BASIS,
                                       consts.HAD_BASIS])
                parties[uid].next_qubit_is_from(leader_uid)
                parties[uid].measure_next_qubit_wrt(basis)

        # The leader generates and transmits a qubit for each of the other
        # parties using different random bits and bases.
        leader = parties[leader_uid]
        successors = self.network_manager.get_successors(leader_uid)
        for successor_uid in successors:
            bit = random.choice([0, 1])
            basis = random.choice([consts.STD_BASIS,
                                   consts.HAD_BASIS])
            # leader.send_qubit(successor_uid, bit, basis)
            coeffs = basis[bit]
            state = leader.generate_state(coeffs)
            leader.transmit(state, successor_uid)

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

                        # If the leader detects eavesdropping on any channel,
                        # then abort the run of the protocol.
                        if leader.compromised_chls:
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
                basis = random.choice([consts.STD_BASIS,
                                       consts.HAD_BASIS])
                parties[uid].next_qubit_is_from(leader_uid)
                parties[uid].measure_next_qubit_wrt(basis)

        # The leader generates and transmits a qubit for each of the other
        # parties using different random bits and bases.
        leader = parties[leader_uid]
        successors = self.network_manager.get_successors(leader_uid)
        for successor_uid in successors:
            bit = random.choice([0, 1])
            basis = random.choice([consts.STD_BASIS,
                                   consts.HAD_BASIS])
            # leader.send_qubit(successor_uid, bit, basis)
            coeffs = basis[bit]
            state = leader.generate_state(coeffs)
            leader.transmit(state, successor_uid)

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
                    if leader.compromised_chls:
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
        '''Run one iteration of the set protocol.'''
        if self.protocol_secure:
            # Run one iteration of the set protocol.
            protocol_secure = self.protocol(**self.protocol_params)
            # If eavesdropping was detected in this run of the protocol, then
            # prevent any future attempts to run an iteration of the protocol.
            self.protocol_secure = protocol_secure
            # Optionally print the data to the terminal.
            if display_data:
                self.display_data()
            # Setup for the next timestep.
            if self.protocol_secure:
                self.next_timestep()
            else:
                self.store_timestep_data()
            # Increment the iteration counter.
            self.num_iterations += 1

    def run_n_steps(self, n, display_bits=True):
        '''Run n iterations of the protocol.'''
        if self.protocol_secure:
            count = 0
            while self.protocol_secure and count < n:
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
        total_qstates_generated = 0
        total_qstates_transmitted = 0
        total_qstates_received = 0

        parties = self.network_manager.get_parties()
        for party_uid in parties:
            party = parties[party_uid]
            total_qstates_generated += party.total_qstates_generated
            total_qstates_transmitted += party.total_qstates_transmitted
            total_qstates_received += party.total_qstates_received

        return (total_qstates_generated,
                total_qstates_transmitted,
                total_qstates_received)

    def display_data(self, display_bits=True):
        '''Print the protocol data to the terminal.'''
        parties = self.network_manager.get_parties()
        qubit_counts = self.calculate_qubit_counts()

        print("Protocol iterations: {}".format(self.num_iterations))
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
        if not edges:
            raise ValueError("The network must have at least one edge.")

        network = nx.DiGraph(edges)

        if len(network) < 2:
            raise ValueError("The network must have at least 2 nodes.")

        # Create a party for every node in the network.
        parties = {}
        for node_uid in network:
            party_name = party_names[node_uid]
            parties[node_uid] = components.Party(node_uid, party_name,
                                                 self, cchl)

        # Create a quantum channel for every edge in the network.
        qchls = {}
        for edge in network.edges:
            tx_uid, rx_uid = edge
            tx_party = parties[tx_uid]
            rx_party = parties[rx_uid]
            qchl = components.QuantumChannel()
            tx_party.connect_tx_qchl(qchl, rx_uid)
            rx_party.connect_rx_qchl(qchl, tx_uid)
            qchls[edge] = qchl

        # Store the parties as nodes and the qchls as edges.
        nx.set_node_attributes(network, parties, "party")
        nx.set_edge_attributes(network, qchls, "qchl")

        self.network = network
        self.parties = nx.get_node_attributes(self.network, "party")
        self.qchls = nx.get_edge_attributes(self.network, "qchl")

        self.intercepted_edges = {}
        self.reset()

    def reset(self):
        '''Reset the network to its configuration at timestep 0.'''
        # Reset all of the parties in the network.
        for uid in self.parties:
            self.parties[uid].reset()
        # Reset all of the quantum channels in the network.
        for uid in self.qchls:
            self.qchls[uid].reset()
        # Reset the network manager's timestep counter.
        self.timestep = 0

    def next_timestep(self):
        '''Store the data from this timestep and set up for the next timestep.'''
        # Increment the timestep for all the parties in the network.
        for uid in self.parties:
            self.parties[uid].next_timestep()
        # Increment the timestep for all the qchls in the network.
        for uid in self.qchls:
            self.qchls[uid].next_timestep()
        # Increment the network manager's timestep counter.
        self.timestep += 1

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        # Store the data for all the parties in the network.
        for uid in self.parties:
            self.parties[uid].store_timestep_data()
        # Store the data for all the qchls in the network.
        for uid in self.qchls:
            self.qchls[uid].store_timestep_data()

    def get_successors(self, party_uid):
        return list(self.network.successors(party_uid))

    def get_predecessors(self, party_uid):
        return list(self.network.predecessors(party_uid))

    def get_legitimate_party_uids(self):
        return list(self.parties.keys())

    def get_parties(self):
        return self.parties

    def get_party(self, party_uid):
        return self.parties[party_uid]

    def get_qchls(self):
        return self.qchls

    def get_qchl(self, qchl_uid):
        return self.qchls[qchl_uid]

    def intercept_edges(self, intercepted_edges, cchl):
        '''Add an eavesdropping party to the given edges.'''
        eve_uid = max([uid for uid in self.parties]) + 1
        qchls = {}

        for edge in self.qchls:
            if edge in intercepted_edges:
                tx_uid, rx_uid = edge
                rx_party = self.parties[rx_uid]

                # Create a new eavesdropping party.
                eve = components.Party(eve_uid, "E",
                                       self, cchl, is_eve=True)
                eve.next_timestep()  # TODO change this to:
                                     # eve.set_timestep(self.timestep)
                self.parties[eve_uid] = eve

                # Redirect the existing channel to this party.
                existing_qchl = self.get_qchl(edge)
                existing_qchl.disconnect_rx_device()
                eve.connect_rx_qchl(existing_qchl, tx_uid)
                existing_qchl.intercepted = True

                # Add a new channel from Eve to the rx party.
                new_qchl = components.QuantumChannel()
                new_qchl.next_timestep()  # TODO Change this to:
                                          # new_qchl.set_timestep(self.timestep)
                eve.connect_tx_qchl(new_qchl, rx_uid)
                rx_party.connect_rx_qchl(new_qchl, tx_uid)

                # Record both qchls in the new dictionary of qchls.
                qchls[(tx_uid, eve_uid)] = existing_qchl
                qchls[(eve_uid, rx_uid)] = new_qchl

                # Remove the old edge from the network and add the new ones.
                self.network.remove_edge(tx_uid, rx_uid)
                self.network.add_edge(tx_uid, eve_uid)
                self.network.add_edge(eve_uid, rx_uid)

                # The next eavesdropping party should have a different UID.
                eve_uid += 1
            else:
                qchls[edge] = self.qchls[edge]

        nx.set_node_attributes(self.network, self.parties, "party")
        nx.set_edge_attributes(self.network, qchls, "qchl")
        self.qchls = qchls
        self.intercepted_edges = intercepted_edges

    ###########################################################################
    # UI STORED DATA RETRIEVAL METHODS
    ###########################################################################

    def get_party_stored_data_for_timestep(self, timestep):
        '''Retrieve the stored data from all parties for the given timestep.'''
        stored_data = {}
        for uid in self.parties:
            party = self.get_party(uid)
            stored_data[uid] = party.get_stored_data_for_timestep(timestep)
        return stored_data

    def get_qchl_stored_data_for_timestep(self, timestep):
        '''Retrieve the stored data from all qchls for the given timestep.'''
        stored_data = {}
        for uid in self.qchls:
            qchl = self.get_qchl(uid)
            stored_data[uid] = qchl.get_stored_data_for_timestep(timestep)
        return stored_data

