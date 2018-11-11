#!/bin/python3

from math import pi
from photon import Photon

NO_CONNECTIONS = {"in": [], "out": []}

class Equipment:

    def __init__(self, environment, label, connections=NO_CONNECTIONS):
        self.label = label
        # Configure connections
        self.connections = {"in": [environment], "out": [environment]}
        self.add_connections(connections)

    def log_action(self, action):
        # TODO: make a proper log
        print("{}: {}".format(self.label, action))

    def log_photon(self, uid):
        # TODO: make a proper log
        print("- Photon {} in {}".format(uid, self.label))

    def add_connections(self, connections):
        for key in connections:
            # Check that the key is valid ("in" or "out")
            if key not in self.connections.keys():
                break
            # Only connect a device if it is not already connected
            new_connections = []
            for device in connections[key]:
                if device not in self.connections[key]:
                    new_connections.append(device)
            # Add the new connections
            self.connections[key] += new_connections

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


##############################################################################
# Photon equipment
##############################################################################

class PhotonEquipment(Equipment):

    def __init__(self, environment, label, connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        # Configure default photon destination
        # If no devices are connected, then default to environment.
        self.photon_destination = environment
        # If any devices are connected, then default to the first device.
        if len(self.connections["out"]) > 1:
            self.photon_destination = self.connections["out"][1]

    def set_photon_destination(self, destination):
        if destination in self.connections["out"]:
            self.photon_destination = destination

    def handle_photon(self, photon, action=None):
        self.log_photon(photon.uid)

        if action is not None:
            action()

        progress = True
        if self.is_environment(self.photon_destination):
            progress = False

        return (self.photon_destination, progress)


class PhotonSource(PhotonEquipment):

    def __init__(self, environment, label="PhotonSource", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        self.photon_count = 0


class SinglePhotonSource(PhotonSource):

    def __init__(self, environment, label="SinglePhotonSource", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)

    def emit_photon(self):
        self.log_action("Emitting photon")

        # Emit a photon towards self.photon_destination
        Photon(self.photon_destination, uid=self.photon_count)
        self.photon_count += 1


class PulsedLaser(PhotonSource):

    pass


class Polariser(PhotonEquipment):

    def __init__(self, environment, label="Polariser", connections=NO_CONNECTIONS, theta=0):
        super().__init__(environment, label, connections)
        self.set_orientation(theta)

    def set_orientation(self, theta):
        '''Theta is the angle (anticlockwise) in radians between the
        horizontal axis and the preferred axis of the polariser.'''

        self.log_action("Setting orientation to {}".format(theta))
        self.orientation = theta

    def handle_photon(self, photon):

        def action():
            photon.polarise(self.orientation)

        return super().handle_photon(photon, action)


class PhotonDetector(PhotonEquipment):

    def __init__(self, environment, label="PhotonDetector", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        self.detecting_photons = False

    def activate(self):
        self.log_action("Activating")
        self.detecting_photons = True

    def deactivate(self):
        self.log_action("Deactivating")
        self.detecting_photons = False

    def detect_photon(self):
        self.log_action("Detecting photon")

    def handle_photon(self, photon):

        def action():
            if self.detecting_photons:
                self.detect_photon()

        return super().handle_photon(photon, action)


class Polarimeter(PhotonEquipment):

    def __init__(self, environment, label="Polarimeter", connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        self.measuring_photons = False
        self.basis = (0, pi/2)  # Default basis

    def activate(self):
        self.log_action("Activating")
        self.measuring_photons = True

    def deactivate(self):
        self.log_action("Deactivating")
        self.measuring_photons = False

    def set_basis(self, basis):
        self.basis = basis

    def measure_photon(self):
        if self.measuring_photons:
            self.log_action("Measuring photon")
            state = photon.measure(self.basis)
            print("* Received bit with value {}".format(state))

    def handle_photon(self, photon):

        def action():
            if self.measuring_photons:
                self.measure_photon()

        return super().handle_photon(photon, action)


class PhaseEncoder:
    """Many optical fibre based implementations described as BB84 use
    phase encoded states. -Wikipedia QKD"""

    def __init__(self):
        pass


##############################################################################
# Channels
##############################################################################

class Channel(Equipment):

    pass


class ClassicalChannel(Channel):

    pass


class QuantumChannel(Channel, PhotonEquipment):

    def __init__(self, environment, label="QuantumChannel", connections=NO_CONNECTIONS):
        super().__init__(label, environment, connections)

