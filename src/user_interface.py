import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons

import k_party_protocol as kpp
import shared_fns


class UI:

    def __init__(self):
        self.title = ""
        self.num_timesteps = 50
        self.k = None
        self.edges = None
        self.protocol_id = 0
        self.check_bit_prob = 0.2
        self.intercepted_edges = []

    def show(self):
        self.run_protocol()
        self.setup_plot()
        self.setup_graph()
        self.stimestep.on_changed(self.update)
        plt.show()

    def run_protocol(self):
        self.protocol = kpp.QKDProtocol(k=self.k, edges=self.edges,
                                        protocol=self.protocol_id,
                                        check_bit_prob=self.check_bit_prob)
        if self.intercepted_edges:
            self.protocol.add_eavesdropping(self.intercepted_edges)
        self.protocol.run_n_steps(self.num_timesteps)

    def setup_plot(self):
        self.fig, _ = plt.subplots()
        plt.subplots_adjust(bottom=0.25)
        self.fig.canvas.set_window_title(self.title)
        axcolor = "#eeddee"
        axtime = plt.axes([0.2, 0.1, 0.65, 0.03], facecolor=axcolor)
        self.stimestep = Slider(axtime, 'Timestep', 0,
                                self.protocol.num_iterations,
                                valinit=0, valstep=1,
                                valfmt="%d",  # Display as an integer.
                                facecolor="#682860")

    def setup_graph(self):
        self.G = nx.DiGraph(self.protocol.network_manager.network.edges)
        if self.protocol_id == 0:
            self.pos = nx.circular_layout(self.G)
        else:
            self.pos = nx.spring_layout(self.G)
        parties = self.protocol.network_manager.get_parties()

        self.legitimate_party_names = {}
        self.eavesdropping_party_names = {}
        self.legitimate_parties = []
        self.eavesdropping_parties = []
        for uid in parties:
            party_name = parties[uid].name
            if parties[uid].is_eve:
                self.eavesdropping_party_names[uid] = party_name
                self.eavesdropping_parties.append(uid)
            else:
                self.legitimate_party_names[uid] = party_name
                self.legitimate_parties.append(uid)

        self.draw_network()

    def draw_network(self):
        plt.sca(self.fig.axes[0])
        plt.axis("off")
        nx.draw_networkx_nodes(self.G, self.pos,
                               nodelist=self.legitimate_parties,
                               node_size=400, node_color="#682860")

        nx.draw_networkx_nodes(self.G, self.pos,
                               nodelist=self.eavesdropping_parties,
                               node_size=400, node_color="#eeddee")

        nx.draw_networkx_labels(self.G, self.pos,
                                nodelist=self.legitimate_parties,
                                labels=self.legitimate_party_names,
                                font_color='w', font_family="arial")

        nx.draw_networkx_labels(self.G, self.pos,
                                nodelist=self.eavesdropping_parties,
                                labels=self.eavesdropping_party_names,
                                font_color='k', font_family="arial")

        nx.draw_networkx_edges(self.G, self.pos)

    def update(self, val):

        def get_tx_label(tx_party, rx_uid):
            bit = tx_party["tx_bits"][ui_timestep][rx_uid]
            basis = tx_party["tx_bases"][ui_timestep][rx_uid]
            basis_char = shared_fns.represent_basis_by_char(basis)
            label = "({}, {})".format(bit, basis_char)
            return label

        def get_rx_label(rx_party, tx_uid):
            bit = rx_party["rx_bits"][ui_timestep][tx_uid]
            basis = rx_party["rx_bases"][ui_timestep][tx_uid]
            basis_char = shared_fns.represent_basis_by_char(basis)
            label = "({}, {})".format(bit, basis_char)
            return label

        ui_timestep = int(self.stimestep.val)
        tstep_data = self.protocol.get_stored_data_for_timestep(ui_timestep)
        network_manager = self.protocol.network_manager
        network_edges = network_manager.network.edges

        # Clear the axis and redraw the basic network.
        self.fig.axes[0].clear()
        self.draw_network()

        # Display all of the bits and bases for the timestep on the edges
        # of the network.
        parties_data = tstep_data["parties"]
        tx_labels = {}
        rx_labels = {}
        for uid in parties_data:
            party = parties_data[uid]
            # Make the tx labels.
            if ui_timestep in party["tx_bits"]:
                for rx_uid in party["tx_bits"][ui_timestep]:
                    label = get_tx_label(party, rx_uid)
                    # If there is a quantum channel connecting the parties.
                    if (uid, rx_uid) in network_edges:
                        tx_labels[(uid, rx_uid)] = label
                    # If the edge has been intercepted.
                    else:
                        eve_uid = nx.shortest_path(self.G, uid, rx_uid)[1]
                        tx_labels[(uid, eve_uid)] = label
            # Make the rx_labels.
            if ui_timestep in party["rx_bits"]:
                for tx_uid in party["rx_bits"][ui_timestep]:
                    label = get_rx_label(party, tx_uid)
                    # If there is a quantum channel connecting the parties.
                    if (tx_uid, uid) in network_edges:
                        rx_labels[(tx_uid, uid)] = label
                    # If the edge has been intercepted.
                    else:
                        eve_uid = nx.shortest_path(self.G, tx_uid, uid)[1]
                        rx_labels[(eve_uid, uid)] = label

        nx.draw_networkx_edge_labels(self.G, self.pos,
                                     edge_labels=tx_labels,
                                     label_pos=0.8,
                                     ax=self.fig.axes[0])

        nx.draw_networkx_edge_labels(self.G, self.pos,
                                     edge_labels=rx_labels,
                                     label_pos=0.2,
                                     ax=self.fig.axes[0])

        # Display the qubits that have been transmitted across each of the
        # quantum channels in this timestep.
        qchls_data = tstep_data["qchls"]
        states = {}
        for qchl in qchls_data:
            state_str = ""
            if qchls_data[qchl]["state"] is not None:
                state_str = qchls_data[qchl]["state"]
            states[qchl] = state_str

        nx.draw_networkx_edge_labels(self.G, self.pos,
                                     edge_labels=states,
                                     font_weight="bold",
                                     bbox=dict(facecolor='w'),
                                     ax=self.fig.axes[0])

def main():
    ui = UI()
    ui.show()

if __name__ == '__main__':
    main()

# resetax = plt.axes([0.8, 0.025, 0.1, 0.04])
# button = Button(resetax, 'Reset', color=axcolor, hovercolor='0.975')

# def reset(event):
#     sfreq.reset()
#     samp.reset()
# button.on_clicked(reset)

# rax = plt.axes([0.025, 0.5, 0.15, 0.15], facecolor=axcolor)
# radio = RadioButtons(rax, ('red', 'blue', 'green'), active=0)

# def colorfunc(label):
#     l.set_color(label)
#     fig.canvas.draw_idle()
# radio.on_clicked(colorfunc)
