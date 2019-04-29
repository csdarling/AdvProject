import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons
from matplotlib.offsetbox import AnchoredText
from matplotlib.patches import Rectangle

import shared_fns


class UI:

    def __init__(self):
        self.title = ""
        self.k = None
        self.edges = None
        self.protocol_id = 0
        self.num_iterations = None
        self.security = 0.95
        self.key_length = 128
        self.check_bit_prob = 0.2
        self.intercepted_edges = []
        self.ui_timestep = 0
        self.paused = True
        self.layout = nx.circular_layout

    def show(self):
        self.run_protocol()
        self.setup_plot()
        self.setup_network()
        self.s_timestep.on_changed(self.update)
        self.b_play.on_clicked(self.play)
        self.b_pause.on_clicked(self.pause)
        self.b_first_tstep.on_clicked(self.first_tstep)
        self.b_prev_tstep.on_clicked(self.prev_tstep)
        self.b_next_tstep.on_clicked(self.next_tstep)
        self.b_last_tstep.on_clicked(self.last_tstep)
        plt.show()

    def run_protocol(self):
        self.protocol.run(num_iterations=self.num_iterations,
                          security=self.security,
                          key_length=self.key_length)

    def setup_plot(self):

        def set_button_colours():
            ax.spines["top"].set_color(b_colour)
            ax.spines["left"].set_color(b_colour)
            ax.spines["bottom"].set_color(spine_colour)
            ax.spines["right"].set_color(spine_colour)

        self.fig = plt.figure()
        self.fig.canvas.set_window_title(self.title)

        ax = plt.axes([0.125, 0.3, 0.62, 0.6], facecolor='w')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)

        spine_colour = "#555555"
        # Display the keys.
        ax = plt.axes([0.76, 0.15, 0.14, 0.75], facecolor='w')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        for side in ax.spines:
            ax.spines[side].set_color(spine_colour)

        text = AnchoredText("Key bits", loc=2,  # Upper left
                            prop=dict(fontfamily="monospace",
                                      wrap=True,
                                      bbox=dict(facecolor='w',
                                                edgecolor="none")))
        ax.add_artist(text)

        # Display the messages from the classical channel.
        ax = plt.axes([0.125, 0.15, 0.62, 0.13], facecolor='w')
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        for side in ax.spines:
            ax.spines[side].set_color(spine_colour)

        text = AnchoredText("Classical messages", loc=2,  # Upper left
                            prop=dict(fontfamily="monospace",
                                      bbox=dict(facecolor='w',
                                                edgecolor="none")))
        ax.add_artist(text)

        # Add the timestep slider.
        s_facecolour1 = "#eeeeee"
        s_facecolour2 = "#682860"
        ax = plt.axes([0.125, 0.1, 0.775, 0.03], facecolor=s_facecolour1)
        for side in ax.spines:
            ax.spines[side].set_color(spine_colour)
        self.s_timestep = Slider(ax, 'Step', 0,
                                 self.protocol.num_iterations,
                                 valinit=0, valstep=1,
                                 valfmt="%d",  # Display as an integer.
                                 facecolor=s_facecolour2)

        b_colour = "#dddddd"
        # Add the play button.
        ax = plt.axes([0.125, 0.04, 0.08, 0.04])
        set_button_colours()
        self.b_play = Button(ax, "Play", color=b_colour, hovercolor='0.975')
        # Add the pause button.
        ax = plt.axes([0.225, 0.04, 0.08, 0.04])
        set_button_colours()
        self.b_pause = Button(ax, "Pause", color=b_colour, hovercolor='0.975')
        # Add the "<<" back to beginning button.
        ax = plt.axes([0.60, 0.04, 0.06, 0.04])
        set_button_colours()
        self.b_first_tstep = Button(ax, "<<", color=b_colour, hovercolor='0.975')
        # Add the "<" previous timestep button.
        ax = plt.axes([0.68, 0.04, 0.06, 0.04])
        set_button_colours()
        self.b_prev_tstep = Button(ax, "<", color=b_colour, hovercolor='0.975')
        # Add the ">" next timestep button.
        ax = plt.axes([0.76, 0.04, 0.06, 0.04])
        set_button_colours()
        self.b_next_tstep = Button(ax, ">", color=b_colour, hovercolor='0.975')
        # Add the ">>" final timestep button.
        ax = plt.axes([0.84, 0.04, 0.06, 0.04])
        set_button_colours()
        self.b_last_tstep = Button(ax, ">>", color=b_colour, hovercolor='0.975')

    def setup_network(self):
        self.network = nx.DiGraph(self.protocol.network_manager.network.edges)
        self.pos = self.layout(self.network)
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
        nx.draw_networkx_nodes(self.network, self.pos,
                               nodelist=self.legitimate_parties,
                               node_size=400, node_color="#682860")

        nx.draw_networkx_nodes(self.network, self.pos,
                               nodelist=self.eavesdropping_parties,
                               node_size=400, node_color="#eeddee")

        nx.draw_networkx_labels(self.network, self.pos,
                                nodelist=self.legitimate_parties,
                                labels=self.legitimate_party_names,
                                font_color='w', font_family="arial")

        nx.draw_networkx_labels(self.network, self.pos,
                                nodelist=self.eavesdropping_parties,
                                labels=self.eavesdropping_party_names,
                                font_color='k', font_family="arial")

        nx.draw_networkx_edges(self.network, self.pos)

    def play(self, ev):
        self.paused = False
        while (not self.paused and
               self.ui_timestep < self.protocol.num_iterations):
            self.next_tstep(pause=False)
            plt.pause(0.25)

    def pause(self, ev):
        self.paused = True

    def first_tstep(self, ev=None):
        self.paused = True
        if self.ui_timestep:
            self.ui_timestep = 0
            self.s_timestep.set_val(self.ui_timestep)

    def prev_tstep(self, ev=None):
        self.paused = True
        if self.ui_timestep > 0:
            self.ui_timestep -= 1
            self.s_timestep.set_val(self.ui_timestep)

    def next_tstep(self, ev=None, pause=True):
        self.paused = pause
        if self.ui_timestep < self.protocol.num_iterations:
            self.ui_timestep += 1
            self.s_timestep.set_val(self.ui_timestep)

    def last_tstep(self, ev=None):
        self.paused = True
        if self.ui_timestep < self.protocol.num_iterations:
            self.ui_timestep = self.protocol.num_iterations
            self.s_timestep.set_val(self.ui_timestep)

    def update(self, val):

        def get_tx_label(tx_party, rx_uid):
            bit = tx_party["tx_bits"][self.ui_timestep][rx_uid]
            basis = tx_party["tx_bases"][self.ui_timestep][rx_uid]
            basis_char = shared_fns.represent_basis_by_char(basis)
            label = "({}, {})".format(bit, basis_char)
            return label

        def get_rx_label(rx_party, tx_uid):
            bit = rx_party["rx_bits"][self.ui_timestep][tx_uid]
            basis = rx_party["rx_bases"][self.ui_timestep][tx_uid]
            basis_char = shared_fns.represent_basis_by_char(basis)
            label = "({}, {})".format(bit, basis_char)
            return label

        self.ui_timestep = int(self.s_timestep.val)
        tstep_data = self.protocol.get_stored_data_for_timestep(self.ui_timestep)
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
            if self.ui_timestep in party["tx_bits"]:
                for rx_uid in party["tx_bits"][self.ui_timestep]:
                    label = get_tx_label(party, rx_uid)
                    # If there is a quantum channel connecting the parties.
                    if (uid, rx_uid) in network_edges:
                        tx_labels[(uid, rx_uid)] = label
                    # If the edge has been intercepted.
                    else:
                        eve_uid = nx.shortest_path(self.network, uid, rx_uid)[1]
                        tx_labels[(uid, eve_uid)] = label
            # Make the rx_labels.
            if self.ui_timestep in party["rx_bits"]:
                for tx_uid in party["rx_bits"][self.ui_timestep]:
                    label = get_rx_label(party, tx_uid)
                    # If there is a quantum channel connecting the parties.
                    if (tx_uid, uid) in network_edges:
                        rx_labels[(tx_uid, uid)] = label
                    # If the edge has been intercepted.
                    else:
                        eve_uid = nx.shortest_path(self.network, tx_uid, uid)[1]
                        rx_labels[(eve_uid, uid)] = label

        nx.draw_networkx_edge_labels(self.network, self.pos,
                                     edge_labels=tx_labels,
                                     label_pos=0.8,
                                     ax=self.fig.axes[0])

        nx.draw_networkx_edge_labels(self.network, self.pos,
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

        nx.draw_networkx_edge_labels(self.network, self.pos,
                                     edge_labels=states,
                                     font_weight="bold",
                                     bbox=dict(facecolor='w'),
                                     ax=self.fig.axes[0])

def main():
    ui = UI()
    ui.show()

if __name__ == '__main__':
    main()

