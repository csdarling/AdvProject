#!/bin/python3

import threading
import random
import numpy as np
from math import cos, sin, pi, floor, isclose

class Photon:

    def __init__(self, destination, uid):
        self.uid = uid
        self._destination = destination
        self._polarisation_axis = None
        self._collapsed = False
        self._progress()

    def _progress(self):
        self._destination, progress = self._destination.handle_photon(self)
        if progress:
            self._progress()

    def _collapse(self, phi):
        # phton_state = sin(theta)|0> + cos(theta)|1>
        # basis_state =   sin(phi)|0> +   cos(phi)|1>
        # bdual_state =   cos(phi)|0> -   sin(phi)|1>

        theta = self._polarisation_axis

        phi_perp = phi + pi/2
        phi_perp -= 2 * pi * floor(phi_perp / (2 * pi))
        results = [phi, phi_perp]

        coeffs = [sin(theta) * sin(phi) + cos(theta) * cos(phi),
                  sin(theta) * cos(phi) - cos(theta) * sin(phi)]
        prob_distr = [coeff ** 2 for coeff in coeffs]

        idx = np.random.choice(2, 1, p=prob_distr)[0]
        self._polarisation_axis = results[idx]
        self.collapsed = True

        # if isclose(self._polarisation, meas_basis[0]):
        #     prob_distr = [0, 1]
        # elif isclose(self._polarisation, meas_basis[1]):
        #     prob_distr = [1, 0]
        # else:
        #     prob_distr = [0.5, 0.5]

        # self.state = np.random.choice(2, 1, p=prob_distr)[0]

    def polarise(self, theta):
        self._polarisation_axis = theta

    def measure(self, angle):
        if not self._collapsed:
            self._collapse(angle)
        return self._polarisation_axis


    # def _progress(self):
    #     '''Move the photon to the next node in its path.'''

    #     if not len(self.path) - 1:
    #         self.in_system = False
    #         return

    #     # TODO: Model probability of successfully reaching the next node
    #     self.path = self.path[1:]

    #     if hasattr(self.path[0], "log_photon"):
    #         self.path[0].log_photon(self.uid)

    #     if hasattr(self.path[0], "orientation"):
    #         self._polarisation = self.path[0].orientation
    #         # self._state = (sin(theta), cos(theta))

    #     if hasattr(self.path[0], "detect_photon"):
    #         self.path[0].detect_photon()

    #     if hasattr(self.path[0], "measure_photon"):
    #         self._collapse(self.path[0].basis)
    #         self.path[0].measure_photon(self.state)

    #     # timer = threading.Timer(random.random() / 100, self._progress)
    #     # timer.start()
    #     self._progress()

