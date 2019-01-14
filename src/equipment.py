#!/bin/python3

import time
import random
import threading
import multiprocessing as mp
from math import pi
from photon import Photon
from consts import *

NO_CONNECTIONS = {"in": [], "out": []}

class Equipment:

    def __init__(self, uid, environment, label, connections=NO_CONNECTIONS):
        self.uid = uid
        self.label = label
        # Configure internal connections
        self.connections = {"in": [environment], "out": [environment]}
        self.add_connections(connections)

    def log_action(self, action, log=False):
        # TODO: make a proper log
        if log:
            print("{}: {}".format(self.label, action))

    def add_connections(self, connections):
        for direction in connections:
            # Check that the direction is valid ("in" or "out").
            valid_keys = list(self.connections.keys())
            if direction not in valid_keys:
                break
            key_id = valid_keys.index(direction)
            # Only connect a device if it is not already connected.
            for device in connections[direction]:
                if device not in self.connections[direction]:
                    # print("Adding {} to {} ({}) connections\n".format(device.label, self.label, direction))
                    self.connections[direction].append(device)
                    other_direction = valid_keys[(key_id + 1) % 2]
                    # Add the connection to the other device in the other direction.
                    if self not in device.connections[other_direction]:
                        device.add_connections({other_direction: [self]})

    def remove_connections(self, connections):
        for key in connections:
            # Check that the key is valid ("in" or "out")
            if key not in self.connections.keys():
                break
            # Remove all specified connections, provided they exist
            for device in connections[key]:
                if device in self.connections[key]:
                    self.connections[key].remove(device)

    def is_environment(self, obj):
        '''Checks if the given object is the environment.'''
        return True if obj == self.connections["out"][0] else False


class IO(Equipment):

    def __init__(self, uid, environment, label, connections=NO_CONNECTIONS, parent_device=None):
        super().__init__(uid, environment, label, connections)
        self.read_conn = None
        self.write_conn = None
        self.listening = threading.Event()
        self.listen_thread = None

    def add_conns(self, read_conn, write_conn):
        self.read_conn = read_conn
        self.write_conn = write_conn
        self.start_listening()
        if hasattr(self, "listen"):
            self.listen_thread = threading.Thread(target=self.listen)
            self.listen_thread.daemon = True
            self.listen_thread.start()

    def start_listening(self):
        if self.read_conn is not None:
            self.listening.set()

    def stop_listening(self):
        self.listening.clear()


##############################################################################
# Classical equipment
##############################################################################

class ClassicalEquipment(Equipment):

    pass


