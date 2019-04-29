import networkx as nx
import string
import components


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
            party_names = string.ascii_uppercase[:4] + string.ascii_uppercase[5:]
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
                eve.update_rx_action(tx_uid, "forward", True)
                eve.update_rx_action(tx_uid, "forward_id", rx_uid)
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

