import networkx as nx
import numpy as np
import random
import string
import time
import copy

import components
import shared_fns
import consts

party_names = string.ascii_uppercase[:4] + string.ascii_uppercase[5:]


class KPartyBB84:

    def __init__(self, k, edges=None, protocol=0):
        self.cchl = ClassicalChannel()
        self.network_manager = NetworkManager(k, self.cchl, edges=edges)
        self.cchl.add_network_manager(self.network_manager)

        if protocol == 0:
            self.protocol = self.chained_protocol
        else:
            raise NotImplementedError()

        # self.secret_key = ""
        self.total_qubits_sent = 0
        self.current_step = 0

    def reset(self):
        self.network_manager.reset()
        self.cchl.reset()
        # self.secret_key = ""
        self.total_qubits_sent = 0
        self.current_step = 0

    def chained_protocol(self):
        parties = self.network_manager.get_parties()
        # Every party sends a qubit to each of its recipients at approximately
        # the same time.
        for party_A_uid in parties:
            party_A = parties[party_A_uid]
            successors = self.network_manager.get_successors(party_A_uid)

            # The party sends a qubit to each of its successors.
            for party_B_uid in successors:
                party_B = parties[party_B_uid]

                # Party A chooses a random bit.
                bit_A = random.choice([0, 1])

                # Both parties choose a basis.
                basis_A = None
                # If party_A has already measured a qubit w.r.t. a basis, then
                # use the same basis
                for uid in party_A.rx_bases:
                    rx_bases = party_A.rx_bases[uid]
                    if self.current_step < len(rx_bases):
                        basis_A = rx_bases[self.current_step]

                if basis_A is None:
                    # print("Party {} choosing random tx basis".format(party_A.name))
                    basis_A = random.choice([consts.STANDARD_BASIS,
                                             consts.HADAMARD_BASIS])

                basis_B = None
                for uid in party_B.tx_bases:
                    tx_bases = party_B.tx_bases[uid]
                    if self.current_step < len(tx_bases):
                        basis_B = tx_bases[self.current_step]

                if basis_B is None:
                    # print("Party {} choosing random rx basis".format(party_B.name))
                    basis_B = random.choice([consts.STANDARD_BASIS,
                                             consts.HADAMARD_BASIS])

                # Party B will measure the next qubit it receives (just from A??)
                # w.r.t. this random basis.
                party_B.set_next_sender_uid(party_A_uid)
                party_B.set_next_measurement_basis(basis_B, party_A_uid)

                # Party A encodes the bit as a qubit w.r.t its random basis,
                # and send this qubit to party B.
                party_A.send_qubit(party_B_uid, bit_A, basis_A)
                self.total_qubits_sent += 1
                time.sleep(0.005)

        # Each party publicly announces the basis it used.
        for party_uid in parties:
            party = parties[party_uid]
            if party.rx_bases:
                party.broadcast_rx_bases(self.current_step)
            else:
                party.broadcast_tx_bases(self.current_step)

        # If all the bases match, then add the corresponding bit to the sifted key.
        bases = self.cchl.get_bases(self.current_step)
        comparison = [bases[0]] * len(bases)
        bases_match = all(np.allclose(bases[i], comparison[i]) for i in range(len(bases)))
        if bases_match:
            # Each party publicly announces if its recipient(s) need to flip
            # the received bit value.
            for party_A_uid in parties:
                party_A = parties[party_A_uid]
                for party_B_uid in party_A.rx_bits:
                    for party_C_uid in party_A.tx_bits:
                        party_C = parties[party_C_uid]
                        flip_bool = False
                        rx_bit = party_A.rx_bits[party_B_uid][self.current_step]
                        tx_bit = party_A.tx_bits[party_C_uid][self.current_step]
                        if rx_bit != tx_bit:
                            flip_bool = True
                        party_A.broadcast_flip_instruction(party_C_uid, self.current_step, flip_bool)
                        party_C.broadcast_flip_instruction(party_A_uid, self.current_step, flip_bool)

            for party_uid in parties:
                party = parties[party_uid]
                # print("\nParty {} ({}) retrieving flip instruction".format(party_uid, party.name))
                party.retrieve_flip_instruction(self.current_step)
                # print("\nParty {} ({}) extending secret keys".format(party_uid, party.name))
                party.extend_secret_keys()

    def run_one_step(self, display_data=True):
        self.protocol()

        self.current_step += 1

        if display_data:
            self.display_data()

    def run_n_steps(self, n):
        for i in range(n):
            self.run_one_step(display_data=False)

        self.display_data()

    def run(self):
        pass

    def display_data_old(self):
        parties = self.get_parties()
        print("Total qubits sent:  {}".format(self.total_qubits_sent))
        print("Sifted key length:  {}\n".format(parties[0].sifted_key_length))

        for uid in parties:
            party = parties[uid]
            print("{}'s tx bits:    {}".format(party.name, party.tx_bits))
            print("{}'s rx bits:    {}".format(party.name, party.rx_bits))
            print("{}'s bases:      {}\n".format(party.name, party.bases))

        for uid in parties:
            party = parties[uid]
            print("{}'s sifted key: {}".format(party.name, party.format_sifted_key()))

        print()

    def display_data(self):
        parties = self.network_manager.get_parties()

        print("Protocol iterations: {}".format(self.current_step))
        print("Total qubits sent:   {}".format(self.total_qubits_sent))

        party0_lens = parties[0].secret_keys_lengths
        party0_lens_uids = list(party0_lens.keys())
        key_length = 0
        if party0_lens_uids:
            key_length = party0_lens[party0_lens_uids[0]]

        print("Secret key length:   {}".format(key_length))

        for party_A_uid in parties:
            party_A = parties[party_A_uid]
            if party_A.tx_bits:
                print("\nParty {} (tx)".format(party_A.name))

            for party_B_uid in party_A.tx_bits:
                party_B = parties[party_B_uid]
                tx_bits = party_A.tx_bits[party_B_uid]
                tx_bits_str = shared_fns.convert_list_to_string(tx_bits)
                tx_bases = party_A.tx_bases[party_B_uid]
                tx_bases_chars = self.represent_bases_by_chars(tx_bases)
                tx_bases_str = shared_fns.convert_list_to_string(tx_bases_chars)

                print("    {} -> {}:  {}".format(party_A.name, party_B.name,
                                                   tx_bits_str))
                print("             {}".format(tx_bases_str))

            if party_A.rx_bits:
                print("\nParty {} (rx)".format(party_A.name))

            for party_B_uid in party_A.rx_bits:
                party_B = parties[party_B_uid]
                rx_bits = party_A.rx_bits[party_B_uid]
                rx_bits_str = shared_fns.convert_list_to_string(rx_bits)
                rx_bases = party_A.rx_bases[party_B_uid]
                rx_bases_chars = self.represent_bases_by_chars(rx_bases)
                rx_bases_str = shared_fns.convert_list_to_string(rx_bases_chars)

                print("    {} -> {}:  {}".format(party_B.name, party_A.name,
                                                    rx_bits_str))
                print("             {}".format(rx_bases_str))

        print("\n")
        for party_A_uid in parties:
            party_A = parties[party_A_uid]
            for party_B_uid in party_A.secret_keys:
                party_B = parties[party_B_uid]

                # secret_key_idxs = party_A.secret_keys_idxs[party_B_uid]
                # secret_key_length = party_A.secret_keys_lengths[party_B_uid]
                # secret_key_str = shared_fns.convert_list_to_string(party_A.secret_keys[party_B_uid])
                # formatted = shared_fns.add_spaces_to_bitstring(secret_key_str,
                #                                                secret_key_idxs,
                #                                                secret_key_length)

                print("{} <-> {} key: {}".format(party_A.name, party_B.name, party_A.secret_keys[party_B_uid]))#formatted))

    def represent_bases_by_chars(self, bases):
        basis_chars = []
        for basis in bases:
            if np.allclose(basis, consts.STANDARD_BASIS):
                basis_chars.append('S')
            elif np.allclose(basis, consts.HADAMARD_BASIS):
                basis_chars.append('H')
            else:
                basis_chars.append('?')

        return basis_chars

    def view_secret_key(self, view_all=False):
        parties = self.network_manager.get_parties()
        secret_key = parties[0].secret_key
        secret_key_str = shared_fns.convert_list_to_string(secret_key)
        print(secret_key_str)

        if view_all:
            raise NotImplementedError("Not implemented for view_all=True")


