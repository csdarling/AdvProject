import threading

class Channel:

    def __init__(self, uid, environment, names):
        self.uid = uid
        self.names = names
        self.conns = {}
        self.conn_handlers = {}

    def add_conns(self, read_conn, write_conn, device_uid):
        # if device_uid not in self.conns:
        self.conns[device_uid] = (read_conn, write_conn)
        self.conn_handlers[device_uid] = threading.Thread(target=self.conn_handler,
                                                          args=(device_uid,))
        self.conn_handlers[device_uid].daemon = True
        self.conn_handlers[device_uid].start()

    def conn_handler(self, sender_uid):
        read_conn = self.conns[sender_uid][0]
        msg = read_conn.recv()
        # print("{} sent message {}".format(self.names[sender_uid], msg))
        if sender_uid in self.conns:
            self.conn_handler(sender_uid)


class ClassicalChannel(Channel):

    def __init__(self, uid, environment, names={}):
        super().__init__(uid, environment, names)
        self.names[uid] = "CChl"
        self.listeners = {}

    def start_listening(self, device1_uid, device2_uid):
        # device1 should receive any transmissions from device2
        if device2_uid not in self.listeners:
            self.listeners[device2_uid] = []

        self.listeners[device2_uid].append(device1_uid)

    def remove_connection(self, uid):
        # Device should no longer receive transmissions from any other devices.
        for other_device in self.listeners:
            if uid in self.listeners[other_device]:
                self.listeners[other_device].remove(uid)
        # Remove the connection to the channel.
        self.conns.pop(uid, None)
        # Remove the connection handler thread.
        # TODO: Find a way to interrupt the conn.recv() function.
        # ----- Use Queue instead of Pipe?
        # self.conn_handlers[uid].join()
        # self.conn_handlers.pop(uid, None)

    def conn_handler(self, sender_uid):
        read_conn = self.conns[sender_uid][0]
        msg = read_conn.recv()
        # print("{} sent message {}".format(self.names[sender_uid], msg))
        if sender_uid in self.conns:
            # Send the message to the intended recipient.
            target_uid = msg[0]
            if target_uid in self.conns and target_uid in self.listeners[sender_uid]:
                self.conns[target_uid][1].send(msg)
            # If another device is also listening to this sender, then forward
            # the message to this other device as well (CLASSICAL CHL ONLY).
            for other_uid in self.listeners[sender_uid]:
                if (other_uid != target_uid):
                    self.conns[other_uid][1].send(msg)
            self.conn_handler(sender_uid)


class QuantumChannel(Channel):

    def __init__(self, uid, environment, names):
        super().__init__(uid, environment, names)
        self.names[uid] = "QChl"

    def add_conns(self, read_conn, write_conn, device_uid):
        # Only two devices can be connected to a single QuantumChannel.
        if len(self.conns) < 2:
            # super().add_connection(conn, device_uid)
            self.conns[device_uid] = (read_conn, write_conn)
            self.conn_handlers[device_uid] = threading.Thread(target=self.conn_handler,
                                                              args=(device_uid,))
            self.conn_handlers[device_uid].daemon = True
            self.conn_handlers[device_uid].start()
        else:
            print("Can't connect {} to {} (max 2 connected devices).".format(device_uid, self.uid))

    def conn_handler(self, sender_uid):
        read_conn = self.conns[sender_uid][0]
        qubit = read_conn.recv()  # TODO: interrupt this if connection is removed.
        # TODO: remove this if statement - it's a hack for handling connection
        # being removed, but only works if an extra photon is sent.
        if sender_uid in self.conns:
            if len(self.conns) == 2:
                target_uid = [uid for uid in self.conns if uid != sender_uid][0]
                # print("Qubit {} in {} from {} to {}".format(qubit, self.names[self.uid], self.names[sender_uid], self.names[target_uid]))
                self.conns[target_uid][1].send(qubit)
            self.conn_handler(sender_uid)

