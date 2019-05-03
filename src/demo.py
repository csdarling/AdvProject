import networkx as nx
import qkd_protocols as qkd
from user_interface import UI


class BB84(UI):

    def __init__(self):
        super().__init__()
        self.title = "2-party BB84"
        self.protocol = qkd.BB84()
        self.security = 0.95
        self.key_length = 128
        self.check_bit_prob = 0.2
        self.layout = nx.circular_layout


class BB84WithEavesdropping(UI):

    def __init__(self):
        super().__init__()
        self.title = "2-party BB84 with eavesdropping"
        self.protocol = qkd.BB84(eavesdropping=True)
        self.security = 0.95
        self.key_length = 128
        self.check_bit_prob = 0.2
        self.layout = nx.circular_layout


class BBM92(UI):

    def __init__(self):
        super().__init__()
        self.title = "2-party BBM92"
        self.protocol_id = 1
        self.security = 0.95
        self.key_length = 128
        self.check_bit_prob = 0.2


class BBM92WithEavesdropping(UI):

    def __init__(self):
        super().__init__()
        self.title = "2-party BBM92 with eavesdropping"
        self.protocol_id = 1
        self.security = 0.95
        self.key_length = 128
        self.check_bit_prob = 0.2
        self.intercepted_edges = [(0, 1)]


class ChainedBB84(UI):

    def __init__(self):
        super().__init__()
        self.title = "Chained BB84"
        self.protocol = qkd.ChainedBB84(4)
        self.security = 0.95
        self.key_length = 32
        self.check_bit_prob = 0.2


def main():
    bb84_ui = BB84()
    bb84_ui.show()

    bb84_with_eavesdropping_ui = BB84WithEavesdropping()
    bb84_with_eavesdropping_ui.show()

    chained_bb84 = ChainedBB84()
    chained_bb84.show()


if __name__ == '__main__':
    main()
