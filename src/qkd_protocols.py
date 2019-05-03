import networkx as nx
import numpy as np
import random
import copy
import math

import components
import shared_fns
import consts
from network_manager import NetworkManager


class QKDProtocol:

    def __init__(self, k=None, edges=None, check_bit_prob=0.2, protocol_id=0):
        self.cchl = components.ClassicalChannel()
        self.setup_network_manager(k, edges)
        self.check_bit_prob = check_bit_prob
        self.eavesdropping = False
        self.intercepted_edges = []
        self.computation_time = None
        self.memory_usage = None

    def reset(self):
        '''Reset the protocol to its configuration at timestep 0.'''
        self.timestep = 0
        self.num_iterations = 0
        self.num_generated_states = 0
        self.security = 0
        self.key_length = 0
        self.stored_data = {}
        self.cchl.reset()
        self.network_manager.reset()
        self.protocol_secure = True
        self.next_timestep()

    def setup_network_manager(self, k=None, edges=None):
        '''Set the protocol to run when run_one_step or run_n_steps is called.'''
        if k is None and edges is None:
            raise ValueError("Either k or edges must be specified.")

        # If k is not set then it defaults to the maximum node uid in edges.
        if k is None:
            k = max([max((a, b) for a, b in edges)])

        self.network_manager = NetworkManager(self.cchl, edges)
        self.reset()

    def add_eavesdropping(self, edges):
        '''Add eavesdropping to the specified edges.'''
        self.network_manager.intercept_edges(edges, self.cchl)
        self.eavesdropping = True
        self.intercepted_edges = edges

    def next_timestep(self):
        '''Store the data from this timestep and set up for the next timestep.'''
        self.cchl.next_timestep()
        self.network_manager.next_timestep()
        self.stored_data[self.num_iterations] = {
            "security": self.security,
            "key_length": self.key_length
        }
        self.timestep += 1

    def store_timestep_data(self):
        '''Store the data from this timestep.'''
        self.cchl.store_timestep_data()
        self.network_manager.store_timestep_data()
        self.stored_data[self.num_iterations] = {
            "security": self.security,
            "key_length": self.key_length
        }

    def get_stored_data_for_timestep(self, timestep):
        '''Retrieve all of the stored data for a given timestep.'''
        stored_data = {
            "protocol": copy.deepcopy(self.stored_data[timestep]),
            "cchl": self.cchl.get_stored_data_for_timestep(timestep),
            "parties": self.network_manager.get_party_stored_data_for_timestep(timestep),
            "qchls": self.network_manager.get_qchl_stored_data_for_timestep(timestep)
        }
        return stored_data

    def run_one_step(self, display_data=True):
        '''Run one iteration of the set protocol.'''
        if self.protocol_secure:
            # Run one iteration of the set protocol.
            protocol_secure = self.protocol()
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
            # Update the security and the key length fields
            self.update_security()
            self.update_key_length()
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

    def run(self, num_iterations=None, security=0.95, key_length=128):
        '''Run for the given number of iterations, or until the secret key reaches the required length.'''
        # If the number of iterations is explicitly specified, then run the
        # protocol for exactly this number of iterations.
        if num_iterations is not None:
            self.run_n_steps(num_iterations)
        # Otherwise, continue to run the protocol until the secret key reaches
        # the required length and enough bits have been used as check bits to
        # provide the required level of security.
        else:
            # Calculate the minimum number of check bits
            required_num_check_bits = self.required_num_check_bits(security)
            # Run the protocol until the required number of check bits and
            # key bits is reached.
            num_check_bits = self.get_shortest_check_bits()
            num_key_bits = self.get_shortest_key_length()
            while self.protocol_secure and (num_key_bits < key_length or
                                num_check_bits < required_num_check_bits):
                self.run_one_step(display_data=False)
                num_check_bits = self.get_shortest_check_bits()
                num_key_bits = self.get_shortest_key_length()

    def required_num_check_bits(self, security):
        '''Calculate the minimum number of check bits required for the given security level.'''
        return math.ceil(math.log(1 - security) / math.log(0.75))

    def get_shortest_key_length(self):
        '''Return the length of the shortest secret key in the network.'''
        # TODO Move this to NetworkManager
        parties = self.network_manager.get_parties()
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

        return min_key_length

    def get_shortest_check_bits(self):
        '''Return the length of the shortest check bits in the network.'''
        # TODO Move this to NetworkManager
        parties = self.network_manager.get_parties()
        min_check_bits = math.inf
        for uidA in parties:
            partyA = parties[uidA]
            check_bits = partyA.check_bits
            if not check_bits:
                min_check_bits = 0
                break
            check_bits_by_uid = shared_fns.reorder_by_uid(check_bits)
            for uidB in check_bits_by_uid:
                key_length = len(list(check_bits_by_uid[uidB]))
                if key_length < min_check_bits:
                    min_check_bits = key_length

        return min_check_bits

    def update_key_length(self):
        self.key_length = self.get_shortest_key_length()

    def update_security(self):
        # Given n matching check bits, calculate the least upper bound for the
        # probability that Eve has gotten away with eavesdropping.
        num_check_bits = self.get_shortest_check_bits()
        security = 0
        upper_bound = 1
        while upper_bound - security > 0.0001:
            candidate = security + (upper_bound - security) / 2
            n = self.required_num_check_bits(candidate)
            if n > num_check_bits:
                upper_bound = candidate
            elif n <= num_check_bits:
                security = candidate
        self.security = security

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