class NetworkManager:

    def __init__(self, k, cchl, edges=None):
        network = nx.DiGraph()

        if edges is None:
            network = nx.complete_graph(k, nx.DiGraph())

        else:
            network.add_edges_from(edges)

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

            # party_u.set_target(v_uid)

            qchls[edge] = qchl

        nx.set_node_attributes(network, parties, "party")
        nx.set_edge_attributes(network, qchls, "qchl")

        self.network = network
        self.reset()

    def reset(self):
        parties = self.get_parties()
        for uid in parties:
            parties[uid].reset()
            parties[uid].update_network()

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


class ClassicalChannel:

    def __init__(self):
        self.reset()

    def reset(self):
        self.bases = {}
        self.flip_instructions = {}
        self.msgs_ready_to_compare_bases = {}

    def add_network_manager(self, network_manager):
        self.network_manager = network_manager

    def get_bases(self, basis_idx):
        return self.bases[basis_idx]

    def get_flip_instructions(self, uid, bit_idx):
        # print("Flip instructions: {}".format(self.flip_instructions))
        sender_uid, flip_bool = (None, False)
        # print("uid {} getting flip instruction".format(uid))
        if uid in self.flip_instructions:
            # print("uid {} is in self.flip_instructions".format(uid))
            if bit_idx in self.flip_instructions[uid]:
                # print("bit_idx {} in self.flip_instructions[{}]".format(bit_idx, uid))
                sender_uid, flip_bool = self.flip_instructions[uid][bit_idx]

        return (sender_uid, flip_bool)

    ###########################################################################
    # CLASSICAL COMMUNICATION METHODS
    ###########################################################################

    def msg_ready_to_compare_basis(self, party_uid, basis_idx):
        print("msg_ready_to_compare_basis, party_uid {}, basis_idx {}".format(party_uid, basis_idx))
        msgs = self.msgs_ready_to_compare_bases

        if party_uid not in msgs:
            msgs[party_uid] = []

        # Limit the number of basis indices stored to (up to) 3 for each party.
        if len(msgs[party_uid]) == 3:
            msgs[party_uid].pop(0)

        msgs[party_uid].append(basis_idx)
        return copy.deepcopy(msgs)

    def msg_compare_bases(self, basis_idx):
        print("msg_compare_bases(), basis_idx {}".format(basis_idx))
        parties = self.network_manager.get_parties()
        bases = []
        for uid in parties:
            basis = parties[uid].transmit_basis(basis_idx)
            bases.append(basis)

        for uid in parties:
            parties[uid].compare_bases(bases)

    def msg_broadcast_bases(self, basis_idx, bases):
        # shared_fns.append_to_dol(self.bases, basis_idx, bases)

        if basis_idx not in self.bases:
            self.bases[basis_idx] = []

        self.bases[basis_idx].extend(bases)

    def msg_broadcast_flip_instructions(self, tx_uid, rx_uid, bit_idx, flip_bool):
        if rx_uid not in self.flip_instructions:
            self.flip_instructions[rx_uid] = {}

        self.flip_instructions[rx_uid][bit_idx] = (tx_uid, flip_bool)

    def msg_flip_bit(self, recipient_uid, bit_position):
        '''Forward the following message to the intended recipient:
        Flip the bit of the sifted key that is in the given bit_position.'''

        recipient = self.network_manager.get_party(recipient_uid)
        recipient.add_flip_bit(bit_position)

    def msg_flip_bits(self, recipient_uid, flip_bit_str):
        '''Forward the following message to the intended recipient:
        For any '1' in flip_bit_str, flip the bit in the corresponding
        position of the sifted key.

        E.g. repicient's old sifted key == "011", flip_bits_str == "101"
             --> recipient's new sifted key == "110".'''

        recipient = self.network_manager.get_party(recipient_uid)
        recipient.flip_bits(flip_bit_str)

    ###########################################################################
    # OBSOLETE METHODS
    ###########################################################################

    def compare_bases(self, basis_idx):
        # Check that all the parties have the same number of bases.
        parties = self.get_parties()
        bases_length = len(parties[0].bases)
        bases_lengths_match = True
        for uid in parties:
            party = parties[uid]
            if len(party.bases) != bases_length:
                bases_lengths_match = False
                break

        # Check whether all the bases match.
        if bases_lengths_match:
            basis_value = parties[0].bases[-1]
            basis_values_match = True
            for uid in parties:
                party = parties[uid]
                if not party.bases or party.bases[-1] != basis_value:
                    basis_values_match = False
                    break

            for uid in parties:
                party = parties[uid]
                print("{} updating sifted_key ({})".format(party.name, basis_values_match))
                party.update_sifted_key(basis_values_match)

