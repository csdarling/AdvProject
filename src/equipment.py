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


##############################################################################
# Photon equipment
##############################################################################

class PhotonEquipment(Equipment):

    def __init__(self, environment, label, connections=NO_CONNECTIONS):
        super().__init__(environment, label, connections)
        # Set default photon destination to be the environment.
        self.photon_destination = environment

    def log_photon(self, uid):
        # TODO: make a proper log
        print("- Photon {} in {}".format(uid, self.label))

    def add_connections(self, connections):
        super().add_connections(connections)
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

    def __init__(self, environment, label="Polariser", connections=NO_CONNECTIONS, parent_device=None, theta=0):
        super().__init__(environment, label, connections)
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
            print("orientation = {}".format(self.orientation))
            print("polarisation_axis = {}".format(polarisation_axis))
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

    def __init__(self, environment, label="PhotonDetector", connections=NO_CONNECTIONS, parent_device=None):
        super().__init__(environment, label, connections)
        self.photon_count = 0
        self.parent_device = parent_device

    # def activate(self):
    #     self.log_action("Activating")
    #     self.detecting_photons = True

    # def deactivate(self):
    #     self.log_action("Deactivating")
    #     self.detecting_photons = False

    def detect_photon(self):
        self.log_action("Detecting photon")
        self.photon_count += 1

    def handle_photon(self, photon):

        def action():
            self.detect_photon()

        feedback = super().handle_photon(photon, action)

        if self.parent_device is not None:
            self.parent_device.control_logic(self.label)

        return feedback

class Polarimeter(PhotonEquipment):

    def __init__(self, environment, label="Polarimeter", connections=NO_CONNECTIONS, basis=(pi/2, 0)):
        super().__init__(environment, label, connections)

        labels = ["Detector1", "Polariser", "Detector2", "Detector3"]
        labels = [self.label + "." + label for label in labels]

        self.component_ids = labels
        self.components = [
            PhotonDetector(environment, label=labels[0], parent_device = self),
            Polariser(environment, label=labels[1], parent_device = self),
            PhotonDetector(environment, label=labels[2], parent_device = self),
            PhotonDetector(environment, label=labels[3], parent_device = self)
        ]

        self.components[0].add_connections({"in": connections["in"],
                                            "out": [self.components[1]]})
        self.components[1].add_connections({"out": [self.components[2],
                                                    self.components[3]]})
        self.components[2].add_connections({"out": connections["out"]})
        self.components[3].add_connections({"out": connections["out"]})

        self.set_basis(basis)
        self.current_measurement = 0

        self.components[1].reflect_to(self.components[3])

    # def activate(self):
    #     self.log_action("Activating")
    #     self.measuring_photons = True

    # def deactivate(self):
    #     self.log_action("Deactivating")
    #     self.measuring_photons = False

    def set_basis(self, basis):
        absorbed = basis[0]
        passes = basis[1]
        self.components[1].set_orientation(passes)

    # def add_connections(self, connections):
    #     super().add_connections(connections)
    #     if "in" in connections.keys():
    #         self.components[0].add_connections(connections["in"])
    #     elif "out" in connections.keys():
    #         self.components[2].add_connections(connections["out"])

    def handle_photon(self, photon):
        return self.components[0].handle_photon(photon)

    def control_logic(self, component_id):
        index = self.component_ids.index(component_id)

        if index == 0:
            # PhotonDetector1 currently has no function (but will in future).
            pass

        elif index == 2:
            # The photon has passed through the Polariser and been detected by
            # PhotonDetector2.
            self.current_measurement = 1
            print("Received bit: 1")

        elif index == 3:
            # The photon has been absorbed by the Polariser. This is currently
            # modelled as the photon being reflected towards PhotonDetector3.
            self.current_measurement = 0
            print("Received bit: 0")

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
        super().__init__(environment, label, connections)