class Bb84(ClassicalEquipment):

    STANDARD_BASIS = (0, pi/2)
    HADAMARD_BASIS = (pi/4, 3 * (pi/4))
    START   = 0
    ACK     = 1
    COMPARE = 2

    def __init__(self, uid, environment, label, photon_equipment=None, user_name=None, connections=NO_CONNECTIONS):
        super().__init__(uid, environment, label, connections)
        self.devices = photon_equipment
        self.name = user_name

    def set_mode(self, mode):
        # Sending or receiving
        self.mode = mode

    def add_devices(self, devices):
        self.devices = devices

    def generate_n_random_bits(self, n):
        random_bits = []
        for i in range(n):
            random_bits.append(random.choice([0, 1]))

        return random_bits

    def generate_n_random_bases(self, n):
        random_bases = []
        random_bits = self.generate_n_random_bits(n)
        for bit in random_bits:
            if bit == 0:
                random_bases.append(Bb84.STANDARD_BASIS)
            elif bit == 1:
                random_bases.append(Bb84.HADAMARD_BASIS)

        return random_bases

    def send_qubits(bits, bases):
        for i in range(len(bits)):
            bit = bits[i]
            basis = bases[i]
            self.devices["Polariser"].set_orientation(basis[bit])
            self.devices["SinglePhotonSource"].emit_photon()

    def wait_for_msg(self, cchl, msg):
        source = None
        msg_received = False
        while not msg_received:
            msg_tuples = cchl.get_all_messages(self, self.name)
            for src, m in msg_tuples:
                if m == msg:
                    msg_received = True
                    source = src
                    break

        return source

    def wait_for_msg_from_target(self, cchl, msg, target):
        msgs = cchl.get_all_messages(self, self.name)
        while not (target, msg) in msgs:
            msgs = cchl.get_all_messages(self, self.name)

    def run_sender_protocol(self, target, n):
        cchl = self.connections["out"][1]
        cchl.send_message(target, self.name, Bb84.START)

        # p_wait_ack = mp.Process(target=listen)
        # p_wait_ack.start()
        # p_wait_ack.join()

        self.wait_for_msg_from_target(cchl, Bb84.ACK, target)

        random_bits = self.generate_n_random_bits(n)
        random_bases = self.generate_n_random_bases(n)
        self.send_qubits(random_bits, random_bases)

        self.wait_for_msg_from_target(cchl, Bb84.COMPARE, target)

    def run_receiver_protocol(self, n):
        cchl = self.connections["out"][1]
        target = self.wait_for_msg(cchl, Bb84.START)

        # TODO: Get ready for BB84
        # E.g. set up photon equipment...
        polarimeter = self.devices[POLARIMETER]
        meas_count = 0
        measurements = []

        cchl.send_message(target, self.name, Bb84.ACK)

        while meas_count < n:
            # Check to see if a new measurement has been recorded
            if meas_count < polarimeter.measurement_count:
                # Read the measurement
                measurements.append(polarimeter.measurement)
                # Set a new random basis
                basis = self.generate_n_random_bases(1)
                polarimeter.set_basis(basis)
                # Increment the measurement count
                meas_count = polarimeter.measurement_count

        cchl.send_message(target, self.name, Bb84.COMPARE)
        # self.wait_for_msg_from_target(cchl, Bb84.COMPARE, target)


class ClassicalIO(IO, ClassicalEquipment):

    def __init__(self, uid, environment, label="ClassicalIO", connections=NO_CONNECTIONS, parent_device=None):
        super().__init__(uid, environment, label, connections)

    def set_messages(self, messages, messages_lock):
        self.messages = messages
        self.messages_lock = messages_lock

    def send_message(self, msg):
        self.write_conn.send(msg)

    def listen(self):
        while not self.listening.is_set():
            time.sleep(0.1)

        while self.listening.is_set():
            message = self.read_conn.recv()
            # print("\n{} received message {}".format(self.label, message))

            with self.messages_lock:
                self.messages.append(message)


##############################################################################
# Photon equipment
##############################################################################

class PhotonEquipment(Equipment):

    def __init__(self, uid, environment, label, connections=NO_CONNECTIONS):
        super().__init__(uid, environment, label, connections)
        # Set default photon destination to be the environment.
        self.photon_destination = environment

    def log_photon(self, uid, log=False):
        # TODO: make a proper log
        if log:
            print("Photon {} in {}".format(uid, self.label))

    def add_connections(self, connections):
        super().add_connections(connections)
        # If any devices are connected, then default to the first device.
        if len(self.connections["out"]) > 1:
            self.photon_destination = self.connections["out"][1]

    def set_photon_destination(self, destination):
        if destination in self.connections["out"]:
            self.photon_destination = destination

    def handle_photon(self, photon, action=None, action_params=()):
        self.log_photon(photon.uid)

        if action is not None:
            action(*action_params)

        progress = True
        if self.is_environment(self.photon_destination):
            progress = False

        return (self.photon_destination, progress)


class PhotonSource(PhotonEquipment):

    def __init__(self, uid, environment, label="PhotonSource", connections=NO_CONNECTIONS):
        super().__init__(uid, environment, label, connections)
        self.photon_count = 0


