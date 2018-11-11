from consts import (
    EQUIPMENT_STRS
    # PHOTONSRC,
    # SPS,
    # POLARISER,
    # PHOTONDETECTOR,
    # POLARIMETER,
    # CCHL,
    # QCHL
)
from user import User
import equipment

class System:

    def __init__(self, environment, user_specs, channel_specs):
        self.environment = environment
        self.configure_users(user_specs)
        self.configure_channels(channel_specs)

    def create_components(self, component_specs):

        def add_component_connections(component_str, all_components, direction):
            component = all_components[component_str]
            if direction in component_specs[component.label]:
                connection_strs = component_specs[component.label][direction]
                connections = {direction: []}
                for conn_str in connection_strs:
                    for other_comp_str in all_components:
                        if other_comp_str == conn_str:
                            connections[direction].append(all_components[other_comp_str])

                components[component_str].add_connections(connections)

        components = {}
        for component_str in component_specs:
            if component_str in EQUIPMENT_STRS:
                print("Adding component {}".format(component_str))
                Component = getattr(equipment, component_str)
                components[component_str] = Component(self.environment, component_str)

        for component_str in components:
            add_component_connections(component_str, components, "in")
            add_component_connections(component_str, components, "out")

        return components

    def configure_users(self, specs):
        # EXAMPLE INPUT:
        # user_specs = {
        #     "Alice": {SPS: {"out": [POLARISER]},
        #               POLARISER: {"in": [SPS], "out": [QCHL]}},
        #     "Bob":   {PHOTONDETECTOR: {"in": [QCHL], "out": [POLARIMETER]},
        #               POLARIMETER: {"in": [PHOTONDETECTOR]}}
        # }

        users = {}
        for user_str in specs:
            print("Adding user {}".format(user_str))
            components = self.create_components(specs[user_str])
            users[user_str] = User(components, name=user_str)

        self.users = users

    def configure_channels(self, specs):
        # EXAMPLE INPUT:
        # chl_specs = {
        #     CCHL:  {"in": ["Alice", "Bob"], "out": ["Alice", "Bob"]},
        #     QCHL:  {"in": ["Alice", "Bob"], "out": ["Alice", "Bob"]}
        # }

        def add_chl_connections(chl_str, direction):
            directions = ["in", "out"]
            a = 0 if direction == directions[0] else 1
            b = 1 if a == 0 else 0

            for name in specs[chl_str][directions[a]]:
                if name in self.users:
                    # TODO: Make an "Output" device
                    for component_str in self.users[name].components:
                        components = self.users[name].components
                        if chl_str in components[component_str].connections[directions[b]]:
                            chl.add_connections({directions[a]: components[component_str]})
                            # output.add_connections({"out": chl})

        chls = {}
        for chl_str in specs:
            # Create the channel
            Chl = getattr(equipment, chl_str)
            chl = Chl(self.environment, chl_str)
            # Add the channel's connections
            add_chl_connections(chl_str, "in")
            add_chl_connections(chl_str, "out")
            chls[chl_str] = chl

        self.channels = chls
