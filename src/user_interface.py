import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, RadioButtons
import k_party_protocol as kpp


class UI:

    def __init__(self):
        self.num_timesteps = 20
        self.run_protocol()
        self.setup_plot()
        self.setup_graph()
        self.stimestep.on_changed(self.update)
        plt.show()

    def run_protocol(self):
        k = 10
        self.protocol_id = 1
        self.bb84 = kpp.KPartyBB84(k, protocol=self.protocol_id)
        self.bb84.run_n_steps(self.num_timesteps)

    def setup_plot(self):
        self.fig, _ = plt.subplots()
        plt.subplots_adjust(bottom=0.25)
        axcolor = "#eeddee"
        axtime = plt.axes([0.2, 0.1, 0.65, 0.03], facecolor=axcolor)
        self.stimestep = Slider(axtime, 'Timestep', 0, self.num_timesteps, valinit=0, valstep=1, valfmt="%d", facecolor="#682860")

    def setup_graph(self):
        self.G = nx.DiGraph(self.bb84.network_manager.network.edges)
        if self.protocol_id == 0:
            self.pos = nx.circular_layout(self.G)
        else:
            self.pos = nx.spring_layout(self.G)
        nx.draw(self.G, self.pos, with_labels=True, ax=self.fig.axes[0],
                node_size=400, node_color="#682860",
                font_color='w', font_family="arial")

    def update(self, val):
        ui_timestep = self.stimestep.val

        data = self.bb84.get_stored_data_for_timestep(ui_timestep)
        qchls_data = data["qchls"]

        states = {}
        for qchl in qchls_data:
            state_str = ""
            if qchls_data[qchl]["state"] is not None:
                state_str = qchls_data[qchl]["state"]
            states[qchl] = state_str

        self.fig.axes[0].clear()
        nx.draw(self.G, self.pos, with_labels=True, ax=self.fig.axes[0],
                node_size=350, node_color="#682860",
                font_color='w', font_family="arial")

        nx.draw_networkx_edge_labels(self.G, self.pos, edge_labels=states,
                                     ax=self.fig.axes[0])

def main():
    ui = UI()

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
