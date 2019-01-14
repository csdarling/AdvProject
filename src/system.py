import multiprocessing as mp
import threading

from consts import *
import equipment
import device
import channel


class System:

    def __init__(self, environment):
        self.environment = environment
        self.uid_count = 0
        self.cchl = self.create_new(channel.ClassicalChannel)
        self.devices = {}
        self.qchls = {}
        self.system_photons = {}
        self.system_photons_lock = threading.Lock()

    def create_new(self, ObjClass, *args, **kwargs):
        obj = ObjClass(self.uid_count, self.environment, *args, **kwargs)
        self.uid_count += 1
        return obj

    def add_device(self, device_name, device_type):
        if device_type == PHOTONDEVICE:
            labels = [SPS, POLARISER, POLARIMETER, PHOTONIO]
            labels = [device_name + "." + label for label in labels]
            sps = self.create_new(equipment.SinglePhotonSource, label=labels[0])
            polariser = self.create_new(equipment.Polariser, label=labels[1])
            polarimeter = self.create_new(equipment.Polarimeter, label=labels[2])
            photon_io = self.create_new(equipment.PhotonIO, label=labels[3])

            sps.add_connections({"out": [polariser]})
            polariser.add_connections({"out": [photon_io]})
            polarimeter.add_connections({"in": [photon_io]})

            sps.add_system_photons(self.system_photons, self.system_photons_lock)

            q_components = {
                SPS: sps,
                POLARISER: polariser,
                POLARIMETER: polarimeter,
                PHOTONIO: photon_io
            }

            labels = [BB84, CLASSICALIO]
            labels = [device_name + "." + label for label in labels]

            c_components = {
                BB84: self.create_new(equipment.Bb84, label=labels[0]),
                CLASSICALIO: self.create_new(equipment.ClassicalIO, label=labels[1])
            }

            device_uid = self.uid_count
            dev = self.create_new(device.Device,
                                  name=device_name,
                                  c_components=c_components,
                                  q_components=q_components)

            self.cchl.names[device_uid] = device_name

            connsA = mp.Pipe()
            connsB = mp.Pipe()
            self.cchl.add_conns(connsA[0], connsB[0], device_uid)
            dev.c_components[CLASSICALIO].add_conns(connsB[1], connsA[1])

            self.devices[device_uid] = dev

            return device_uid

    def start_listening(self, device1_uid, device2_uid):
        self.cchl.start_listening(device1_uid, device2_uid)

    def connect_devices_via_qchl(self, device1_uid, device2_uid):

        def connect_to_qchl(device):
            connsA = mp.Pipe()
            connsB = mp.Pipe()
            device.q_components[PHOTONIO].add_conns(connsA[0], connsB[0])
            qchl.add_conns(connsB[1], connsA[1], device.uid)

        device1 = self.devices[device1_uid]
        device2 = self.devices[device2_uid]

        names = {}
        for uid in self.devices:
            if hasattr(self.devices[uid], "name"):
                names[uid] = self.devices[uid].name

        qchl = self.create_new(channel.QuantumChannel, names)
        connect_to_qchl(device1)
        connect_to_qchl(device2)

        self.qchls[(device1, device2)] = qchl
        self.qchls[(device2, device1)] = qchl

    def send_photons(self, device_uid, freq):
        device = self.devices[device_uid]
        device.send_photons(freq)

    def stop_sending_photons(self, device_uid):
        device = self.devices[device_uid]
        device.stop_sending_photons()

    def send_n_photons(self, device_uid, n, freq=1):
        device = self.devices[device_uid]
        device.send_n_photons(n, freq)

    def send_message(self, device_uid, message):
        device = self.devices[device_uid]
        device.send_message(message)

    def run_bb84(self, sender_uid, target_uid):
        sender = self.devices[sender_uid]
        sender.bb84_sender_protocol(target_uid)

    def step_through(self, fn, level):
        with self.events_lock:
            events = {}
            for i in range(level):
                events[i] = self.events[i]

            equal = True
            while equal:
                time.sleep(0.09)
                for i in range(level):
                    if events[i] != self.events[i]:
                        equal = False
                        break

        self.print_system_diagram()
        input()

    def print_system_diagram(self):

        def get_polariser_symbol(orientation):
            symbol = ''
            if orientation == 0:
                symbol = '-'
            elif orientation == math.pi / 4:
                symbol = '/'
            elif orientation == math.pi / 2:
                symbol = '|'
            elif orientation == 3 * math.pi / 4:
                symbol = '\\'
            return symbol

        def get_polarimeter_symbol(basis):
            symbol = ''
            if basis == (0, pi / 2):
                symbol = '+'
            elif basis == (pi / 4, 3 * pi / 4):
                symbol = 'x'
            return symbol

        def get_photon_symbol(polarisation):
            symbol = '*'
            if polarisation == 0:
                symbol = '-'
            elif polarisation == math.pi / 4:
                symbol = '/'
            elif polarisation == math.pi / 2:
                symbol = '|'
            elif polarisation == 3 * math.pi / 4:
                symbol = '\\'
            return symbol

        line1 = ' ' * 7 + "ALICE" + ' ' * 33 + "BOB" + ' ' * 8
        line2 = '.' + '-' * 17 + '.' + ' ' * 7 + "QCHL" + ' ' * 7 + '.' + '-' * 17 + '.'
        line3 = '|' + ' ' * 17 + '|' + "  " + '.' + '-' * 12 + '.' + "  " + '|' + ' ' * 17 + '|'
        line4 = "|  S      P       |=>|" + ' ' * 12 + "|=>|           D     |"
        line5 = line3
        line6 = '|' + '-' * 17 + "|  |" + ' ' * 12 + "|  |" + '-' * 17 + '|'
        line7 = line3
        line8 = "|     D           |<=|" + ' ' * 12 + "|<=|       P      S  |"
        line9 = line3
        line10 = '\'' + '-' * 17 + '\'' + ' ' * 7 + "QCHL" + ' ' * 7 + '\'' + '-' * 17 + '\''

        alice_polariser = getattr(self.devices["Alice"], POLARISER)
        alice_polariser_symbol = get_polariser_symbol(alice_polariser.orientation)
        line4 = line4[:13] + alice_polariser_symbol + line4[14:]

        bob_polarimeter = getattr(self.devices["Bob"], POLARIMETER)
        bob_polarimeter_symbol = get_polarimeter_symbol(bob_polarimeter.basis)
        line4 = line4[:47] + bob_polarimeter_symbol + line4[48:]

        for photon_uid in self.system_photons:
            photon = self.system_photons[photon_uid]
            location = photon.location.label
            symbol = get_photon_symbol(photon._polarisation_axis)

            if location == getattr(Alice, SPS):
                line4 = line4[:6] + symbol + line4[7:]

            elif location == getattr(Alice, POLARISER):
                line4 = line4[:15] + symbol + line4[16:]

            elif location == getattr(Bob, POLARIMETER):
                measurement = 'D'
                if bob_polarimeter.current_measurement is not None:
                    measurement = bob_polarimeter.current_measurement
                line4 = line4[:44] + symbol + line4[45:49] + measurement + line4[50:]