class SinglePhotonSource(PhotonSource):

    def __init__(self, uid, environment, label="SinglePhotonSource", connections=NO_CONNECTIONS):
        super().__init__(uid, environment, label, connections)
        self.active = threading.Event()
        self.frequency = 1
        self.emit_photons_thread = None
        self.timestamps = []
        self.system_photons = None
        self.system_photons_lock = None

    def add_system_photons(self, system_photons, lock):
        self.system_photons = system_photons
        self.system_photons_lock = lock

    def set_frequency(self, freq):
        self.frequency = freq

    def emit_photon(self):
        self.log_action("Emitting photon")
        self.timestamps.append(time.time())

        # Emit a photon towards self.photon_destination
        photon = Photon(self.photon_destination, uid=self.photon_count, location=self.label)
        with self.system_photons_lock:
            self.system_photons[self.photon_count] = photon
        self.photon_count += 1

    def emit_photons(self):
        freq = self.frequency
        while self.active.is_set():
            self.emit_photon()
            time.sleep(1.0 / freq)

    def activate(self):
        if not self.active.is_set():
            self.active.set()
            self.emit_photons_thread = threading.Thread(target=self.emit_photons)
            self.emit_photons_thread.daemon = True  # TODO: Should this really be a daemon?
            self.emit_photons_thread.start()

    def deactivate(self):
        if self.active.is_set():
            self.active.clear()
            self.emit_photons_thread.join()


class PulsedLaser(PhotonSource):

    pass


class Polariser(PhotonEquipment):

    def __init__(self, uid, environment, label="Polariser", connections=NO_CONNECTIONS, parent_device=None, theta=0):
        super().__init__(uid, environment, label, connections)
        self.set_orientation(theta)
        self.parent_device = parent_device
        self.reflect_destination = None

    def set_orientation(self, theta):
        '''Theta is the angle (anticlockwise) in radians between the
        horizontal axis and the preferred axis of the polariser.'''

        self.log_action("Setting orientation to {}".format(theta))
        self.orientation = theta

    def handle_photon(self, photon):

        def action():
            polarisation_axis = photon.polarise(self.orientation)
            # print("filter orientation = {}".format(self.orientation))
            # print("photon polarisation_axis = {}".format(polarisation_axis))
            if polarisation_axis != self.orientation:
                if self.reflect_destination is not None:
                    self.photon_destination = self.reflect_destination
                else:
                    self.photon_destination = self.connections["out"][0]

        photon_destination = self.photon_destination
        feedback = super().handle_photon(photon, action)
        self.photon_destination = photon_destination
        return feedback

    def reflect_to(self, destination):
        self.reflect_destination = destination


class PhotonDetector(PhotonEquipment):

    def __init__(self, uid, environment, label="PhotonDetector", connections=NO_CONNECTIONS, parent_device=None):
        super().__init__(uid, environment, label, connections)
        self.photon_count = 0
        self.parent_device = parent_device
        self.timestamps = []

    # def activate(self):
    #     self.log_action("Activating")
    #     self.detecting_photons = True

    # def deactivate(self):
    #     self.log_action("Deactivating")
    #     self.detecting_photons = False

    def detect_photon(self):
        self.log_action("Detecting photon")
        self.timestamps.append(time.time())
        self.photon_count += 1

    def handle_photon(self, photon):

        def action():
            self.detect_photon()

        feedback = super().handle_photon(photon, action)

        if self.parent_device is not None:
            self.parent_device.control_logic(self.label)

        return feedback


