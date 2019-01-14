#!/bin/python3

import equipment
from consts import (
    EQUIPMENT_STRS,
    BB84,
    PHOTONSRC,
    SPS,
    POLARISER,
    PHOTONDETECTOR,
    POLARIMETER,
    CCHL,
    QCHL
)

class User:

    def __init__(self, components, name="User"):
        self.components = components
        self.name = name

    def send_photon(self):

        if SPS in self.components:
            self.components[SPS].emit_photon()

        # elif "PulsedLaser" in self.components:
        #     self.components["PulsedLaser"].emit_photon()

        else:
            raise Exception("{} doesn't have a Photon Source.".format(self.name))

    def send_polarised_photon(self, orientation):

        if POLARISER in self.components:
            self.components[POLARISER].set_orientation(orientation)
            self.send_photon()

        else:
            raise Exception("{} doesn't have a Polariser.".format(self.name))

    def start_detecting_photons(self):

        if PHOTONDETECTOR in self.components:
            self.components[PHOTONDETECTOR].activate()

        else:
            raise Exception("{} doesn't have a Photon Detector.".format(self.name))

    def stop_detecting_photons(self):

        if PHOTONDETECTOR in self.components:
            self.components[PHOTONDETECTOR].deactivate()

        else:
            raise Exception("{} doesn't have a Photon Detector.".format(self.name))

    def start_measuring_photons(self):

        if POLARIMETER in self.components:
            self.components[POLARIMETER].activate()

        else:
            raise Exception("{} doesn't have a Polarimeter.".format(self.name))

    def stop_measuring_photons(self):

        if POLARIMETER in self.components:
            self.components[POLARIMETER].deactivate()

        else:
            raise Exception("{} doesn't have a Polarimeter.".format(self.name))

    def read_measurement(self):

        if POLARIMETER in self.components:
            bit = self.components[POLARIMETER].current_measurement
            print("Received bit: {}".format(bit))

        else:
            raise Exception("{} doesn't have a Polarimeter.".format(self.name))

    def bb84_sender(self, target, n):
        bb84 = self.components[BB84]
        bb84.run_sender_protocol(target, n)

    def bb84_receiver(self, n):
        bb84 = self.components[BB84]
        bb84.run_receiver_protocol(n)

    def bb84(self, target):
        NUM_BITS = 4

        bb84 = self.components[BB84]
        # Alert the receiver over the classical channel

        # Wait for a response

        # Run the protocol
        bb84.run(target, n)
