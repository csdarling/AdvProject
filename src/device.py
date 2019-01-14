import random
import time
import threading
import copy
import warnings

from consts import *

class Device:

    def __init__(self, uid, env, name, c_components, q_components):
        self.uid = uid
        self.environment = env
        self.name = name
        self.c_components = c_components
        self.q_components = q_components

        # self.events = self.create_events()
        # self.events_lock = threading.Lock()
        # self.pass_events_to_components()
        # self.event_handler_threads = self.create_event_handler_threads()

        self.messages = []
        self.messages_lock = threading.Lock()
        self.process_messages_thread = threading.Thread(target=self.process_messages)
        self.process_messages_thread.daemon = True
        self.process_messages_thread.start()
        self.c_components[CLASSICALIO].set_messages(self.messages, self.messages_lock)

    # def create_events(self):
    #     events = {}
    #     for ev in EVENTS:
    #         events[ev] = threading.Event()
    #     return events

    # def pass_events_to_components(self):
    #     self.c_components[CLASSICALIO].set_events(self.events, self.events_lock)

    # def create_event_handler_threads(self):
    #     handler_threads = {}
    #     for ev_id in self.events:
    #         thr = threading.Thread(target=self.event_handler, args=(ev_id,))
    #         thr.daemon = True
    #         thr.start()
    #         handler_threads[ev_id] = thr
    #     return handler_threads

    # def event_handler(self, ev_id):
    #     is_set = self.events[ev_id].is_set()
    #     unchanged = lambda : is_set == self.events[ev_id].is_set()

    #     while unchanged():
    #         time.sleep(0.1)

    #     if ev_id == EV_SENDING_PHOTONS:
    #         if not self.events[ev_id].is_set():
    #             self.stop_sending_photons()

    #     else:
    #         print("Event: {}".format(self.events[ev_id]))

    #     self.event_handler(ev_id)

    def send_message(self, msg):
        self.c_components[CLASSICALIO].send_message(msg)

    def process_messages(self):
        TODO_tbd = True
        with self.messages_lock:
            for message in self.messages:
                target_uid = message[0]
                if target_uid == self.uid:
                    sender_uid = message[1]
                    msg = message[2]
                    if msg == MSG_START_BB84:
                        # self.messages.remove(message)
                        print("\n* Received MSG_START_BB84 *\n")
                        TODO_tbd = False
                        n = message[3]
                        bb84_thread = threading.Thread(target=self.bb84_receiver_protocol, args=(sender_uid, n))
                        bb84_thread.start()

                    else:
                        warnings.warn("Unexpected message received: {}".format(msg))

            # TODO remove processed messages
            # self.messages.clear()

        time.sleep(0.5)
        if TODO_tbd:
            self.process_messages()

    def wait_for_message(self, recipient, sender, msg):
        while True:
            with self.messages_lock:
                for m in self.messages:
                    if m[0] == recipient and m[1] == sender and m[2] == msg:
                        # TODO: Remove the message?
                        return m
            time.sleep(0.5)

    def wait_for_photon(self):
        photon_count = self.q_components[POLARIMETER].measurement_count
        while self.q_components[POLARIMETER].measurement_count == photon_count:
            time.sleep(0.1)

    def send_photons(self, freq):
        # with self.events_lock:
        #     self.events[EV_SENDING_PHOTONS].set()

        sps = self.q_components[SPS]
        sps.set_frequency(freq)
        sps.activate()

    def stop_sending_photons(self):
        sps = self.q_components[SPS]
        sps.deactivate()

    def send_n_photons(self, n, freq=1):
        sps = self.q_components[SPS]
        sps.set_frequency(freq)
        sps.activate()
        # try:
        while sps.photon_count < n:
            time.sleep(1 / (2 * freq))
        # finally:
        sps.deactivate()

    def send_photon(self):
        self.send_n_photons(1)

    def get_sps_timestamps(self):
        sps = self.q_components[SPS]
        return sps.timestamps

    def get_polarimeter_timestamps(self):
        polarimeter = self.q_components[POLARIMETER]
        return polarimeter.components[0].timestamps

    def bb84_sender_protocol(self, target_uid):
        n = 10  # Total number of photons to send to Bob
        bb84 = self.c_components[BB84]  # BB84 logic

        # Tell Bob to start the BB84 receiver protocol
        self.send_message((target_uid, self.uid, MSG_START_BB84, n))
        self.wait_for_message(self.uid, target_uid, MSG_ACK)

        # Generate n random bits and bases
        bits = bb84.generate_n_random_bits(n)
        bases = bb84.generate_n_random_bases(n)

        # Encode the bits as polarised photons and send to Bob
        for i, bit in enumerate(bits):
            basis = bases[i]
            print("\n-- Photon {} --\n".format(i))
            print("Alice's bit: {}\nAlice's basis: {}".format(bit, basis))
            self.q_components[POLARISER].set_orientation(basis[bit])
            self.send_photon()

        # Compare timestamps to work out which photons were received by Bob - TODO
        timestamps_msg = self.wait_for_message(self.uid, target_uid, MSG_COMPARE_TIMESTAMPS)

        # Compare bases
        bases_msg = self.wait_for_message(self.uid, target_uid, MSG_COMPARE_BASES)
        print("\nComparing bases...")
        target_bases = bases_msg[3]
        same_bases = [i for i, b in enumerate(target_bases) if b == bases[i]]
        print("Usable photons: {}".format(same_bases))
        time.sleep(1)

        # Send the indices of the usable photons to Bob
        self.send_message((target_uid, self.uid, MSG_COMPARE_BASES, same_bases))

        # Remove the bits where Alice and Bob's bases don't match to get the sifted key
        sifted_key = [bits[i] for i in same_bases]
        print("\n{}'s sifted key: {}".format(self.name, sifted_key))

        # Compare k bits to check for eavesdropping
        compare_bits_msg = self.wait_for_message(self.uid, target_uid, MSG_COMPARE_BITS)
        comparison_indices = compare_bits_msg[3]
        comparison_bits = compare_bits_msg[4]

        print("Comparison indices: {}".format(comparison_indices))
        print("Comparison bits:    {}".format(comparison_bits))

        identical = True
        for count, idx in enumerate(comparison_indices):
            if comparison_bits[count] != sifted_key[idx]:
                identical = False

        # self.send_message((target_uid, self.uid, MSG_BITS_MATCH, identical))

        # If they match, take the sifted key minus these bits as the shared secret key
        if identical:
            print("\nComparison bits match.")
            key = [bit for i, bit in enumerate(sifted_key) if i not in comparison_indices]
            print("\nShared secret key: {}\n".format(key))

        # Otherwise, re-run the protocol
        else:
            print("\nEavesdropping detected: re-running the protocol...\n")
            self.bb84_sender_protocol(target_uid)

    def bb84_receiver_protocol(self, sender_uid, n):
        bb84 = self.c_components[BB84]

        # Generate n random bases
        bases = bb84.generate_n_random_bases(n)
        self.send_message((sender_uid, self.uid, MSG_ACK))

        # Measure the photons w.r.t. these bases
        measured_bits = []
        for i in range(n):
            self.q_components[POLARIMETER].set_basis(bases[i])
            self.wait_for_photon()
            bit = self.q_components[POLARIMETER].current_measurement
            measured_bits.append(bit)
            print("Bob's basis: {}".format(bases[i]))
            print("{}'s bit: {}\n".format(self.name, bit))

        # Send Alice the timestamps so she can check which photons were received
        timestamps = self.q_components[POLARIMETER].get_timestamps()
        self.send_message((sender_uid, self.uid, MSG_COMPARE_TIMESTAMPS, timestamps))

        # Send Alice the random bases so she can check which of their bases match
        self.send_message((sender_uid, self.uid, MSG_COMPARE_BASES, bases))
        time.sleep(1)

        # Wait for Alice to tell Bob which bases match
        same_bases_msg = self.wait_for_message(self.uid, sender_uid, MSG_COMPARE_BASES)
        same_bases = same_bases_msg[3]

        # Remove the bits where Alice and Bob's bases do not match to get the sifted key
        sifted_key = [measured_bits[i] for i in same_bases]
        print("{}'s sifted key: {}\n".format(self.name, sifted_key))

        k = 2  # The number of bits to compare

        # Take a random sample of k bits
        comparison_bits_indices = sorted(random.sample(range(len(sifted_key)), k))
        comparison_bits = [sifted_key[i] for i in comparison_bits_indices]

        # Send the values of these bits along with their positions in the sifted key
        self.send_message((sender_uid, self.uid, MSG_COMPARE_BITS, comparison_bits_indices, comparison_bits))