class Polarimeter(PhotonEquipment):

    def __init__(self, uid, environment, label="Polarimeter", connections=NO_CONNECTIONS, basis=(pi/2, 0)):
        super().__init__(uid, environment, label, connections)

        labels = ["Detector1", "Polariser", "Detector2", "Detector3"]
        labels = [self.label + "." + label for label in labels]

        self.component_ids = labels
        self.components = [
            # TODO: All these components have the same uids!
            PhotonDetector(uid, environment, label=labels[0], parent_device = self),
            Polariser(uid, environment, label=labels[1], parent_device = self),
            PhotonDetector(uid, environment, label=labels[2], parent_device = self),
            PhotonDetector(uid, environment, label=labels[3], parent_device = self)
        ]

        self.components[0].add_connections({"in": connections["in"],
                                            "out": [self.components[1]]})
        self.components[1].add_connections({"out": [self.components[2],
                                                    self.components[3]]})
        self.components[2].add_connections({"out": connections["out"]})
        self.components[3].add_connections({"out": connections["out"]})

        self.set_basis(basis)
        self.current_measurement = 0
        self.measurement_count = 0

        self.components[1].reflect_to(self.components[3])

    def set_basis(self, basis):
        absorbed = basis[0]
        passes = basis[1]
        self.components[1].set_orientation(passes)
        self.basis = basis

    # def add_connections(self, connections):
    #     super().add_connections(connections)
    #     if "in" in connections.keys():
    #         self.components[0].add_connections(connections["in"])
    #     elif "out" in connections.keys():
    #         self.components[2].add_connections(connections["out"])

    def get_timestamps(self):
        return self.components[0].timestamps

    def handle_photon(self, photon):
        return self.components[0].handle_photon(photon)

    def control_logic(self, component_id):
        index = self.component_ids.index(component_id)

        if index == 0:
            # TODO: PhotonDetector1 currently has no function (but will in future).
            pass

        elif index == 2:
            # The photon has passed through the Polariser and been detected by
            # PhotonDetector2.
            self.current_measurement = 1
            self.measurement_count += 1

        elif index == 3:
            # The photon has been absorbed by the Polariser. This is currently
            # modelled as the photon being reflected towards PhotonDetector3.
            self.current_measurement = 0
            self.measurement_count += 1


class PhaseEncoder:
    """Many optical fibre based implementations described as BB84 use
    phase encoded states. -Wikipedia QKD"""

    def __init__(self):
        pass


class PhotonIO(IO, PhotonEquipment):

    def __init__(self, uid, environment, label="PhotonIO", connections=NO_CONNECTIONS, parent_device=None):
        super().__init__(uid, environment, label, connections)

    def listen(self):
        while not self.listening.is_set():
            time.sleep(0.1)

        while self.listening.is_set():
            photon = self.read_conn.recv()
            # print("{} received photon {}".format(self.label, photon))
            # TODO: Change this!!
            photon._destination = self.photon_destination
            photon._progress()

        self.listen()

    def send_photon(self, photon):
        # TODO: Shouldn't need this time.sleep - find a way to remove it.
        time.sleep(0.1)
        if self.write_conn is not None:
            self.write_conn.send(photon)

    def handle_photon(self, photon):

        # TODO: The following doesn't work - not quite sure why.
        # def action(photon):
        #     # self.send_photon(photon)
        #     th = threading.Thread(target=self.send_photon, args=(photon,))
        #     th.start()
        # return super().handle_photon(photon, action, (photon,), prog=False)

        # TODO: The handle_photon method MUST return before the send_photon
        # method can be used. The following is a solution, but not a good one.
        th = threading.Thread(target=self.send_photon, args=(photon,))
        th.start()
        return (None, False)


##############################################################################
# Channels
##############################################################################

class Channel(Equipment):

    pass


class ClassicalChannel(Channel, ClassicalEquipment):

    def __init__(self, environment, label="ClassicalChannel", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        self.messages = []

    def send_message(self, target, source, message):
        print(">> Sending message: {}".format((target, source, message)))
        time.sleep(0.1)
        self.messages.append((target, source, message))
        print(">> Message sent")
        # print("Messages in CChl: {}".format(self.messages))

    def get_all_messages(self, requester, target_name):
        messages = []
        for target, source, msg in self.messages:
            if target == target_name:
                messages.append((source, msg))

        # If the requester is the intended device, then remove the
        # messages from the channel. This represents reaching the
        # physical end of a channel, e.g. the end of a wire.
        #
        # TODO: Using the requester name might be dodgy - could Eve
        # set her name to be the same as the target's?
        if requester.name == target_name:
            for source, msg in messages:
                self.messages.remove((target_name, source, msg))

        return messages


class QuantumChannel(Channel, PhotonEquipment):

    def __init__(self, environment, label="QuantumChannel", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)