class BB84(QKDProtocol):

    def __init__(self, check_bit_prob=0.2, eavesdropping=False):
        super().__init__(self, edges=[(0, 1)], check_bit_prob=check_bit_prob)
        if eavesdropping:
            self.add_eavesdropping([(0, 1)])

    def protocol(self):
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
        bob_basis = bob.choose_from(valid_bases)
        bob.set_basis(alice.uid, bob_basis)

        eve_basis = None
        if self.eavesdropping:
            eve_basis = eve.choose_from(valid_bases)
            eve.set_basis(alice.uid, eve_basis)

        # Alice randomly picks a bit and basis
        bit = alice.choose_from(valid_bits)
        alice_basis = alice.choose_from(valid_bases)

        # Alice sends the corresponding qubit to Bob.
        alice.send_state(bit, alice_basis, bob.uid)

        # Alice and Bob publicly announce their bases.
        bob.broadcast_rx_bases(self.timestep)
        alice.broadcast_tx_bases(self.timestep)

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

            # The sifted key bits from this iteration are used as check bits
            # with probability check_bit_prob.
            random_num = random.random()
            if random_num < self.check_bit_prob:
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

        # TODO Indent this one more to the right? Only needs to happen when Alice and Bob use the same basis.
        # Remove all check bits from the secret keys.
        alice.synch_sifted_and_secret_keys()
        alice.remove_check_bits_from_secret_keys()
        bob.synch_sifted_and_secret_keys()
        bob.remove_check_bits_from_secret_keys()

        if self.eavesdropping:
            eve.synch_sifted_and_secret_keys()
            eve.remove_check_bits_from_secret_keys()

        return protocol_secure


class BBM92(QKDProtocol):

    def __init__(self, check_bit_prob=0.2, eavesdropping=False):
        super().__init__(self, edges=[(0, 1)], check_bit_prob=check_bit_prob)
        if eavesdropping:
            self.add_eavesdropping([(0, 1)])

    def protocol(self):
        '''Run 2-party BBM92.'''
        alice = self.network_manager.get_party(0)
        bob = self.network_manager.get_party(1)

        # TODO

        # Bob randomly picks a basis.


        # Alice prepares an entangled Bell state.


        # Alice keeps one qubit and transmits the other to Bob.


        # Alice and Bob broadcast their bases.
        # (All identical to BB84.)


class ChainedBB84(QKDProtocol):

    def __init__(self, k, edges=[], check_bit_prob=0.2, intercepted_edges=[]):
        if not edges:
            edges = [(i, i + 1) for i in range(k - 1)]

        else:
            # Find a path through the network that passes through every party
            # at least once. Set edges to be this path.
            pass

        super().__init__(self, edges=edges, check_bit_prob=check_bit_prob)

        if intercepted_edges:
            self.add_eavesdropping(intercepted_edges)

    def protocol(self):
        '''Run the chained BB84 protocol.'''
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
                parties[uid].set_basis(predecessor_uid, basis)
                # After measurement, the qubit should be forwarded to the next
                # party in the chain.
                successors = self.network_manager.get_successors(uid)
                if successors:
                    successor_uid = successors[0]
                    parties[uid].forward(predecessor_uid, successor_uid)

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
        # coeffs = basis[bit]
        # state = first_party.generate_state(coeffs)
        # first_party.transmit(state, successor_uid)
        first_party.send_state(bit, basis, successor_uid)

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

            # The sifted key bits from this iteration are used as check bits
            # with probability check_bit_prob.
            random_num = random.random()
            if random_num < self.check_bit_prob:
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


class KPartyBBM92(QKDProtocol):

    def __init__(self, k, edges=[], check_bit_prob=0.2, intercepted_edges=[]):
        # Party 0 is the generator of the entangled state so needs to have
        # a path to every other party.

        if not edges:
            # Run on a star graph by default.
            edges = [(0, i + 1) for i in range(k - 1)]

        super().__init__(self, edges=edges, check_bit_prob=check_bit_prob)

        if intercepted_edges:
            self.add_eavesdropping(intercepted_edges)

    def protocol(self):
        pass


class Repeated2PartyQKD(QKDProtocol):

    def __init__(self, k, edges=[], check_bit_prob=0.2, intercepted_edges=[]):
        if not edges:
            # Create a random connected graph.
            pass

        super().__init__(self, edges=edges, check_bit_prob=check_bit_prob)

        if intercepted_edges:
            self.add_eavesdropping(intercepted_edges)

    def protocol(self):
        '''Run BB84 Star Graph Protocol 2. TODO generalise to any connected network.'''
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

        # The sifted key bits from this iteration are used as check bits
        # with probability check_bit_prob.
        random_num = random.random()
        if random_num < self.check_bit_prob:
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


