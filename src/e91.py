import random
import numpy as np
import time
import components

from math import log, ceil


class E91:

    def __init__(self, eve=False, min_key_length=0):
        self.min_key_length = min_key_length
        alice = components.Party(0, "Alice", cchl=self)
        bob = components.Party(1, "Bob", cchl=self)

        # ADDED ####################################
        epr_source = components.EPRPairSource()
        ############################################

        qchl = components.QuantumChannel()

        qchl.add_socket(alice.uid, alice.socket)
        alice.connect_to_qchl(qchl)
        qchl.add_socket(bob.uid, bob.socket)
        bob.connect_to_qchl(qchl)
        qchl.add_edge(alice.uid, bob.uid)
        alice.set_target(bob.uid)

        self.alice = alice
        self.bob = bob
        self.qchl = qchl
        # ADDED ####################################
        self.epr_source = epr_source
        ############################################

        self.eve = None
        if eve:
            self.add_eve()

        self.eve_check_complete = False
        self.secret_key = ""

    def reset(self):
        self.alice.reset()
        self.bob.reset()
        # ADDED ####################################
        self.epr_source.reset()
        ############################################

        if self.eve is not None:
            self.eve.reset()

        self.eve_check_complete = False
        self.secret_key = ""

    def display_data(self):
        alice = self.alice
        bob = self.bob
        eve = self.eve

        print()
        # EDITED #########################################################
        print("Total qubits sent:  {}".format(self.epr_source.total_sent))
        ##################################################################
        print("Sifted key length:  {}".format(bob.sifted_key_length))
        print()
        print("Alice's bits:       {}".format(alice.bits))
        print("Alice's bases:      {}".format(alice.bases))

        if eve is not None:
            print()
            print("Eve's bits:         {}".format(eve.bits))
            print("Eve's bases:        {}".format(eve.bases))

        print()
        print("Bob's bits:         {}".format(bob.bits))
        print("Bob's bases:        {}".format(bob.bases))

        print()
        print("Alice's sifted key: {}".format(alice.format_sifted_key()))
        print("Bob's sifted key:   {}".format(bob.format_sifted_key()))
        print()

    def send_qubit(self, display_data=True):
        if self.eve_check_complete:
            self.eve_check_complete = False

        # EDITED ####################################
        self.epr_source.send_qubit(self.alice.socket,
                                   self.bob.socket)
        #############################################

        if display_data:
            self.display_data()

    def send_qubits(self, n, display_data=True):
        if self.eve_check_complete:
            self.eve_check_complete = False

        # EDITED ########################################
        for i in range(n):
            self.epr_source.send_qubit(self.alice.socket,
                                       self.bob.socket)
        #################################################

        if display_data:
            self.display_data()

    def establish_key(self, length, security):
        self.reset()
        num_eve_check_bits = self.calculate_num_eve_check_bits(security)
        required_sifted_key_length = length + num_eve_check_bits

        while self.alice.sifted_key_length < required_sifted_key_length:
            self.send_qubit(display_data=False)

        self.display_data()
        self.check_for_eve(security)

    def dynamically_establish_key(self, check_rate=5, security=0.95):
        self.reset()
        required_num_check_bits = self.calculate_num_eve_check_bits(security)
        num_check_bits = 0
        while num_check_bits < required_num_check_bits:
            self.send_qubit(display_data=False)
            bases_match = lambda : self.alice.bases[-1] == self.bob.bases[-1]

            random_num = random.random()
            if (self.alice.sifted_key_length and bases_match()
                and random_num < 1.0 / check_rate):

                num_check_bits += 1
                self.alice.add_check_bit()
                self.bob.add_check_bit()

            self.display_data()
            print("Alice's check bits: {}".format(self.alice.format_check_bits()))
            print("Bob's check bits:   {}".format(self.bob.format_check_bits()))
            print("\nAlice's secret key: {}".format(self.alice.format_secret_key()))
            print("Bob's secret key:   {}".format(self.bob.format_secret_key()))

            # Compare Alice and Bob's check bits
            if (self.alice.check_bits and self.bob.check_bits and
                self.alice.check_bits[-1] != self.bob.check_bits[-1]):

                print("\nEavesdropping detected! Aborting this run of the protocol.\n")
                self.reset()
                break

            current_security = self.calculate_eve_prob(num_check_bits)
            print("\nKey security: {:.3f}%.\n".format(current_security * 100))

            time.sleep(0.2)

    def add_eve(self):
        eve = components.Party(2, "Eve", cchl=self, is_eve=True)
        self.qchl.add_socket(eve.uid, eve.socket)
        eve.connect_to_qchl(self.qchl)
        self.qchl.intercept_edge((self.alice.uid, self.bob.uid), eve.uid)
        eve.set_target(self.bob.uid)
        self.eve = eve

    def calculate_num_eve_check_bits(self, security):
        return ceil(log(1 - security) / log(0.75))

    def calculate_eve_prob(self, num_check_bits):
        # Given n matching check bits, calculate the least upper bound for the
        # probability that Eve has gotten away with eavesdropping.

        value = 0
        upper_bound = 1

        while upper_bound - value > 0.0001:
            value_attempt = value + (upper_bound - value) / 2
            n = self.calculate_num_eve_check_bits(value_attempt)
            if n > num_check_bits:
                upper_bound = value_attempt
            elif n <= num_check_bits:
                value = value_attempt

        return value

        if self.eve_check_complete:
            return

        num_bits = self.calculate_num_eve_check_bits(security)
        sifted_key_length = self.alice.sifted_key_length

        if sifted_key_length - num_bits < self.min_key_length:
            print("Not enough bits to run eavesdropping test.\n")

        else:
            idxs = sorted(random.sample(self.alice.sifted_key_idxs, num_bits))
            self.alice.add_check_bits(idxs)
            self.bob.add_check_bits(idxs)

            print("Alice's check bits: {}".format(self.alice.format_check_bits()))
            print("Bob's check bits:   {}".format(self.bob.format_check_bits()))

            if self.alice.check_bits == self.bob.check_bits:
                print("\nKey security: {:.3f}%.\n".format(security * 100))
                print("Secret key:         {}\n".format(self.alice.format_secret_key()))
                self.eve_check_complete = True
                self.secret_key = self.alice.secret_key

            else:
                print("\nEavesdropping detected! Aborting this run of the protocol.\n")
                self.reset()

    def check_for_eve(self, security=0.95):
        if self.eve_check_complete:
            return

        num_bits = self.calculate_num_eve_check_bits(security)
        sifted_key_length = self.alice.sifted_key_length

        if sifted_key_length - num_bits < self.min_key_length:
            print("Not enough bits to run eavesdropping test.\n")

        else:
            idxs = sorted(random.sample(self.alice.sifted_key_idxs, num_bits))
            self.alice.add_check_bits(idxs)
            self.bob.add_check_bits(idxs)

            print("Alice's check bits: {}".format(self.alice.format_check_bits()))
            print("Bob's check bits:   {}".format(self.bob.format_check_bits()))

            if self.alice.check_bits == self.bob.check_bits:
                print("\nKey security: {:.3f}%.\n".format(security * 100))
                print("Secret key:         {}\n".format(self.alice.format_secret_key()))
                self.eve_check_complete = True
                self.secret_key = self.alice.secret_key

            else:
                print("\nEavesdropping detected! Aborting this run of the protocol.\n")
                self.reset()

    def compare_bases(self):
        # ADDED ########################################
        if len(self.alice.bases) == len(self.bob.bases):
        ################################################

            match = False
            if self.alice.bases[-1] == self.bob.bases[-1]:
                match = True

            self.alice.update_sifted_key(match)
            self.bob.update_sifted_key(match)
